"""D2 response deadline, bounded concurrency, ownership and remote adapter."""
import gc
import io
import threading
import time
import weakref

import c2pa
import pytest
from test_c2pa_d2 import FIX
from test_offline_c2pa import _remote_reference_jpeg

from litmus.c2pa import reader as reader_mod
from litmus.c2pa.pipeline import analyze_c2pa
from litmus.c2pa.reader import ReadOutcome, classify_error, read_store
from litmus.c2pa.rules import TIMEOUT_LIMITATION
from litmus.c2pa.settings import production_config
from litmus.c2pa.worker import get_worker


@pytest.fixture
def worker():
    worker = get_worker()
    assert worker.wait_idle(3)
    yield worker
    assert worker.wait_idle(3)


def test_deadline_busy_recovery_bounded_threads_and_input_release(worker):
    started, release = threading.Event(), threading.Event()
    thread_ids = []

    class Buffer:
        pass

    data = Buffer()
    reference = weakref.ref(data)

    def blocked(data, mime, config):
        thread_ids.append(threading.get_ident())
        started.set()
        assert release.wait(3)
        return ReadOutcome("no_credentials")

    before = [t.ident for t in threading.enumerate()
              if t.name == "litmus-c2pa-worker"]
    try:
        start = time.monotonic()
        outcome = analyze_c2pa(data, "image/jpeg", config={}, read=blocked,
                               worker=worker, deadline=0.03)
        elapsed = time.monotonic() - start
        assert started.is_set()
        assert (outcome.rule, outcome.result) == (2, "error")
        assert "c2pa_timeout" in outcome.reasons
        assert TIMEOUT_LIMITATION in outcome.limitations
        assert elapsed < 0.75
        del data
        gc.collect()
        assert reference() is not None  # timeout has not cancelled the job
        start = time.monotonic()
        for _ in range(30):
            busy = analyze_c2pa(b"", "image/jpeg", config={}, read=blocked,
                                worker=worker, deadline=1)
            assert busy.reasons == ["c2pa_error", "c2pa_worker_busy"]
        assert time.monotonic() - start < 0.75
        assert [t.ident for t in threading.enumerate()
                if t.name == "litmus-c2pa-worker"] == before
    finally:
        release.set()
    assert worker.wait_idle(3)
    gc.collect()
    assert reference() is None
    recovered = analyze_c2pa(b"", "image/jpeg", config={}, worker=worker,
                             read=lambda *args: ReadOutcome("no_credentials"))
    assert recovered.rule == 3
    assert len(thread_ids) == 1


@pytest.mark.parametrize("raises", [False, True])
def test_abandoned_result_or_exception_released_while_idle(worker, raises):
    release = threading.Event()
    refs = []

    class Payload:
        pass

    def job():
        payload = Payload()
        refs.append(weakref.ref(payload))
        assert release.wait(3)
        if raises:
            raise RuntimeError("constructed worker failure")
        return payload

    try:
        assert worker.submit(job, deadline=0.02).status == "timeout"
    finally:
        release.set()
    assert worker.wait_idle(3)
    # wait_idle includes completion publication and dropping worker references.
    gc.collect()
    assert refs[0]() is None


def test_concurrent_callers_admit_one_job(worker):
    started, release = threading.Event(), threading.Event()
    calls = []
    results = []

    def job():
        calls.append(threading.get_ident())
        started.set()
        assert release.wait(3)
        return "done"

    caller = threading.Thread(target=lambda: results.append(
        worker.submit(job, deadline=2)))
    caller.start()
    try:
        assert started.wait(1)
        assert worker.submit(job, deadline=0.1).status == "busy"
    finally:
        release.set()
        caller.join(3)
    assert len(calls) == 1
    assert results[0].value == "done"


@pytest.mark.parametrize("failure", [None, "context", "reader", "json"])
@pytest.mark.parametrize("timed_out", [False, True])
def test_read_resources_closed_on_worker_on_all_exit_paths(monkeypatch, worker,
                                                          failure, timed_out):
    events = []
    streams = []
    release = threading.Event()
    real_bytes_io = io.BytesIO

    def record(event):
        events.append((event, threading.get_ident()))

    class Settings:
        def close(self):
            record("settings.close")

    class Context:
        def __init__(self, **kwargs):
            record("context.new")
            if timed_out:
                assert release.wait(3)
            if failure == "context":
                raise RuntimeError("context failure")

        def close(self):
            record("context.close")

    class Stream(real_bytes_io):
        def __init__(self, data):
            super().__init__(data)
            streams.append(self)
            record("stream.new")

        def close(self):
            record("stream.close")
            super().close()

    class Reader:
        def __init__(self, *args, **kwargs):
            record("reader.new")
            if failure == "reader":
                raise c2pa.C2paError("constructed reader failure")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            record("reader.close")

        def json(self):
            return "bad-json" if failure == "json" else "{}"

    monkeypatch.setattr(reader_mod, "build_settings", lambda config: Settings())
    monkeypatch.setattr(c2pa, "Context", Context)
    monkeypatch.setattr(c2pa, "Reader", Reader)
    monkeypatch.setattr(reader_mod.io, "BytesIO", Stream)
    try:
        response = worker.submit(read_store, b"image", "image/jpeg", {},
                                 deadline=0.02 if timed_out else 1)
        assert response.status == ("timeout" if timed_out else "done")
        if timed_out:
            assert "settings.close" not in [e for e, _ in events]
    finally:
        release.set()
    assert worker.wait_idle(3)
    names = [e for e, _ in events]
    assert names[-1] == "settings.close"
    if failure != "context":
        assert "context.close" in names
        assert streams and all(s.closed for s in streams)
    if failure in (None, "json"):
        assert names.index("reader.close") < names.index("stream.close")
    assert len({ident for _, ident in events}) == 1
    assert events[0][1] != threading.get_ident()


@pytest.mark.parametrize("variant", ["builder", "xmp"])
def test_remote_adapter_zero_connections_and_passing_control(variant,
                                                           c2pa_fixture_trap):
    trap = c2pa_fixture_trap
    data = ((FIX / "remote_reference.jpg").read_bytes() if variant == "builder"
            else _remote_reference_jpeg(trap.url + "/manifest.c2pa"))
    outcome = analyze_c2pa(data, "image/jpeg", config=production_config())
    assert (outcome.rule, outcome.result, outcome.label) == (
        4, "inconclusive", "remote_reference_only")
    assert trap.connections == []
    config = production_config()
    config["verify"]["remote_manifest_fetch"] = True
    config["core"]["allowed_network_hosts"] = [f"{trap.host}:{trap.port}"]
    control = analyze_c2pa(data, "image/jpeg", config=config)
    assert control.rule == 2  # the trap deliberately serves 404
    assert len(trap.connections) == 1
    assert trap.requests == ["/manifest.c2pa"]


@pytest.mark.parametrize("message,versions,fetch,kind", [
    (reader_mod.REMOTE_PREFIX + "http://127.0.0.1/x", ("0.38.0", "0.91.0"),
     False, "remote_reference_only"),
    (reader_mod.REMOTE_PREFIX + "http://127.0.0.1/x", ("0.38.0", "future"),
     False, "error"),
    (reader_mod.REMOTE_PREFIX + "http://127.0.0.1/x", ("future", "0.91.0"),
     False, "error"),
    (reader_mod.REMOTE_PREFIX + "http://127.0.0.1/x", ("0.38.0", "0.91.0"),
     True, "error"),
    ("other error with " + reader_mod.REMOTE_PREFIX, ("0.38.0", "0.91.0"),
     False, "error")])
def test_remote_adapter_narrow_version_and_prefix_gate(message, versions,
                                                     fetch, kind):
    config = production_config()
    config["verify"]["remote_manifest_fetch"] = fetch
    outcome = classify_error(c2pa.C2paError(message), config, versions)
    assert outcome.kind == kind


def test_worker_recovers_after_exception(worker):
    def broken(*args):
        raise ValueError("constructed read error")
    outcome = analyze_c2pa(b"", "image/jpeg", config={}, read=broken, worker=worker)
    assert outcome.reasons == ["c2pa_error", "c2pa_exception:ValueError"]
    assert worker.submit(lambda: 42, deadline=1).value == 42
