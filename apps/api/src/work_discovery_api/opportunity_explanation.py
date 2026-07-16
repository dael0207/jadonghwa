from __future__ import annotations

from dataclasses import dataclass

from work_discovery_api.work_model_evidence import EvidenceProfile


@dataclass(frozen=True, slots=True)
class ScoreNarrative:
    value: int
    feasibility: int
    residual_risk: int
    evidence_confidence: float
    gate_result: str


def build_score_explanation(
    profile: EvidenceProfile,
    narrative: ScoreNarrative,
    blockers: tuple[str, ...],
) -> tuple[str, ...]:
    return (
        f"Value {narrative.value}: steps={profile.step_count}, "
        f"manual_steps={profile.manual_step_count}, "
        f"pain_points={profile.pain_count}, metrics={profile.metric_count}.",
        f"Feasibility {narrative.feasibility}: "
        f"structured_artifacts={profile.structured_artifact_count}, "
        f"clear_systems={profile.clear_system_count}, rules={profile.rule_count}.",
        f"Evidence confidence {round(narrative.evidence_confidence, 2)}: source_link_rate="
        f"{profile.source_link_rate}, confirmed_claim_rate={profile.confirmed_claim_rate}, "
        f"open_gaps={len(profile.open_material_gaps)}.",
        f"Inherent risks: {len(profile.risk.inherent_risk_constraints)}.",
        f"Controlled risks: {len(profile.risk.controlled_risk_constraints)}.",
        f"Unresolved risks: {len(profile.risk.unresolved_risk_constraints)}.",
        f"Controlled exceptions: {len(profile.risk.controlled_exceptions)}.",
        f"Unresolved exceptions: {len(profile.risk.unresolved_exceptions)}.",
        f"Authority boundary confirmed: {profile.risk.authority_boundary_confirmed}.",
        f"Open contradictions: {profile.risk.open_contradictions}.",
        f"Residual risk {narrative.residual_risk}: "
        "safety policies are excluded from workflow risk.",
        f"Final gate reason: {final_gate_reason(narrative.gate_result, blockers)}",
    )


def final_gate_reason(gate_result: str, blockers: tuple[str, ...]) -> str:
    if gate_result == "READY_FOR_DESIGN":
        return "all readiness evidence and residual-risk thresholds are satisfied."
    if blockers:
        return "; ".join(blockers)
    return "score thresholds require further discovery or enablement."
