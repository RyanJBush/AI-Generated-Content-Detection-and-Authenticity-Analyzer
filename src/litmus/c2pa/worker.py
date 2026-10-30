"""Bounded C2PA worker (R1-D plan §p Correction 3).

- One dedicated worker thread per process (``get_worker``).
- At most one outstanding C2PA task.
- The per-analyzer timeout is a RESPONSE DEADLINE, not cancellation: when it
  passes, the caller gets ``timeout`` and the task keeps running.
- While a task (timed out or not) is still running, new requests return
  ``busy`` immediately instead of queuing.
- The task's inputs (bytes, streams, library handles) are owned by the worker:
  the task function creates and closes them, and the worker drops its
  references when the task finishes, whether or not anyone is still waiting.
- No thread is ever added after the first: the worker is never replaced.
"""
import threading
from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class WorkerResult:
    status: str  # done | timeout | busy
    value: Any = None
    error: Optional[BaseException] = None


class _Job:
    def __init__(self, fn, args):
        self.fn, self.args = fn, args
        self.value, self.error = None, None
        self.done = threading.Event()


class C2paWorker:
    def __init__(self, name: str = "litmus-c2pa-worker"):
        self._cond = threading.Condition()
        self._job: Optional[_Job] = None
        self._busy = False
        self._thread = threading.Thread(target=self._run, name=name, daemon=True)
        self._thread.start()

    @property
    def busy(self) -> bool:
        with self._cond:
            return self._busy

    def submit(self, fn: Callable, *args, deadline: float) -> WorkerResult:
        with self._cond:
            if self._busy:
                return WorkerResult("busy")
            job = _Job(fn, args)
            self._busy, self._job = True, job
            self._cond.notify_all()
        if not job.done.wait(deadline):
            return WorkerResult("timeout")
        return WorkerResult("done", value=job.value, error=job.error)

    def wait_idle(self, timeout: float) -> bool:
        """True once no task is running (for tests and orderly shutdown)."""
        with self._cond:
            return self._cond.wait_for(lambda: not self._busy, timeout)

    def _run(self):
        while True:
            with self._cond:
                self._cond.wait_for(lambda: self._job is not None)
                job = self._job
            try:
                job.value = job.fn(*job.args)
            except BaseException as e:  # reported to the caller, never raised here
                # Tracebacks retain the read frame and its native resources.
                e.__traceback__ = None
                job.error = e
            finally:
                job.fn = job.args = None  # release the task's inputs
                with self._cond:
                    job.done.set()
                    self._job = None
                    job = None  # release abandoned outputs before publishing idle
                    self._busy = False
                    self._cond.notify_all()


_WORKER: Optional[C2paWorker] = None
_WORKER_LOCK = threading.Lock()


def get_worker() -> C2paWorker:
    """The single C2PA worker of this process (created on first use)."""
    global _WORKER
    with _WORKER_LOCK:
        if _WORKER is None:
            _WORKER = C2paWorker()
        return _WORKER
