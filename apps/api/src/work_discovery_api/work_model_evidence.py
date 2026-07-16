from __future__ import annotations

from dataclasses import dataclass

from work_discovery_api.models import JsonObject, JsonValue, WorkModelRead
from work_discovery_api.risk_assessment import RiskAssessment, assess_risk


@dataclass(frozen=True, slots=True)
class EvidenceProfile:
    model_id: str
    project_id: str
    work_model_version: int
    title: str
    summary: str
    process_id: str
    process_count: int
    step_count: int
    manual_step_count: int
    reversible_step_count: int
    artifact_count: int
    structured_artifact_count: int
    system_count: int
    clear_system_count: int
    rule_count: int
    decision_count: int
    exception_count: int
    pain_count: int
    pain_severity_total: int
    metric_count: int
    risk: RiskAssessment
    evidence_refs: tuple[str, ...]
    has_source_refs: bool
    source_link_rate: float
    confirmed_claim_rate: float
    open_contradiction_count: int
    epistemic_coverage: float
    operational_readiness: float
    risk_clarity: float
    recent_case_present: bool
    open_material_gaps: tuple[str, ...]


def evidence_profile(model: WorkModelRead) -> EvidenceProfile:
    payload = model.payload
    processes = object_list(payload.get("processes"))
    steps = process_steps(processes)
    artifacts = object_list(payload.get("artifacts"))
    systems = object_list(payload.get("systems"))
    decisions = object_list(payload.get("decisions"))
    rules = object_list(payload.get("rules"))
    exceptions = object_list(payload.get("exceptions"))
    pains = object_list(payload.get("pain_points"))
    metrics = object_list(payload.get("metrics"))
    evidence_summary = object_value(payload.get("evidence_summary"))
    gate = object_value(payload.get("understanding_gate"))
    process = processes[0] if processes else {}
    process_id = string_value(process.get("id"), "process-discovered-work")
    evidence_refs = collected_source_refs(payload)
    open_contradictions = int_value(
        evidence_summary.get("open_contradiction_count"),
        0,
    )
    return EvidenceProfile(
        model_id=string_value(payload.get("model_id"), f"wm-{model.project_id}"),
        project_id=model.project_id,
        work_model_version=model.version,
        title=string_value(payload.get("title"), "Discovered work"),
        summary=string_value(payload.get("summary"), "Work model summary is not yet available."),
        process_id=process_id,
        process_count=len(processes),
        step_count=len(steps),
        manual_step_count=count_true(steps, "manual_touch"),
        reversible_step_count=count_true(steps, "reversible"),
        artifact_count=len(artifacts),
        structured_artifact_count=structured_artifact_count(artifacts),
        system_count=len(systems),
        clear_system_count=clear_system_count(systems),
        rule_count=len(rules),
        decision_count=len(decisions),
        exception_count=len(exceptions),
        pain_count=len(pains),
        pain_severity_total=sum(int_value(item.get("severity"), 2) for item in pains),
        metric_count=len(metrics),
        risk=assess_risk(payload, open_contradictions),
        evidence_refs=evidence_refs or (process_id,),
        has_source_refs=bool(evidence_refs),
        source_link_rate=float_value(evidence_summary.get("source_link_rate"), 0),
        confirmed_claim_rate=float_value(evidence_summary.get("confirmed_claim_rate"), 0),
        open_contradiction_count=open_contradictions,
        epistemic_coverage=float_value(gate.get("epistemic_coverage"), 0),
        operational_readiness=float_value(gate.get("operational_readiness"), 0),
        risk_clarity=float_value(gate.get("risk_clarity"), 0),
        recent_case_present=bool_value(gate.get("recent_case_present"), fallback=False),
        open_material_gaps=string_tuple(gate.get("open_material_gaps")),
    )


def object_list(value: JsonValue | None) -> tuple[JsonObject, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, dict))


def object_value(value: JsonValue | None) -> JsonObject:
    if isinstance(value, dict):
        return value
    return {}


def process_steps(processes: tuple[JsonObject, ...]) -> tuple[JsonObject, ...]:
    steps: list[JsonObject] = []
    for process in processes:
        steps.extend(object_list(process.get("steps")))
    return tuple(steps)


def structured_artifact_count(artifacts: tuple[JsonObject, ...]) -> int:
    return sum(
        1
        for item in artifacts
        if string_value(item.get("format"), "").upper() not in {"", "UNKNOWN", "TEXT"}
        or len(object_list(item.get("data_fields"))) > 0
    )


def clear_system_count(systems: tuple[JsonObject, ...]) -> int:
    return sum(
        1
        for item in systems
        if string_value(item.get("access_method"), "").upper() not in {"", "UNKNOWN"}
        and string_value(item.get("stability"), "").upper() not in {"", "UNKNOWN"}
    )


def collected_source_refs(payload: JsonObject) -> tuple[str, ...]:
    refs: list[str] = []
    collect_source_refs(payload, refs)
    return tuple(unique_strings(refs))


def collect_source_refs(value: JsonValue | None, refs: list[str]) -> None:
    if isinstance(value, dict):
        source_refs = value.get("source_refs")
        refs.extend(string_tuple(source_refs))
        for child in value.values():
            collect_source_refs(child, refs)
        return
    if isinstance(value, list):
        for child in value:
            collect_source_refs(child, refs)


def count_true(items: tuple[JsonObject, ...], key: str) -> int:
    return sum(1 for item in items if bool_value(item.get(key), fallback=False))


def string_value(value: JsonValue | None, fallback: str) -> str:
    if isinstance(value, str) and value:
        return value
    return fallback


def string_tuple(value: JsonValue | None) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)


def bool_value(value: JsonValue | None, *, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    return fallback


def int_value(value: JsonValue | None, fallback: int) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        return round(value)
    return fallback


def float_value(value: JsonValue | None, fallback: float) -> float:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return fallback


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result
