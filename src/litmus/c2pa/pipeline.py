"""Read -> map -> rules for one image (R1-D2). Not wired into reports: C2PA
analysis stays disabled until D3 is approved.
"""
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
    if supported is None:
        supported = supported_mime_types()
    if mime not in supported:
        return evaluate_rules(RuleInput(format_supported=False, read_kind="error"))

    res = (worker or get_worker()).submit(read, data, mime, config,
                                          deadline=deadline)
    if res.status == "busy":
        return evaluate_rules(RuleInput(True, "error", ["c2pa_worker_busy"]))
    if res.status == "timeout":
        return evaluate_rules(RuleInput(True, "error", ["c2pa_timeout"]))
    if res.error is not None:
        return evaluate_rules(RuleInput(
            True, "error", [f"c2pa_exception:{type(res.error).__name__}"]))

    outcome: ReadOutcome = res.value
    if outcome.kind == "error":
        return evaluate_rules(RuleInput(True, "error", outcome.reasons))
    if outcome.kind != "store":
        return evaluate_rules(RuleInput(True, outcome.kind))
    try:
        mapped = map_store(outcome.store, policy)
    except MappingError:
        return evaluate_rules(RuleInput(True, "error", ["c2pa_mapping_error"]))
    outcome_rules = evaluate_rules(RuleInput(True, "store", mapped=mapped))
    outcome_rules.details["mapped"] = mapped
    return outcome_rules
