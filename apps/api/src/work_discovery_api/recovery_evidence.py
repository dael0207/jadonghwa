from __future__ import annotations

import re
from dataclasses import dataclass

from work_discovery_api.models import AnswerRead, JsonObject

LABELS: dict[str, tuple[str, ...]] = {
    "systems": ("시스템/도구", "시스템", "도구"),
    "inputs": ("입력",),
    "outputs": ("출력",),
    "rules": ("규칙/판단 기준", "판단 기준", "규칙"),
    "exceptions": ("예외/복구", "예외", "복구"),
    "authority": ("승인/권한", "승인", "권한"),
    "metrics": ("성과지표", "지표"),
    "non_goals": ("비범위",),
    "evidence": ("근거",),
}


@dataclass(frozen=True, slots=True)
class RecoveryFacts:
    values: dict[str, tuple[str, ...]]
    source_refs: tuple[str, ...]

    @property
    def present(self) -> bool:
        return bool(self.values)

    @property
    def coverage(self) -> float:
        return len(self.values) / len(LABELS)


def parse_recovery_evidence(answers: tuple[AnswerRead, ...]) -> RecoveryFacts:
    collected: dict[str, list[str]] = {}
    refs: list[str] = []
    for answer in answers:
        if "evidence" not in answer.source_refs:
            continue
        parsed = parse_labelled_text(answer.text)
        if not parsed:
            continue
        refs.append(answer.id)
        for key, values in parsed.items():
            collected.setdefault(key, []).extend(values)
    return RecoveryFacts(
        values={key: tuple(unique(values)) for key, values in collected.items()},
        source_refs=tuple(unique(refs)),
    )


def parse_labelled_text(text: str) -> dict[str, tuple[str, ...]]:
    parsed: dict[str, tuple[str, ...]] = {}
    for raw_line in text.splitlines():
        label, separator, value = raw_line.partition(":")
        if not separator:
            label, separator, value = raw_line.partition("\uff1a")
        if not separator or not value.strip():
            continue
        key = canonical_key(label.strip())
        if key is None:
            continue
        parsed[key] = tuple(split_items(value))
    return parsed


def build_structured_artifacts(facts: RecoveryFacts, meta: JsonObject) -> list[JsonObject]:
    artifacts: list[JsonObject] = []
    for direction, key, kind in (("IN", "inputs", "INPUT"), ("OUT", "outputs", "OUTPUT")):
        for index, name in enumerate(facts.values.get(key, ()), start=1):
            artifacts.append(
                {
                    "id": f"artifact-recovery-{key}-{index:02d}",
                    "kind": kind,
                    "name": name[:300],
                    "direction": direction,
                    "format": artifact_format(name),
                    "data_fields": [],
                    "data_classification": "UNKNOWN",
                    "retention": "프로젝트 보존 정책에 따름",
                    "meta": meta,
                },
            )
    return artifacts


def build_systems(facts: RecoveryFacts, meta: JsonObject) -> list[JsonObject]:
    systems: list[JsonObject] = []
    for index, name in enumerate(facts.values.get("systems", ()), start=1):
        kind, access = system_contract(name)
        systems.append(
            {
                "id": f"system-recovery-{index:02d}",
                "name": name[:200],
                "kind": kind,
                "access_method": access,
                "stability": "STABLE",
                "permission_notes": authority_note(facts),
                "meta": meta,
            },
        )
    return systems


def build_rules(facts: RecoveryFacts, meta: JsonObject) -> list[JsonObject]:
    return [
        {
            "id": f"rule-recovery-{index:02d}",
            "statement": statement[:2000],
            "rule_type": "THRESHOLD" if contains_number(statement) else "HEURISTIC",
            "owner_refs": ["role-user"],
            "effective_from": None,
            "meta": meta,
        }
        for index, statement in enumerate(facts.values.get("rules", ()), start=1)
    ]


def build_decisions(facts: RecoveryFacts, meta: JsonObject) -> list[JsonObject]:
    rules = facts.values.get("rules", ())
    if not rules:
        return []
    return [
        {
            "id": "decision-recovery-01",
            "question": "제시된 규칙과 예외를 기준으로 처리 결과를 확정할 수 있는가?",
            "input_refs": ["artifact-interview-notes"],
            "rule_refs": [f"rule-recovery-{index:02d}" for index in range(1, len(rules) + 1)],
            "decision_owner_refs": ["role-user"],
            "outcomes": ["정상 처리", "사람 확인 필요"],
            "escalation_condition": authority_note(facts),
            "meta": meta,
        },
    ]


def build_exceptions(facts: RecoveryFacts, meta: JsonObject) -> list[JsonObject]:
    exceptions: list[JsonObject] = []
    for index, statement in enumerate(facts.values.get("exceptions", ()), start=1):
        condition, handling = exception_contract(statement)
        exceptions.append(
            {
                "id": f"exception-recovery-{index:02d}",
                "condition": condition[:1000],
                "handling": handling[:2000],
                "impact": "MEDIUM",
                "meta": meta,
            },
        )
    return exceptions


def build_metrics(facts: RecoveryFacts, meta: JsonObject) -> list[JsonObject]:
    metrics: list[JsonObject] = []
    for index, statement in enumerate(facts.values.get("metrics", ()), start=1):
        number = first_number(statement)
        metrics.append(
            {
                "id": f"metric-recovery-{index:02d}",
                "name": statement[:200],
                "unit": "reported",
                "value": {"min": number, "max": number, "typical": number},
                "scope": "PER_MONTH" if "월" in statement else "OTHER",
                "measurement_method": "사용자가 제공한 복구 증거에서 확인",
                "meta": meta,
            },
        )
    return metrics


def build_authority_constraints(facts: RecoveryFacts, meta: JsonObject) -> list[JsonObject]:
    return [
        {
            "id": f"constraint-recovery-authority-{index:02d}",
            "category": "AUTHORITY",
            "constraint_kind": "AUTHORITY_BOUNDARY",
            "statement": statement[:2000],
            "hard": True,
            "control": "명시된 승인자와 업무 담당자가 최종 판단 및 예외 처리를 유지한다.",
            "residual_level": 1,
            "meta": meta,
        }
        for index, statement in enumerate(facts.values.get("authority", ()), start=1)
    ]


def exception_contract(statement: str) -> tuple[str, str]:
    for separator in ("이면", "일 때", "인 경우", "는 "):
        condition, marker, handling = statement.partition(separator)
        if marker and condition.strip() and handling.strip():
            return condition.strip(), handling.strip()
    return statement.strip(), statement.strip()


def canonical_key(label: str) -> str | None:
    normalized = label.replace(" ", "")
    for key, aliases in LABELS.items():
        if any(normalized == alias.replace(" ", "") for alias in aliases):
            return key
    return None


def split_items(value: str) -> list[str]:
    items = [item.strip() for item in re.split(r"[,;\uff0c]", value) if item.strip()]
    return items or [value.strip()]


def artifact_format(name: str) -> str:
    lowered = name.lower()
    formats = (
        ("csv", "CSV"),
        ("excel", "XLSX"),
        ("엑셀", "XLSX"),
        ("ppt", "PPTX"),
        ("pdf", "PDF"),
    )
    for marker, format_name in formats:
        if marker in lowered:
            return format_name
    return "STRUCTURED"


def system_contract(name: str) -> tuple[str, str]:
    lowered = name.lower()
    if "excel" in lowered or "엑셀" in lowered:
        return "SPREADSHEET", "FILE_IMPORT_EXPORT"
    if "mail" in lowered or "메일" in lowered:
        return "EMAIL", "EMAIL"
    if "powerpoint" in lowered or "ppt" in lowered:
        return "DESKTOP", "MANUAL_UI"
    return "WEB", "MANUAL_UI"


def authority_note(facts: RecoveryFacts) -> str:
    values = facts.values.get("authority", ())
    if values:
        return " / ".join(values)[:1000]
    return "실제 자격증명은 수집하지 않으며 사람의 승인 경계를 유지한다."


def contains_number(value: str) -> bool:
    return re.search(r"\d", value) is not None


def first_number(value: str) -> float:
    match = re.search(r"\d+(?:\.\d+)?", value)
    return float(match.group()) if match else 1.0


def unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))
