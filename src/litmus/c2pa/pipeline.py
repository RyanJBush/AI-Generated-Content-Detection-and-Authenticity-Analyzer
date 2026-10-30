"""Read -> map -> rules for one image (D2); diagnostics for the D3 adapter."""
import time
from typing import Any, Callable, Dict, Iterable, Optional

from litmus.c2pa.mapping import PRODUCTION_POLICY, MappingError, TrustPolicy, map_store
from litmus.c2pa.reader import ReadOutcome, read_store, supported_mime_types
from litmus.c2pa.rules import RuleInput, RuleOutcome, evaluate_rules
from litmus.c2pa.worker import C2paWorker, get_worker

DEADLINE_SECONDS = 120.0  # SPEC §6.2: response deadline, not cancellation


def analyze_c2pa(data: bytes, mime: str, *, config: Dict[str, Any],
                 policy: TrustPolicy = PRODUCTION_POLICY,
                 worker: Optional[C2paWorker] = None,
                 deadline: float = DEADLINE_SECONDS,
                 read: Callable[..., ReadOutcome] = read_store,
                 supported: Optional[Iterable[str]] = None) -> RuleOutcome:
    started = time.perf_counter()

    def finish(result, read_outcome=None):
        result.details.update({
            "read_kind": read_outcome.kind if read_outcome else None,
            "read_detail": read_outcome.detail if read_outcome else None,
            "settings_applied": (read_outcome.settings_applied
                                 if read_outcome else None),
            "timings": {
                "read_seconds": read_outcome.read_seconds if read_outcome else None,
                "read_response_seconds": time.perf_counter() - started,
            },
        })
        return result

    if supported is None:
        supported = supported_mime_types()
    if mime not in supported:
        return finish(evaluate_rules(RuleInput(False, "error")))

    res = (worker or get_worker()).submit(read, data, mime, config,
                                          deadline=deadline)
    if res.status == "busy":
        return finish(evaluate_rules(RuleInput(True, "error", ["c2pa_worker_busy"])))
    if res.status == "timeout":
        return finish(evaluate_rules(RuleInput(True, "error", ["c2pa_timeout"])))
    if res.error is not None:
        return finish(evaluate_rules(RuleInput(
            True, "error", [f"c2pa_exception:{type(res.error).__name__}"])))

    outcome: ReadOutcome = res.value
    if outcome.kind == "error":
        return finish(evaluate_rules(RuleInput(True, "error", outcome.reasons)),
                      outcome)
    if outcome.kind != "store":
        return finish(evaluate_rules(RuleInput(True, outcome.kind)), outcome)
    try:
        mapped = map_store(outcome.store, policy)
    except MappingError:
        return finish(evaluate_rules(RuleInput(True, "error", ["c2pa_mapping_error"])),
                      outcome)
    outcome_rules = evaluate_rules(RuleInput(True, "store", mapped=mapped))
    outcome_rules.details["mapped"] = mapped
    return finish(outcome_rules, outcome)
