from __future__ import annotations

from work_discovery_api.models import JsonObject, JsonValue
from work_discovery_api.work_model_evidence import string_tuple


def evidence_refs_for(opportunity_payload: JsonObject, work_model_payload: JsonObject) -> list[str]:
    refs = [
        *string_tuple(opportunity_payload.get("evidence_refs")),
        *string_tuple(work_model_payload.get("source_refs")),
    ]
    return unique_strings(refs) or ["source-work-model"]


def list_with_default(value: JsonValue | None, fallback: str) -> list[str]:
    values = unique_strings(list(string_tuple(value)))
    return values or [fallback]


def string_value(value: JsonValue | None, fallback: str) -> str:
    if isinstance(value, str) and value:
        return value
    return fallback


def bool_value(value: JsonValue | None, *, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    return fallback


def int_value(value: JsonValue | None, fallback: int) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return max(0, min(4, value))
    if isinstance(value, float):
        return max(0, min(4, round(value)))
    return fallback


def first_or_default(values: list[str], fallback: str) -> str:
    if values:
        return values[0]
    return fallback


def unique_strings(values: list[str] | tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result
