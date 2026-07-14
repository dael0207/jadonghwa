from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from work_discovery_api import postgres_sql as sql
from work_discovery_api.domain import AuditAction, InterviewStatus, transition
from work_discovery_api.models import AuditEventRead, InterviewRead, JsonObject, QuestionRead
from work_discovery_api.postgres_rows import audit_from_row, int_value, interview_from_row, one

if TYPE_CHECKING:
    from psycopg import Connection
    from psycopg.rows import DictRow


def decline_consent(
    conn: Connection[DictRow],
    current: InterviewRead,
    interview_id: str,
) -> InterviewRead:
    status = transition(current.status, InterviewStatus.ABORTED)
    conn.execute(sql.UPDATE_INTERVIEW_STATUS, (status.value, UUID(interview_id)))
    insert_audit(
        conn,
        interview_id,
        AuditAction.CONSENT_REVOKED,
        {"project_id": current.project_id, "interview_id": interview_id, "reason": "declined"},
    )
    return interview_from_row(one(conn, sql.INTERVIEW, (UUID(interview_id),)))


def seed_questions(conn: Connection[DictRow], questions: tuple[QuestionRead, ...]) -> None:
    for question in questions:
        conn.execute(
            sql.UPSERT_QUESTION,
            (
                question.id,
                question.stage,
                question.dimension,
                question.text,
                question.position,
                question.required,
            ),
        )


def insert_audit(
    conn: Connection[DictRow],
    subject_id: str,
    action: AuditAction,
    metadata: JsonObject,
) -> AuditEventRead:
    row = one(
        conn,
        sql.INSERT_AUDIT,
        (uuid4(), UUID(subject_id), action.value, Jsonb(metadata)),
    )
    return audit_from_row(row)


def status_after_answer(
    conn: Connection[DictRow],
    current: InterviewRead,
    interview_id: str,
) -> InterviewStatus:
    answered = int_value(one(conn, sql.ANSWERED_COUNT, (UUID(interview_id),))["answered"])
    total = int_value(one(conn, sql.TOTAL_QUESTIONS, ())["total"])
    if answered >= total:
        return transition(current.status, InterviewStatus.MODEL_BUILDING)
    return current.status
