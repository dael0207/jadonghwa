from __future__ import annotations

from dataclasses import dataclass

from work_discovery_api.opportunity_explanation import ScoreNarrative, build_score_explanation
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


@dataclass(frozen=True, slots=True)
class GateMetrics:
    feasibility: int
    residual_risk: int
    evidence_confidence: float


@dataclass(frozen=True, slots=True)
class ScoreSnapshot:
    value: int
    metrics: GateMetrics
    gate_result: str


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
    risk = profile.risk.residual_risk
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
        1
        + risk
        + min(len(profile.risk.unresolved_exceptions), 1)
        - min(profile.rule_count, 1),
        0,
        5,
    )
    metrics = GateMetrics(
        feasibility=feasibility,
        residual_risk=risk,
        evidence_confidence=evidence_confidence,
    )
    gate = gate_result(profile, metrics)
    snapshot = ScoreSnapshot(value=value, metrics=metrics, gate_result=gate)
    missing = missing_evidence(profile, metrics)
    followups = required_followups(profile, missing)
    portfolio = portfolio_class(snapshot)
    blocking = blocked_reasons(profile, metrics)
    return ScoreDecision(
        value=value,
        feasibility=feasibility,
        risk=risk,
        evidence_confidence=round(evidence_confidence, 2),
        oversight=oversight,
        portfolio_class=portfolio,
        gate_result=gate,
        blocked_reasons=blocking,
        missing_evidence=missing,
        required_followups=followups,
        recommendation_mode=recommendation_mode(portfolio, gate, profile),
        recommendation_title=recommendation_title(portfolio, gate),
        explanation=build_score_explanation(
            profile,
            ScoreNarrative(
                value=value,
                feasibility=feasibility,
                residual_risk=risk,
                evidence_confidence=evidence_confidence,
                gate_result=gate,
            ),
            blocking,
        ),
    )


def unknown_penalty(profile: EvidenceProfile) -> int:
    missing_systems = max(profile.system_count - profile.clear_system_count, 0)
    missing_artifacts = max(profile.artifact_count - profile.structured_artifact_count, 0)
    return min((missing_systems + missing_artifacts) * 10, 30)


def missing_evidence(
    profile: EvidenceProfile,
    metrics: GateMetrics,
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
    if profile.risk.unresolved_exceptions:
        missing.append("Exception handling with corroborated source references")
    if profile.risk.unresolved_risk_constraints:
        missing.append("Controls for inherent workflow risks")
    if not profile.risk.authority_boundary_confirmed:
        missing.append("Confirmed human approval and authority boundary")
    if profile.risk.open_contradictions > 0:
        missing.append("Open contradiction resolution")
    if not profile.has_source_refs:
        missing.append("Source references")
    if metrics.feasibility < 60:
        missing.append("Implementation feasibility evidence")
    if metrics.evidence_confidence < 0.75:
        missing.append("Confirmed evidence coverage")
    return tuple(unique_strings(missing))


def required_followups(
    profile: EvidenceProfile,
    missing: tuple[str, ...],
) -> tuple[str, ...]:
    followups = [f"Collect evidence for: {item}" for item in missing[:4]]
    if profile.risk.residual_risk >= 3:
        followups.append("Clarify human approval and authority boundary")
    if profile.metric_count == 0:
        followups.append("Capture rough frequency, volume, and rework estimates")
    return tuple(unique_strings(followups))


def gate_result(profile: EvidenceProfile, metrics: GateMetrics) -> str:
    if metrics.residual_risk >= 4 and (
        metrics.evidence_confidence < 0.8 or profile.risk.open_contradictions > 0
    ):
        return "BLOCKED"
    if (
        metrics.feasibility >= 70
        and metrics.evidence_confidence >= 0.75
        and metrics.residual_risk <= 2
        and ready_requirements_met(profile)
    ):
        return "READY_FOR_DESIGN"
    if (
        metrics.feasibility >= 50
        and metrics.evidence_confidence >= 0.6
        and metrics.residual_risk <= 3
    ):
        return "ENABLE_FIRST"
    return "DISCOVERY_NEEDED"


def ready_requirements_met(profile: EvidenceProfile) -> bool:
    return (
        profile.structured_artifact_count > 0
        and profile.clear_system_count > 0
        and profile.rule_count > 0
        and profile.exception_count > 0
        and not profile.risk.unresolved_exceptions
        and not profile.risk.unresolved_risk_constraints
        and profile.risk.authority_boundary_confirmed
        and profile.has_source_refs
        and profile.risk.open_contradictions == 0
        and not profile.open_material_gaps
    )


def portfolio_class(snapshot: ScoreSnapshot) -> str:
    metrics = snapshot.metrics
    if snapshot.gate_result == "BLOCKED":
        return "DO_NOT_AUTOMATE" if metrics.residual_risk >= 4 else "NO_BUILD"
    if metrics.residual_risk >= 3:
        return "HUMAN_CONTROLLED"
    if (
        snapshot.gate_result == "DISCOVERY_NEEDED"
        or metrics.feasibility < 70
        or metrics.evidence_confidence < 0.75
    ):
        return "ENABLE_FIRST"
    if snapshot.value >= 75:
        return "STRATEGIC_BET"
    return "QUICK_WIN"


def blocked_reasons(profile: EvidenceProfile, metrics: GateMetrics) -> tuple[str, ...]:
    reasons: list[str] = []
    if metrics.feasibility < 70:
        reasons.append("Feasibility evidence is below G1 readiness threshold")
    if metrics.evidence_confidence < 0.75:
        reasons.append("Evidence confidence is below G1 readiness threshold")
    if metrics.residual_risk >= 3:
        reasons.append("Residual risk exceeds the G1 readiness threshold")
    if profile.risk.unresolved_risk_constraints:
        reasons.append("Inherent workflow risks do not have confirmed controls")
    if profile.risk.unresolved_exceptions:
        reasons.append("Exception handling is not corroborated by source evidence")
    if not profile.risk.authority_boundary_confirmed:
        reasons.append("Human approval and final decision authority are not confirmed")
    if profile.risk.open_contradictions > 0:
        reasons.append("Open evidence contradictions must be resolved")
    if profile.exception_count == 0:
        reasons.append("At least one exception case and handling path must be documented")
    if not profile.has_source_refs:
        reasons.append("Source references are required for design readiness")
    return tuple(unique_strings(reasons))


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


def clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def clamp_float(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
