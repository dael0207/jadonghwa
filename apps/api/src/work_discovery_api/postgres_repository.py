from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import psycopg
from psycopg import Connection
from psycopg.rows import DictRow, dict_row
from psycopg.types.json import Jsonb

from work_discovery_api import postgres_sql as sql
from work_discovery_api.domain import (
    AnswerStatus,
    AuditAction,
    ConsentRequiredError,
    InterviewStatus,
    can_accept_answer,
    can_accept_evidence,
    transition,
)
from work_discovery_api.models import (
    AnswerCreate,
    AnswerRead,
    AnswerRevisionCreate,
    AuditEventRead,
    ConsentRequest,
    DesignPackageRead,
    EvidenceCreate,
    InterviewRead,
    JsonObject,
    OpportunityRead,
    ProjectRead,
    QuestionRead,
    WorkModelRead,
    utc_now,
)
from work_discovery_api.postgres_ops import (
    DbAnswerEvent,
    decline_consent,
    insert_answer_event,
    insert_audit,
    seed_questions,
    status_after_answer,
)
from work_discovery_api.postgres_rows import (
    answer_from_row,
    audit_from_row,
    design_package_from_row,
    int_value,
    interview_from_row,
    one,
    opportunity_from_row,
    project_from_row,
    question_from_row,
    work_model_from_row,
)


@dataclass(slots=True)
class PostgresRepository:
    database_url: str

    def create_project(self, name: str, workspace_name: str) -> ProjectRead:
        project_id = uuid4()
        workspace_id = uuid4()
        with self._connect() as conn:
            conn.execute(sql.INSERT_WORKSPACE, (workspace_id, workspace_name))
            conn.execute(sql.INSERT_PROJECT, (project_id, workspace_id, name))
            insert_audit(
                conn,
                str(project_id),
                AuditAction.PROJECT_CREATED,
                {"project_id": str(project_id), "workspace_id": str(workspace_id)},
            )
            return project_from_row(one(conn, sql.PROJECT, (project_id,)))

    def create_interview(
        self,
        project_id: str,
        questions: tuple[QuestionRead, ...],
    ) -> InterviewRead:
        self.require_project(project_id)
        interview_id = uuid4()
        status = transition(InterviewStatus.CREATED, InterviewStatus.CONSENT_PENDING)
        with self._connect() as conn:
            seed_questions(conn, questions)
            conn.execute(
                sql.INSERT_INTERVIEW,
                (interview_id, UUID(project_id), status.value),
            )
            insert_audit(
                conn,
                str(interview_id),
                AuditAction.INTERVIEW_CREATED,
                {"project_id": project_id, "interview_id": str(interview_id)},
            )
            return interview_from_row(one(conn, sql.INTERVIEW, (interview_id,)))

    def require_project(self, project_id: str) -> ProjectRead:
        with self._connect() as conn:
            return project_from_row(one(conn, sql.PROJECT, (UUID(project_id),)))

    def get_interview(self, interview_id: str) -> InterviewRead:
        with self._connect() as conn:
            return interview_from_row(one(conn, sql.INTERVIEW, (UUID(interview_id),)))

    def list_project_interviews(self, project_id: str) -> tuple[InterviewRead, ...]:
        self.require_project(project_id)
        with self._connect() as conn:
            rows = conn.execute(sql.PROJECT_INTERVIEWS, (UUID(project_id),)).fetchall()
            return tuple(interview_from_row(row) for row in rows)

    def grant_consent(self, interview_id: str, consent: ConsentRequest) -> InterviewRead:
        current = self.get_interview(interview_id)
        with self._connect() as conn:
            if not consent.ai_processing or not consent.data_processing:
                return decline_consent(conn, current, interview_id)
            conn.execute(
                sql.INSERT_CONSENT,
                (
                    uuid4(),
                    UUID(interview_id),
                    consent.ai_processing,
                    consent.data_processing,
                    consent.audio_recording,
                    consent.retention_days,
                ),
            )
            status = transition(current.status, InterviewStatus.CONSENTED)
            status = transition(status, InterviewStatus.INTAKE_IN_PROGRESS)
            conn.execute(sql.UPDATE_INTERVIEW_CONSENTED, (status.value, UUID(interview_id)))
            insert_audit(
                conn,
                interview_id,
                AuditAction.CONSENT_GRANTED,
                {
                    "project_id": current.project_id,
                    "interview_id": interview_id,
                    "audio_recording": consent.audio_recording,
                },
            )
            return interview_from_row(one(conn, sql.INTERVIEW, (UUID(interview_id),)))

    def revoke_consent(self, interview_id: str) -> InterviewRead:
        current = self.get_interview(interview_id)
        status = transition(current.status, InterviewStatus.CONSENT_REVOKED)
        with self._connect() as conn:
            conn.execute(sql.REVOKE_CONSENT, (UUID(interview_id),))
            conn.execute(sql.UPDATE_INTERVIEW_CONSENT_REVOKED, (status.value, UUID(interview_id)))
            insert_audit(
                conn,
                interview_id,
                AuditAction.CONSENT_REVOKED,
                {"project_id": current.project_id, "interview_id": interview_id},
            )
            return interview_from_row(one(conn, sql.INTERVIEW, (UUID(interview_id),)))

    def get_questions(self, interview_id: str) -> tuple[QuestionRead, ...]:
        self.get_interview(interview_id)
        with self._connect() as conn:
            rows = conn.execute(sql.QUESTIONS).fetchall()
            return tuple(question_from_row(row) for row in rows)

    def record_answer(self, interview_id: str, answer: AnswerCreate) -> AnswerRead:
        current = self.get_interview(interview_id)
        if not can_accept_answer(current.status, current.active_consent):
            raise ConsentRequiredError(interview_id=interview_id)
        with self._connect() as conn:
            one(conn, "SELECT id FROM questions WHERE id=%s", (answer.question_id,))
            answer_read = insert_answer_event(
                conn,
                interview_id,
                DbAnswerEvent(
                    question_id=answer.question_id,
                    text=answer.text,
                    status=answer.status,
                    revision_of=answer.revision_of,
                    event_type="ANSWER",
                    source_refs=(),
                ),
            )
            status = status_after_answer(conn, current, interview_id)
            conn.execute(
                "UPDATE interview_sessions SET status=%s, updated_at=now() WHERE id=%s",
                (status.value, UUID(interview_id)),
            )
            insert_audit(
                conn,
                interview_id,
                AuditAction.ANSWER_RECORDED,
                {
                    "project_id": current.project_id,
                    "interview_id": interview_id,
                    "question_id": answer.question_id,
                    "answer_id": answer_read.id,
                },
            )
            return answer_read

    def record_evidence(self, interview_id: str, evidence: EvidenceCreate) -> AnswerRead:
        current = self.get_interview(interview_id)
        if not current.active_consent:
            raise ConsentRequiredError(interview_id=interview_id)
        if not can_accept_evidence(current.status, current.active_consent):
            transition(current.status, InterviewStatus.NEEDS_EVIDENCE)
        with self._connect() as conn:
            question_id = evidence.question_id or str(one(conn, sql.FIRST_QUESTION_ID, ())["id"])
            one(conn, "SELECT id FROM questions WHERE id=%s", (question_id,))
            answer_read = insert_answer_event(
                conn,
                interview_id,
                DbAnswerEvent(
                    question_id=question_id,
                    text=evidence.text,
                    status=AnswerStatus.ANSWERED,
                    revision_of=None,
                    event_type="EVIDENCE",
                    source_refs=("evidence",),
                ),
            )
            insert_audit(
                conn,
                interview_id,
                AuditAction.EVIDENCE_ADDED,
                {
                    "project_id": current.project_id,
                    "interview_id": interview_id,
                    "question_id": question_id,
                    "answer_id": answer_read.id,
                },
            )
            return answer_read

    def revise_answer(
        self,
        interview_id: str,
        answer_id: str,
        revision: AnswerRevisionCreate,
    ) -> AnswerRead:
        current = self.get_interview(interview_id)
        if not current.active_consent:
            raise ConsentRequiredError(interview_id=interview_id)
        if not can_accept_evidence(current.status, current.active_consent):
            transition(current.status, InterviewStatus.NEEDS_EVIDENCE)
        with self._connect() as conn:
            original = answer_from_row(
                one(conn, sql.ANSWER_IN_INTERVIEW, (UUID(answer_id), UUID(interview_id))),
            )
            answer_read = insert_answer_event(
                conn,
                interview_id,
                DbAnswerEvent(
                    question_id=original.question_id,
                    text=revision.text,
                    status=revision.status,
                    revision_of=answer_id,
                    event_type="REVISION",
                    source_refs=(f"revision:{answer_id}",),
                ),
            )
            insert_audit(
                conn,
                interview_id,
                AuditAction.ANSWER_REVISED,
                {
                    "project_id": current.project_id,
                    "interview_id": interview_id,
                    "question_id": original.question_id,
                    "answer_id": answer_read.id,
                    "revision_of": answer_id,
                },
            )
            return answer_read

    def list_answers(self, interview_id: str) -> tuple[AnswerRead, ...]:
        self.get_interview(interview_id)
        with self._connect() as conn:
            rows = conn.execute(sql.ANSWERS, (UUID(interview_id),)).fetchall()
            return tuple(answer_from_row(row) for row in rows)

    def get_work_model(self, project_id: str) -> WorkModelRead:
        self.require_project(project_id)
        with self._connect() as conn:
            row = conn.execute(sql.WORK_MODEL, (UUID(project_id),)).fetchone()
            if row is None:
                return WorkModelRead(
                    project_id=project_id,
                    version=1,
                    payload={"version": "work-model-v1", "process": {}, "steps": []},
                    schema_valid=False,
                    created_at=utc_now(),
                )
            return work_model_from_row(row)

    def get_work_model_version(self, project_id: str, version: int) -> WorkModelRead:
        self.require_project(project_id)
        with self._connect() as conn:
            return work_model_from_row(
                one(conn, sql.WORK_MODEL_BY_VERSION, (UUID(project_id), version)),
            )

    def get_interview_work_model(self, interview_id: str) -> WorkModelRead:
        return self.get_work_model(self.get_interview(interview_id).project_id)

    def list_work_models(self, project_id: str) -> tuple[WorkModelRead, ...]:
        self.require_project(project_id)
        with self._connect() as conn:
            rows = conn.execute(sql.WORK_MODELS, (UUID(project_id),)).fetchall()
            return tuple(work_model_from_row(row) for row in rows)

    def replace_work_model(
        self,
        project_id: str,
        payload: JsonObject,
        valid: bool,
    ) -> WorkModelRead:
        self.require_project(project_id)
        with self._connect() as conn:
            version = int_value(one(conn, sql.NEXT_MODEL_VERSION, (UUID(project_id),))["version"])
            model_id = uuid4()
            conn.execute(
                sql.INSERT_WORK_MODEL,
                (model_id, UUID(project_id), version, Jsonb(payload), valid),
            )
            insert_audit(
                conn,
                project_id,
                AuditAction.WORK_MODEL_VALIDATED,
                {"project_id": project_id, "valid": valid},
            )
            return work_model_from_row(one(conn, sql.WORK_MODEL_BY_ID, (model_id,)))

    def save_opportunity(
        self,
        project_id: str,
        work_model_version: int,
        payload: JsonObject,
        valid: bool,
    ) -> OpportunityRead:
        self.require_project(project_id)
        opportunity_id = uuid4()
        with self._connect() as conn:
            conn.execute(
                sql.INSERT_OPPORTUNITY,
                (
                    opportunity_id,
                    UUID(project_id),
                    work_model_version,
                    Jsonb(payload),
                    valid,
                ),
            )
            return opportunity_from_row(one(conn, sql.OPPORTUNITY, (opportunity_id,)))

    def get_opportunity(self, opportunity_id: str) -> OpportunityRead:
        with self._connect() as conn:
            return opportunity_from_row(one(conn, sql.OPPORTUNITY, (UUID(opportunity_id),)))

    def list_opportunities(self, project_id: str) -> tuple[OpportunityRead, ...]:
        self.require_project(project_id)
        with self._connect() as conn:
            rows = conn.execute(sql.OPPORTUNITIES_BY_PROJECT, (UUID(project_id),)).fetchall()
            return tuple(opportunity_from_row(row) for row in rows)

    def save_design_package(
        self,
        project_id: str,
        opportunity_id: str,
        work_model_version: int,
        payload: JsonObject,
        valid: bool,
    ) -> DesignPackageRead:
        self.require_project(project_id)
        self.get_opportunity(opportunity_id)
        package_id = uuid4()
        with self._connect() as conn:
            conn.execute(
                sql.INSERT_DESIGN_PACKAGE,
                (
                    package_id,
                    UUID(project_id),
                    UUID(opportunity_id),
                    work_model_version,
                    Jsonb(payload),
                    valid,
                ),
            )
            return design_package_from_row(one(conn, sql.DESIGN_PACKAGE, (package_id,)))

    def get_design_package(self, package_id: str) -> DesignPackageRead:
        with self._connect() as conn:
            return design_package_from_row(one(conn, sql.DESIGN_PACKAGE, (UUID(package_id),)))

    def list_project_design_packages(self, project_id: str) -> tuple[DesignPackageRead, ...]:
        self.require_project(project_id)
        with self._connect() as conn:
            rows = conn.execute(sql.DESIGN_PACKAGES_BY_PROJECT, (UUID(project_id),)).fetchall()
            return tuple(design_package_from_row(row) for row in rows)

    def list_opportunity_design_packages(
        self,
        opportunity_id: str,
    ) -> tuple[DesignPackageRead, ...]:
        self.get_opportunity(opportunity_id)
        with self._connect() as conn:
            rows = conn.execute(
                sql.DESIGN_PACKAGES_BY_OPPORTUNITY,
                (UUID(opportunity_id),),
            ).fetchall()
            return tuple(design_package_from_row(row) for row in rows)

    def transition_interview(self, interview_id: str, target: InterviewStatus) -> InterviewRead:
        current = self.get_interview(interview_id)
        status = transition(current.status, target)
        with self._connect() as conn:
            conn.execute(sql.UPDATE_INTERVIEW_STATUS, (status.value, UUID(interview_id)))
            return interview_from_row(one(conn, sql.INTERVIEW, (UUID(interview_id),)))

    def record_audit(
        self,
        subject_id: str,
        action: AuditAction,
        metadata: JsonObject,
    ) -> AuditEventRead:
        with self._connect() as conn:
            return insert_audit(conn, subject_id, action, metadata)

    def list_interview_audit_events(self, interview_id: str) -> tuple[AuditEventRead, ...]:
        self.get_interview(interview_id)
        with self._connect() as conn:
            rows = conn.execute(sql.INTERVIEW_AUDIT, (UUID(interview_id), interview_id)).fetchall()
            return tuple(audit_from_row(row) for row in rows)

    def list_project_audit_events(self, project_id: str) -> tuple[AuditEventRead, ...]:
        self.require_project(project_id)
        with self._connect() as conn:
            rows = conn.execute(sql.PROJECT_AUDIT, (UUID(project_id), project_id)).fetchall()
            return tuple(audit_from_row(row) for row in rows)

    def _connect(self) -> Connection[DictRow]:
        return psycopg.Connection[DictRow].connect(self.database_url, row_factory=dict_row)
