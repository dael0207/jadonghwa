from __future__ import annotations

from work_discovery_api.models import (
    JsonObject,
    JsonValue,
    OpportunityDiffRead,
    OpportunityRead,
    ReadinessRead,
    utc_now,
)

SCORE_KEYS: tuple[str, ...] = (
    "value",
    "feasibility",
    "risk",
    "evidence_confidence",
    "oversight",
)


def readiness_from_opportunity(
    project_id: str,
    interview_id: str | None,
    opportunity: OpportunityRead,
) -> ReadinessRead:
    payload = opportunity.payload
    scores = object_value(payload.get("scores"))
    gate = object_value(payload.get("gate"))
    result = string_value(gate.get("result"), "BLOCKED")
    if not opportunity.schema_valid:
        result = "BLOCKED"
    score_summary = score_summary_from(scores)
    blocking = list(string_tuple(gate.get("blocked_reasons")))
    if not opportunity.schema_valid:
        blocking.append("Opportunity payload does not pass schema validation")
    missing = missing_evidence_from_scores(scores)
    followups = list(string_tuple(payload.get("open_questions")))
    if not followups:
        followups.extend(f"Resolve: {item}" for item in missing)
    ready_for_g1 = result == "READY_FOR_DESIGN" and not blocking and opportunity.schema_valid
    return ReadinessRead(
        project_id=project_id,
        interview_id=interview_id,
        work_model_version=opportunity.work_model_version,
        ready_for_g1=ready_for_g1,
        result=result,
        blocking_reasons=tuple(unique_strings(blocking)),
        missing_evidence=missing,
        required_followups=tuple(unique_strings(followups)),
        score_summary=score_summary,
        created_at=utc_now(),
    )


def diff_opportunities(
    project_id: str,
    previous: OpportunityRead,
    latest: OpportunityRead,
) -> OpportunityDiffRead:
    previous_scores = object_value(previous.payload.get("scores"))
    latest_scores = object_value(latest.payload.get("scores"))
    previous_gate = object_value(previous.payload.get("gate"))
    latest_gate = object_value(latest.payload.get("gate"))
    previous_result = string_value(previous_gate.get("result"), "BLOCKED")
    latest_result = string_value(latest_gate.get("result"), "BLOCKED")
    previous_evidence = set(string_tuple(previous.payload.get("evidence_refs")))
    latest_evidence = set(string_tuple(latest.payload.get("evidence_refs")))
    previous_blockers = set(string_tuple(previous_gate.get("blocked_reasons")))
    latest_blockers = set(string_tuple(latest_gate.get("blocked_reasons")))
    return OpportunityDiffRead(
        project_id=project_id,
        previous_opportunity_id=previous.id,
        latest_opportunity_id=latest.id,
        score_changes=score_changes(previous_scores, latest_scores),
        gate_result_changed=previous_result != latest_result,
        previous_gate_result=previous_result,
        latest_gate_result=latest_result,
        added_evidence_refs=tuple(sorted(latest_evidence - previous_evidence)),
        removed_evidence_refs=tuple(sorted(previous_evidence - latest_evidence)),
        changed_blocked_reasons=tuple(sorted(previous_blockers.symmetric_difference(latest_blockers))),
        recommendation_changed=recommendation_changed(previous.payload, latest.payload),
        created_at=utc_now(),
    )


def score_summary_from(scores: JsonObject) -> JsonObject:
    summary: JsonObject = {}
    for key in SCORE_KEYS:
        value = scores.get(key)
        if isinstance(value, int | float) and not isinstance(value, bool):
            summary[key] = value
    portfolio = scores.get("portfolio_class")
    if isinstance(portfolio, str):
        summary["portfolio_class"] = portfolio
    return summary


def score_changes(previous_scores: JsonObject, latest_scores: JsonObject) -> JsonObject:
    changes: JsonObject = {}
    for key in SCORE_KEYS:
        previous = number_value(previous_scores.get(key))
        latest = number_value(latest_scores.get(key))
        if previous is None or latest is None:
            continue
        changes[key] = {
            "previous": previous,
            "latest": latest,
            "delta": round(latest - previous, 3),
        }
    previous_class = previous_scores.get("portfolio_class")
    latest_class = latest_scores.get("portfolio_class")
    if isinstance(previous_class, str) and isinstance(latest_class, str):
        changes["portfolio_class"] = {
            "previous": previous_class,
            "latest": latest_class,
            "changed": previous_class != latest_class,
        }
    return changes


def missing_evidence_from_scores(scores: JsonObject) -> tuple[str, ...]:
    missing: list[str] = []
    feasibility = number_value(scores.get("feasibility"))
    confidence = number_value(scores.get("evidence_confidence"))
    risk = number_value(scores.get("risk"))
    if feasibility is None or feasibility < 70:
        missing.append("Feasibility evidence")
    if confidence is None or confidence < 0.75:
        missing.append("Confirmed evidence coverage")
    if risk is not None and risk >= 3:
        missing.append("Human oversight and risk boundary")
    return tuple(missing)


def recommendation_changed(previous_payload: JsonObject, latest_payload: JsonObject) -> bool:
    previous = object_value(previous_payload.get("recommendation"))
    latest = object_value(latest_payload.get("recommendation"))
    keys = ("solution_mode", "title", "autonomy_level")
    return any(previous.get(key) != latest.get(key) for key in keys)


def object_value(value: JsonValue | None) -> JsonObject:
    if isinstance(value, dict):
        return value
    return {}


def string_value(value: JsonValue | None, fallback: str) -> str:
    if isinstance(value, str) and value:
        return value
    return fallback


def string_tuple(value: JsonValue | None) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)


def number_value(value: JsonValue | None) -> float | None:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return None


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result
