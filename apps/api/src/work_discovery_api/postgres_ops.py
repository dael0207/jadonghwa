from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from work_discovery_api import postgres_sql as sql
from work_discovery_api.domain import AnswerStatus, AuditAction, InterviewStatus, transition
from work_discovery_api.models import (
    AnswerRead,
    AuditEventRead,
    InterviewRead,
    JsonObject,
    QuestionRead,
)
from work_discovery_api.postgres_rows import (
    answer_from_row,
    audit_from_row,
    int_value,
    interview_from_row,
    one,
)

if TYPE_CHECKING:
    from psycopg import Connection
    from psycopg.rows import DictRow


@dataclass(frozen=True, slots=True)
class DbAnswerEvent:
    question_id: str
    text: str
    status: AnswerStatus
    revision_of: str | None
    event_type: str
    source_refs: tuple[str, ...]


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


def insert_answer_event(
    conn: Connection[DictRow],
    interview_id: str,
    event: DbAnswerEvent,
) -> AnswerRead:
    turn_id = uuid4()
    answer_id = uuid4()
    sequence = int_value(one(conn, sql.NEXT_TURN, (UUID(interview_id),))["next_sequence"])
    conn.execute(
        sql.INSERT_TURN,
        (turn_id, UUID(interview_id), sequence, event.event_type),
    )
    conn.execute(
        sql.INSERT_ANSWER,
        (
            answer_id,
            turn_id,
            event.question_id,
            event.text,
            event.status.value,
            UUID(event.revision_of) if event.revision_of else None,
            Jsonb([f"turn:{turn_id}", *event.source_refs]),
        ),
    )
    return answer_from_row(one(conn, sql.ANSWER, (answer_id,)))


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
