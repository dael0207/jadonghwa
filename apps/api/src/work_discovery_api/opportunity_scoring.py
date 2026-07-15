from __future__ import annotations

from dataclasses import dataclass

from work_discovery_api.work_model_evidence import EvidenceProfile, unique_strings


@dataclass(frozen=True, slots=True)
class ScoreDecision:
    value: int
    feasibility: int
    risk: int
    evidence_confidence: float
    oversight: int
    portfolio_class: str
    gate_result: str
    blocked_reasons: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    required_followups: tuple[str, ...]
    recommendation_mode: str
    recommendation_title: str
    explanation: tuple[str, ...]


def score_profile(profile: EvidenceProfile) -> ScoreDecision:
    value = clamp_int(
        20
        + profile.step_count * 5
        + profile.manual_step_count * 4
        + profile.pain_count * 8
        + profile.pain_severity_total * 3
        + min(profile.metric_count * 8, 16),
        0,
        100,
    )
    feasibility = clamp_int(
        20
        + profile.structured_artifact_count * 12
        + profile.clear_system_count * 10
        + profile.rule_count * 9
        + profile.decision_count * 6
        + min(profile.reversible_step_count * 3, 12)
        + round(profile.operational_readiness * 18)
        - unknown_penalty(profile),
        0,
        100,
    )
    risk = clamp_int(
        1
        + profile.risk_constraint_count
        + profile.authority_constraint_count
        + min(profile.exception_count, 1)
        + (1 if profile.open_contradiction_count > 0 else 0),
        0,
        4,
    )
    evidence_confidence = clamp_float(
        0.2
        + profile.source_link_rate * 0.25
        + profile.confirmed_claim_rate * 0.25
        + profile.epistemic_coverage * 0.2
        + profile.operational_readiness * 0.1
        + profile.risk_clarity * 0.07
        + (0.05 if profile.recent_case_present else 0)
        - len(profile.open_material_gaps) * 0.08
        - profile.open_contradiction_count * 0.12,
        0,
        1,
    )
    oversight = clamp_int(
        1 + risk + min(profile.exception_count, 1) - min(profile.rule_count, 1),
        0,
        5,
    )
    missing = missing_evidence(profile, feasibility, evidence_confidence)
    followups = required_followups(profile, risk, missing)
    gate = gate_result(feasibility, risk, evidence_confidence)
    portfolio = portfolio_class(value, feasibility, risk, evidence_confidence, gate)
    return ScoreDecision(
        value=value,
        feasibility=feasibility,
        risk=risk,
        evidence_confidence=round(evidence_confidence, 2),
        oversight=oversight,
        portfolio_class=portfolio,
        gate_result=gate,
        blocked_reasons=blocked_reasons(feasibility, risk, evidence_confidence),
        missing_evidence=missing,
        required_followups=followups,
        recommendation_mode=recommendation_mode(portfolio, gate, profile),
        recommendation_title=recommendation_title(portfolio, gate),
        explanation=score_explanation(profile, value, feasibility, risk, evidence_confidence),
    )


def unknown_penalty(profile: EvidenceProfile) -> int:
    missing_systems = max(profile.system_count - profile.clear_system_count, 0)
    missing_artifacts = max(profile.artifact_count - profile.structured_artifact_count, 0)
    return min((missing_systems + missing_artifacts) * 10, 30)


def missing_evidence(
    profile: EvidenceProfile,
    feasibility: int,
    evidence_confidence: float,
) -> tuple[str, ...]:
    missing: list[str] = list(profile.open_material_gaps)
    if profile.structured_artifact_count == 0:
        missing.append("Structured input and output artifacts")
    if profile.clear_system_count == 0:
        missing.append("System access method and stability")
    if profile.rule_count == 0:
        missing.append("Decision rules")
    if profile.exception_count == 0:
        missing.append("Exception cases")
    if feasibility < 60:
        missing.append("Implementation feasibility evidence")
    if evidence_confidence < 0.75:
        missing.append("Confirmed evidence coverage")
    return tuple(unique_strings(missing))


def required_followups(
    profile: EvidenceProfile,
    risk: int,
    missing: tuple[str, ...],
) -> tuple[str, ...]:
    followups = [f"Collect evidence for: {item}" for item in missing[:4]]
    if risk >= 3:
        followups.append("Clarify human approval and authority boundary")
    if profile.metric_count == 0:
        followups.append("Capture rough frequency, volume, and rework estimates")
    return tuple(unique_strings(followups))


def gate_result(feasibility: int, risk: int, evidence_confidence: float) -> str:
    if risk >= 4 and evidence_confidence < 0.8:
        return "BLOCKED"
    if feasibility >= 70 and evidence_confidence >= 0.75 and risk <= 2:
        return "READY_FOR_DESIGN"
    if feasibility >= 50 and evidence_confidence >= 0.6 and risk <= 3:
        return "ENABLE_FIRST"
    return "DISCOVERY_NEEDED"


def portfolio_class(value: int, feasibility: int, risk: int, confidence: float, gate: str) -> str:
    if gate == "BLOCKED":
        return "DO_NOT_AUTOMATE" if risk >= 4 else "NO_BUILD"
    if risk >= 3:
        return "HUMAN_CONTROLLED"
    if gate == "DISCOVERY_NEEDED" or feasibility < 70 or confidence < 0.75:
        return "ENABLE_FIRST"
    if value >= 75:
        return "STRATEGIC_BET"
    return "QUICK_WIN"


def blocked_reasons(feasibility: int, risk: int, evidence_confidence: float) -> tuple[str, ...]:
    reasons: list[str] = []
    if feasibility < 70:
        reasons.append("Feasibility evidence is below G1 readiness threshold")
    if evidence_confidence < 0.75:
        reasons.append("Evidence confidence is below G1 readiness threshold")
    if risk >= 3:
        reasons.append("Risk requires stronger human oversight before design")
    return tuple(reasons)


def recommendation_mode(portfolio: str, gate: str, profile: EvidenceProfile) -> str:
    if gate == "BLOCKED":
        return "HUMAN_ONLY"
    if gate == "ENABLE_FIRST":
        return "SIMPLIFY_STANDARDIZE"
    if gate == "READY_FOR_DESIGN" and profile.rule_count > 0 and profile.clear_system_count > 0:
        return "DETERMINISTIC_AUTOMATION"
    if portfolio == "HUMAN_CONTROLLED":
        return "KNOWLEDGE_ASSIST"
    return "FORM_DASHBOARD"


def recommendation_title(portfolio: str, gate: str) -> str:
    if gate == "READY_FOR_DESIGN":
        return "Proceed to G1 design readiness"
    if gate == "ENABLE_FIRST":
        return "Enable the workflow before design"
    if gate == "BLOCKED":
        return "Keep the work manual for now"
    if portfolio == "HUMAN_CONTROLLED":
        return "Assist with human-controlled execution"
    return "Continue discovery before automation design"


def score_explanation(
    profile: EvidenceProfile,
    value: int,
    feasibility: int,
    risk: int,
    evidence_confidence: float,
) -> tuple[str, ...]:
    return (
        f"Value {value}: steps={profile.step_count}, manual_steps={profile.manual_step_count}, "
        f"pain_points={profile.pain_count}, metrics={profile.metric_count}.",
        f"Feasibility {feasibility}: structured_artifacts={profile.structured_artifact_count}, "
        f"clear_systems={profile.clear_system_count}, rules={profile.rule_count}.",
        f"Risk {risk}: risk_constraints={profile.risk_constraint_count}, "
        f"authority_constraints={profile.authority_constraint_count}, "
        f"exceptions={profile.exception_count}.",
        f"Evidence confidence {round(evidence_confidence, 2)}: source_link_rate="
        f"{profile.source_link_rate}, confirmed_claim_rate={profile.confirmed_claim_rate}, "
        f"open_gaps={len(profile.open_material_gaps)}.",
        "Oversight: derived from risk and exception handling needs.",
    )


def clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def clamp_float(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
