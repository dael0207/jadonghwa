from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import TYPE_CHECKING, LiteralString, cast

from work_discovery_api.domain import AnswerStatus, AuditAction, InterviewStatus
from work_discovery_api.models import (
    AnswerRead,
    AuditEventRead,
    InterviewRead,
    JsonObject,
    ProjectRead,
    QuestionRead,
    WorkModelRead,
)

if TYPE_CHECKING:
    from psycopg import Connection
    from psycopg.rows import DictRow

Row = Mapping[str, object]


def one(conn: Connection[DictRow], sql: LiteralString, params: tuple[object, ...]) -> Row:
    row = conn.execute(sql, params).fetchone()
    if row is None:
        message = "database row not found"
        raise KeyError(message)
    return cast("Row", row)


def project_from_row(row: Row) -> ProjectRead:
    return ProjectRead(
        id=str(row["id"]),
        name=str(row["name"]),
        workspace_id=str(row["workspace_id"]),
        workspace_name=str(row["workspace_name"]),
        created_at=cast("datetime", row["created_at"]),
    )


def interview_from_row(row: Row) -> InterviewRead:
    return InterviewRead(
        id=str(row["id"]),
        project_id=str(row["project_id"]),
        status=InterviewStatus(str(row["status"])),
        active_consent=bool(row["active_consent"]),
        answered_count=int_value(row["answered_count"]),
        created_at=cast("datetime", row["created_at"]),
    )


def question_from_row(row: Row) -> QuestionRead:
    return QuestionRead(
        id=str(row["id"]),
        stage=str(row["stage"]),
        dimension=str(row["dimension"]),
        text=str(row["question_text"]),
        required=bool(row["required"]),
        position=int_value(row["position"]),
    )


def answer_from_row(row: Row) -> AnswerRead:
    return AnswerRead(
        id=str(row["id"]),
        turn_id=str(row["turn_id"]),
        question_id=str(row["question_id"]),
        text=str(row["answer_text"]),
        status=AnswerStatus(str(row["answer_status"])),
        revision_of=str(row["revision_of"]) if row["revision_of"] is not None else None,
        source_refs=source_refs_from(row["source_refs"]),
        created_at=cast("datetime", row["created_at"]),
    )


def work_model_from_row(row: Row) -> WorkModelRead:
    return WorkModelRead(
        project_id=str(row["project_id"]),
        version=int_value(row["version"]),
        payload=cast("JsonObject", row["payload"]),
        schema_valid=bool(row["schema_valid"]),
        created_at=cast("datetime", row["created_at"]),
    )


def audit_from_row(row: Row) -> AuditEventRead:
    return AuditEventRead(
        id=str(row["id"]),
        subject_id=str(row["subject_id"]),
        action=AuditAction(str(row["action"])),
        metadata=cast("JsonObject", row["metadata"]),
        created_at=cast("datetime", row["created_at"]),
    )


def source_refs_from(value: object) -> tuple[str, ...]:
    if isinstance(value, list | tuple):
        return tuple(str(item) for item in value)
    return ()


def int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    message = f"expected integer-like value, got {type(value).__name__}"
    raise TypeError(message)
