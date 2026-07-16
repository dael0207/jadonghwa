from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal, assert_never

from work_discovery_api.models import JsonObject, JsonValue

type ConstraintKind = Literal[
    "SAFETY_POLICY",
    "INHERENT_RISK",
    "AUTHORITY_BOUNDARY",
    "OPERATIONAL",
]

TRUSTED_STATES: Final = frozenset({"CORROBORATED", "CONFIRMED"})
INHERENT_RISK_CATEGORIES: Final = frozenset(
    {"PRIVACY", "SECURITY", "LEGAL", "FINANCIAL", "SAFETY", "QUALITY"},
)
AUTHORITY_CATEGORIES: Final = frozenset({"AUTHORITY", "ORGANIZATIONAL"})
LEGACY_SAFETY_POLICY_IDS: Final = frozenset({"constraint-no-external-execution"})


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    safety_policy_constraints: tuple[str, ...]
    inherent_risk_constraints: tuple[str, ...]
    unresolved_risk_constraints: tuple[str, ...]
    controlled_risk_constraints: tuple[str, ...]
    unresolved_exceptions: tuple[str, ...]
    controlled_exceptions: tuple[str, ...]
    authority_boundary_confirmed: bool
    authority_controls: tuple[str, ...]
    unresolved_authority_boundaries: tuple[str, ...]
    open_contradictions: int
    residual_risk: int


@dataclass(frozen=True, slots=True)
class ConstraintFindings:
    safety_policies: tuple[str, ...]
    inherent: tuple[str, ...]
    controlled_risks: tuple[str, ...]
    unresolved_risks: tuple[str, ...]
    authority_controls: tuple[str, ...]
    unresolved_authority: tuple[str, ...]
    controlled_levels: tuple[int, ...]


def assess_constraints(payload: JsonObject) -> ConstraintFindings:
    safety_policies: list[str] = []
    inherent: list[str] = []
    controlled_risks: list[str] = []
    unresolved_risks: list[str] = []
    authority_controls: list[str] = []
    unresolved_authority: list[str] = []
    controlled_levels: list[int] = []

    for constraint in object_list(payload.get("constraints")):
        label = constraint_label(constraint)
        kind = constraint_kind(constraint)
        match kind:
            case "SAFETY_POLICY":
                safety_policies.append(label)
            case "INHERENT_RISK":
                inherent.append(label)
                if constraint_is_controlled(constraint):
                    controlled_risks.append(controlled_label(constraint, label))
                    controlled_levels.append(integer_value(constraint.get("residual_level"), 2))
                else:
                    unresolved_risks.append(label)
            case "AUTHORITY_BOUNDARY":
                if constraint_is_controlled(constraint):
                    authority_controls.append(controlled_label(constraint, label))
                    controlled_levels.append(integer_value(constraint.get("residual_level"), 1))
                else:
                    unresolved_authority.append(label)
            case "OPERATIONAL":
                continue
            case unreachable:
                assert_never(unreachable)

    return ConstraintFindings(
        safety_policies=tuple(safety_policies),
        inherent=tuple(inherent),
        controlled_risks=tuple(controlled_risks),
        unresolved_risks=tuple(unresolved_risks),
        authority_controls=tuple(authority_controls),
        unresolved_authority=tuple(unresolved_authority),
        controlled_levels=tuple(controlled_levels),
    )


def assess_exceptions(payload: JsonObject) -> tuple[tuple[str, ...], tuple[str, ...]]:
    controlled: list[str] = []
    unresolved: list[str] = []
    for exception in object_list(payload.get("exceptions")):
        label = exception_label(exception)
        if exception_is_controlled(exception):
            controlled.append(label)
        else:
            unresolved.append(label)
    return tuple(controlled), tuple(unresolved)


def assess_risk(payload: JsonObject, open_contradictions: int) -> RiskAssessment:
    constraints = assess_constraints(payload)
    controlled_exceptions, unresolved_exceptions = assess_exceptions(payload)

    authority_confirmed = bool(constraints.authority_controls) and not (
        constraints.unresolved_authority
    )
    residual = residual_risk(
        unresolved_count=(
            int(bool(constraints.unresolved_risks))
            + int(bool(unresolved_exceptions))
            + int(bool(constraints.unresolved_authority))
        ),
        authority_confirmed=authority_confirmed,
        open_contradictions=open_contradictions,
        controlled_levels=constraints.controlled_levels,
    )
    return RiskAssessment(
        safety_policy_constraints=constraints.safety_policies,
        inherent_risk_constraints=constraints.inherent,
        unresolved_risk_constraints=constraints.unresolved_risks,
        controlled_risk_constraints=constraints.controlled_risks,
        unresolved_exceptions=unresolved_exceptions,
        controlled_exceptions=controlled_exceptions,
        authority_boundary_confirmed=authority_confirmed,
        authority_controls=constraints.authority_controls,
        unresolved_authority_boundaries=constraints.unresolved_authority,
        open_contradictions=open_contradictions,
        residual_risk=residual,
    )


def constraint_kind(constraint: JsonObject) -> ConstraintKind:
    explicit = string_value(constraint.get("constraint_kind"), "")
    match explicit:
        case "SAFETY_POLICY" | "INHERENT_RISK" | "AUTHORITY_BOUNDARY" | "OPERATIONAL":
            return explicit
        case "":
            pass
        case _:
            return "OPERATIONAL"

    identifier = string_value(constraint.get("id"), "")
    category = string_value(constraint.get("category"), "").upper()
    if identifier in LEGACY_SAFETY_POLICY_IDS:
        return "SAFETY_POLICY"
    if category in AUTHORITY_CATEGORIES:
        return "AUTHORITY_BOUNDARY"
    if category in INHERENT_RISK_CATEGORIES:
        return "INHERENT_RISK"
    return "OPERATIONAL"


def constraint_is_controlled(constraint: JsonObject) -> bool:
    control = string_value(constraint.get("control"), "")
    residual = integer_value(constraint.get("residual_level"), -1)
    return bool(control) and 0 <= residual <= 2 and has_strong_evidence(constraint)


def exception_is_controlled(exception: JsonObject) -> bool:
    condition = string_value(exception.get("condition"), "")
    handling = string_value(exception.get("handling"), "")
    return bool(condition and handling) and has_strong_evidence(exception)


def has_strong_evidence(item: JsonObject) -> bool:
    meta = object_value(item.get("meta"))
    state = string_value(meta.get("state"), "")
    return state in TRUSTED_STATES and bool(string_tuple(meta.get("source_refs")))


def residual_risk(
    *,
    unresolved_count: int,
    authority_confirmed: bool,
    open_contradictions: int,
    controlled_levels: tuple[int, ...],
) -> int:
    if open_contradictions > 0:
        return 4
    if unresolved_count > 0:
        return min(1 + unresolved_count * 2, 4)
    if not authority_confirmed:
        return 3
    return max((1, *controlled_levels))


def constraint_label(constraint: JsonObject) -> str:
    return string_value(
        constraint.get("statement"),
        string_value(constraint.get("id"), "Unlabelled constraint"),
    )


def controlled_label(constraint: JsonObject, label: str) -> str:
    control = string_value(constraint.get("control"), "Control not recorded")
    return f"{label} Control: {control}"


def exception_label(exception: JsonObject) -> str:
    condition = string_value(exception.get("condition"), "Unlabelled exception")
    handling = string_value(exception.get("handling"), "Handling not recorded")
    return f"{condition} Handling: {handling}"


def object_list(value: JsonValue | None) -> tuple[JsonObject, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, dict))


def object_value(value: JsonValue | None) -> JsonObject:
    if isinstance(value, dict):
        return value
    return {}


def string_tuple(value: JsonValue | None) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)


def string_value(value: JsonValue | None, fallback: str) -> str:
    if isinstance(value, str) and value:
        return value
    return fallback


def integer_value(value: JsonValue | None, fallback: int) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return fallback
