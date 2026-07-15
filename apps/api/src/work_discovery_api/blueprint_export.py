from __future__ import annotations

from work_discovery_api.models import BlueprintRead, JsonObject, JsonValue
from work_discovery_api.work_model_evidence import object_list, object_value, string_tuple


def blueprint_json_export(blueprint: BlueprintRead) -> JsonObject:
    return blueprint.payload


def blueprint_markdown_export(blueprint: BlueprintRead) -> str:
    payload = blueprint.payload
    lines = [
        f"# G1 Solution Blueprint: {text(payload, 'blueprint_id')}",
        "",
        f"- Project: `{text(payload, 'project_id')}`",
        f"- Design package: `{text(payload, 'design_package_id')}`",
        f"- Type: `{text(payload, 'blueprint_type')}`",
        f"- Export ready: `{str(payload.get('export_ready')).lower()}`",
        "",
    ]
    add_section(lines, "Executive Brief", object_value(payload.get("executive_brief")))
    add_as_is_to_be(lines, object_value(payload.get("as_is_to_be")))
    add_prd(lines, object_value(payload.get("prd")))
    add_json_list(lines, "UX Spec", object_value(payload.get("ux_spec")))
    add_json_list(lines, "Data Spec", object_value(payload.get("data_spec")))
    add_json_list(lines, "API Spec", object_value(payload.get("api_spec")))
    add_acceptance(lines, object_list(payload.get("acceptance_tests")))
    add_backlog(lines, object_list(payload.get("implementation_backlog")))
    add_risks(lines, object_list(payload.get("risks_and_controls")))
    add_quality_gate(lines, object_value(payload.get("quality_gate")))
    add_simple_list(lines, "Open Questions", string_tuple(payload.get("open_questions")))
    add_simple_list(lines, "Non-goals", string_tuple(payload.get("non_goals")))
    return "\n".join(lines).strip() + "\n"


def add_section(lines: list[str], title: str, section: JsonObject) -> None:
    lines.extend([f"## {title}", "", value_as_text(section.get("summary"))])
    lines.extend(f"- {item}" for item in string_tuple(section.get("bullets")))
    add_evidence(lines, section)


def add_as_is_to_be(lines: list[str], section: JsonObject) -> None:
    lines.extend(["", "## AS-IS / TO-BE", ""])
    for label, key in (("AS-IS", "as_is"), ("TO-BE", "to_be"), ("Human", "retained_human_steps")):
        lines.append(f"### {label}")
        add_simple_items(lines, as_strings(section.get(key)))
    add_evidence(lines, section)


def add_prd(lines: list[str], prd: JsonObject) -> None:
    lines.extend(["", "## PRD", "", value_as_text(prd.get("purpose"))])
    for label, key in (
        ("Users", "users"),
        ("Scope", "scope"),
        ("Non-goals", "non_goals"),
        ("Functional Requirements", "functional_requirements"),
        ("Non-functional Requirements", "non_functional_requirements"),
        ("Success Metrics", "success_metrics"),
    ):
        lines.append(f"### {label}")
        add_simple_items(lines, as_strings(prd.get(key)))


def add_json_list(lines: list[str], title: str, section: JsonObject) -> None:
    lines.extend(["", f"## {title}", ""])
    for key, value in section.items():
        lines.append(f"### {key.replace('_', ' ').title()}")
        add_simple_items(lines, value_to_lines(value))


def add_acceptance(lines: list[str], tests: tuple[JsonObject, ...]) -> None:
    lines.extend(["", "## Acceptance Tests", ""])
    for test in tests:
        lines.extend(
            [
                f"### {value_as_text(test.get('scenario'))}",
                f"- Given: {value_as_text(test.get('given'))}",
                f"- When: {value_as_text(test.get('when'))}",
                f"- Then: {value_as_text(test.get('then'))}",
            ],
        )


def add_backlog(lines: list[str], items: tuple[JsonObject, ...]) -> None:
    lines.extend(["", "## Implementation Backlog", ""])
    for item in items:
        priority = value_as_text(item.get("priority"))
        title = value_as_text(item.get("title"))
        description = value_as_text(item.get("description"))
        lines.append(f"- [{priority}] {title}: {description}")


def add_risks(lines: list[str], risks: tuple[JsonObject, ...]) -> None:
    lines.extend(["", "## Risks And Controls", ""])
    for risk in risks:
        lines.append(f"- Risk: {value_as_text(risk.get('risk'))}")
        lines.append(f"  Control: {value_as_text(risk.get('control'))}")


def add_quality_gate(lines: list[str], gate: JsonObject) -> None:
    lines.extend(["", "## Quality Gate", "", f"Passed: `{str(gate.get('passed')).lower()}`"])
    lines.extend(
        f"- {value_as_text(item.get('key'))}: {value_as_text(item.get('detail'))}"
        for item in object_list(gate.get("criteria"))
    )
    blockers = as_strings(gate.get("blocking_items"))
    if blockers:
        lines.append("### Blocking Items")
        add_simple_items(lines, blockers)


def add_simple_list(lines: list[str], title: str, items: tuple[str, ...]) -> None:
    lines.extend(["", f"## {title}", ""])
    add_simple_items(lines, items)


def add_simple_items(lines: list[str], items: tuple[str, ...] | list[str]) -> None:
    if not items:
        lines.append("- None")
        return
    lines.extend(f"- {item}" for item in items)


def add_evidence(lines: list[str], section: JsonObject) -> None:
    refs = string_tuple(section.get("evidence_refs"))
    if refs:
        lines.append("")
        lines.append(f"Evidence: {', '.join(refs)}")
    lines.append("")


def text(payload: JsonObject, key: str) -> str:
    return value_as_text(payload.get(key))


def value_as_text(value: JsonValue | None) -> str:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    return "N/A"


def as_strings(value: JsonValue | None) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(value_as_text(item) for item in value)
    return ()


def value_to_lines(value: JsonValue | None) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(
            value_as_text(item) if not isinstance(item, dict) else dict_summary(item)
            for item in value
        )
    if isinstance(value, dict):
        return tuple(f"{key}: {value_as_text(child)}" for key, child in value.items())
    return (value_as_text(value),)


def dict_summary(value: JsonObject) -> str:
    name = value_as_text(value.get("name"))
    purpose = value_as_text(value.get("purpose"))
    if name != "N/A":
        return name
    return purpose
