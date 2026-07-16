from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from work_discovery_api.models import JsonObject, utc_now
from work_discovery_api.opportunity_scoring import ScoreDecision
from work_discovery_api.work_model_evidence import EvidenceProfile


def build_opportunity_payload(profile: EvidenceProfile, decision: ScoreDecision) -> JsonObject:
    seed = f"{profile.model_id}:{profile.work_model_version}"
    opportunity_id = f"opp-{uuid5(NAMESPACE_URL, seed)}"
    return {
        "opportunity_id": opportunity_id,
        "project_id": profile.project_id,
        "work_model_id": profile.model_id,
        "target_refs": [profile.process_id],
        "problem_statement": problem_statement(profile),
        "recommendation": {
            "solution_mode": decision.recommendation_mode,
            "title": decision.recommendation_title,
            "rationale": recommendation_rationale(profile, decision),
            "scope": recommendation_scope(decision),
            "autonomy_level": autonomy_level(decision),
        },
        "alternative_options": alternative_options(decision),
        "scores": {
            "value": decision.value,
            "feasibility": decision.feasibility,
            "risk": decision.risk,
            "evidence_confidence": decision.evidence_confidence,
            "oversight": decision.oversight,
            "portfolio_class": decision.portfolio_class,
            "score_explanation": list(decision.explanation),
        },
        "gate": {
            "result": decision.gate_result,
            "blocked_reasons": list(decision.blocked_reasons),
        },
        "risk_profile": build_risk_profile(profile),
        "human_role": {
            "retained_responsibilities": human_responsibilities(decision),
            "approval_points": approval_points(decision),
            "exception_handling": exception_handling(profile, decision),
            "override_available": True,
        },
        "benefit_estimate": benefit_estimate(profile, decision),
        "risks": risks(profile, decision),
        "prerequisites": prerequisites(decision),
        "evidence_refs": list(profile.evidence_refs),
        "open_questions": open_questions(decision),
        "validation_experiment": validation_experiment(decision),
        "mvp_scope": mvp_scope(decision),
        "non_goals": [
            "Real LLM scoring",
            "STT or voice recording",
            "External system execution",
            "Credential collection",
            "G1 specification generation",
        ],
        "created_at": utc_now().isoformat(),
    }


def problem_statement(profile: EvidenceProfile) -> str:
    return (
        f"{profile.title} has {profile.step_count} captured steps, "
        f"{profile.manual_step_count} manual touch points, and {profile.pain_count} pain points. "
        f"Evidence summary: {profile.summary[:1200]}"
    )


def recommendation_rationale(profile: EvidenceProfile, decision: ScoreDecision) -> str:
    return (
        f"Value={decision.value}, feasibility={decision.feasibility}, risk={decision.risk}, "
        f"evidence_confidence={decision.evidence_confidence}. "
        f"The recommendation keeps human oversight at level {decision.oversight} "
        f"using {len(profile.evidence_refs)} evidence refs because "
        f"{len(decision.blocked_reasons)} readiness blockers remain."
    )


def recommendation_scope(decision: ScoreDecision) -> list[str]:
    if decision.gate_result == "READY_FOR_DESIGN":
        return ["G1 design package planning", "Human approval points", "Pilot validation plan"]
    if decision.gate_result == "ENABLE_FIRST":
        return ["Input/output standardization", "Rules and exception mapping", "Evidence capture"]
    if decision.gate_result == "BLOCKED":
        return ["Manual control", "Risk clarification", "No automation build"]
    return ["Discovery follow-up", "Evidence gap closure", "Playback refinement"]


def autonomy_level(decision: ScoreDecision) -> int:
    if decision.gate_result == "READY_FOR_DESIGN":
        return 2 if decision.risk <= 2 else 1
    if decision.gate_result == "ENABLE_FIRST":
        return 1
    return 0


def alternative_options(decision: ScoreDecision) -> list[JsonObject]:
    options: list[JsonObject] = [
        {
            "solution_mode": "SIMPLIFY_STANDARDIZE",
            "title": "Standardize the work before automation",
            "rationale": (
                "Reduce ambiguity in inputs, outputs, rules, and exception handling first."
            ),
            "scope": ["Checklist", "Template", "Owner review"],
            "autonomy_level": 0,
        },
    ]
    if decision.gate_result != "BLOCKED":
        options.append(
            {
                "solution_mode": "KNOWLEDGE_ASSIST",
                "title": "Assistive work guide",
                "rationale": "Provide recommendations while keeping execution in human hands.",
                "scope": ["Draft guidance", "Evidence reminders", "Human approval"],
                "autonomy_level": 1,
            },
        )
    return options[:3]


def human_responsibilities(decision: ScoreDecision) -> list[str]:
    responsibilities = [
        "Confirm source evidence",
        "Approve any action that affects external systems",
    ]
    if decision.risk >= 3:
        responsibilities.append("Keep final decision authority with the user")
    return responsibilities


def approval_points(decision: ScoreDecision) -> list[str]:
    points = ["Before G1 design starts", "Before any pilot uses real business data"]
    if decision.oversight >= 3:
        points.append("Before recommendations are applied to production work")
    return points


def exception_handling(profile: EvidenceProfile, decision: ScoreDecision) -> list[str]:
    if profile.risk.controlled_exceptions and not profile.risk.unresolved_exceptions:
        return list(profile.risk.controlled_exceptions)
    if profile.exception_count > 0:
        return ["Route unresolved exceptions to manual review"]
    if decision.gate_result == "READY_FOR_DESIGN":
        return ["Escalate unrecognized cases to a human reviewer"]
    return ["Collect missing exception cases before design readiness"]


def benefit_estimate(profile: EvidenceProfile, decision: ScoreDecision) -> JsonObject:
    typical_manual = float(max(profile.manual_step_count, 1) * max(profile.process_count, 1) * 12)
    recoverable = round(typical_manual * (decision.value / 100) * 0.45, 1)
    return {
        "basis": "USER_ESTIMATE" if profile.metric_count > 0 else "UNKNOWN",
        "annual_manual_hours": {
            "min": round(typical_manual * 0.5, 1),
            "max": round(typical_manual * 1.5, 1),
            "typical": typical_manual,
        },
        "annual_rework_hours": {
            "min": 0,
            "max": round(max(profile.pain_severity_total, 1) * 6, 1),
            "typical": round(max(profile.pain_severity_total, 1) * 3, 1),
        },
        "recoverable_hours": {
            "min": 0,
            "max": round(recoverable * 1.5, 1),
            "typical": recoverable,
        },
        "annual_total_benefit": {"currency": "KRW", "min": 0, "max": 0, "typical": 0},
        "build_cost": {"currency": "KRW", "min": 0, "max": 0, "typical": 0},
        "annual_run_cost": {"currency": "KRW", "min": 0, "max": 0, "typical": 0},
        "assumptions": [
            "M4 does not estimate money from real measurements.",
            "Hours are deterministic placeholders derived from captured work structure.",
        ],
    }


def risks(profile: EvidenceProfile, decision: ScoreDecision) -> list[JsonObject]:
    items: list[JsonObject] = [
        {
            "category": "OPERATIONS",
            "level": decision.risk,
            "description": "Residual workflow uncertainty after documented controls.",
            "control": "Require playback confirmation and readiness review before G1 design.",
            "residual_level": decision.risk,
        },
    ]
    if profile.risk.inherent_risk_constraints:
        items.append(
            {
                "category": "OTHER",
                "level": min(decision.risk, 4),
                "description": "; ".join(profile.risk.inherent_risk_constraints)[:2000],
                "control": risk_control_summary(profile),
                "residual_level": decision.risk,
            },
        )
    return items


def build_risk_profile(profile: EvidenceProfile) -> JsonObject:
    assessment = profile.risk
    return {
        "safety_policy_constraints": list(assessment.safety_policy_constraints),
        "inherent_risk_constraints": list(assessment.inherent_risk_constraints),
        "unresolved_risk_constraints": list(assessment.unresolved_risk_constraints),
        "controlled_risk_constraints": list(assessment.controlled_risk_constraints),
        "unresolved_exceptions": list(assessment.unresolved_exceptions),
        "controlled_exceptions": list(assessment.controlled_exceptions),
        "authority_boundary_confirmed": assessment.authority_boundary_confirmed,
        "authority_controls": list(assessment.authority_controls),
        "open_contradictions": assessment.open_contradictions,
        "residual_risk": assessment.residual_risk,
    }


def risk_control_summary(profile: EvidenceProfile) -> str:
    controls = [
        *profile.risk.controlled_risk_constraints,
        *profile.risk.authority_controls,
    ]
    if controls:
        return "; ".join(controls)[:2000]
    return "No confirmed control is recorded; keep the workflow human-controlled."


def prerequisites(decision: ScoreDecision) -> list[str]:
    items = ["Schema-valid Work Model", "Active consent", "Human-readable playback evidence"]
    if decision.gate_result != "READY_FOR_DESIGN":
        items.extend(decision.missing_evidence)
    return items


def open_questions(decision: ScoreDecision) -> list[str]:
    if decision.required_followups:
        return list(decision.required_followups)
    return ["Which approval point should remain mandatory in a future pilot?"]


def validation_experiment(decision: ScoreDecision) -> JsonObject:
    return {
        "hypothesis": "The scored opportunity reflects the confirmed work model evidence.",
        "method": "Review score explanations, blockers, and evidence references with the user.",
        "sample": "Latest schema-valid Work Model for one project.",
        "success_criteria": [
            f"Gate result is accepted as {decision.gate_result}.",
            "Blocking reasons and follow-ups are either resolved or explicitly deferred.",
        ],
    }


def mvp_scope(decision: ScoreDecision) -> list[str]:
    if decision.gate_result == "READY_FOR_DESIGN":
        return ["Prepare for G1 design package inputs without generating G1 yet"]
    return ["Resolve readiness blockers before G1 design work"]
