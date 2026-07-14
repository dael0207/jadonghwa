from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from work_discovery_api.domain import (
    AnswerStatus,
    AuditAction,
    ConsentRequiredError,
    InterviewStatus,
    can_accept_answer,
    transition,
)
from work_discovery_api.models import (
    AnswerCreate,
    AnswerRead,
    ConsentRequest,
    InterviewRead,
    JsonObject,
    ProjectRead,
    QuestionRead,
    WorkModelRead,
    utc_now,
)


@dataclass(slots=True)
class InterviewRecord:
    id: str
    project_id: str
    status: InterviewStatus
    active_consent: bool
    answered_questions: set[str] = field(default_factory=set)


@dataclass(slots=True)
class MemoryStore:
    projects: dict[str, ProjectRead] = field(default_factory=dict)
    interviews: dict[str, InterviewRecord] = field(default_factory=dict)
    questions: dict[str, tuple[QuestionRead, ...]] = field(default_factory=dict)
    answers: dict[str, list[AnswerRead]] = field(default_factory=dict)
    work_models: dict[str, WorkModelRead] = field(default_factory=dict)
    audit_events: list[tuple[str, AuditAction]] = field(default_factory=list)

    def create_project(self, name: str, workspace_name: str) -> ProjectRead:
        project_id = str(uuid4())
        workspace_id = str(uuid4())
        project = ProjectRead(
            id=project_id,
            name=name,
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            created_at=utc_now(),
        )
        self.projects[project_id] = project
        self.audit_events.append((project_id, AuditAction.PROJECT_CREATED))
        return project

    def create_interview(
        self,
        project_id: str,
        questions: tuple[QuestionRead, ...],
    ) -> InterviewRead:
        self.require_project(project_id)
        interview_id = str(uuid4())
        record = InterviewRecord(
            id=interview_id,
            project_id=project_id,
            status=transition(InterviewStatus.CREATED, InterviewStatus.CONSENT_PENDING),
            active_consent=False,
        )
        self.interviews[interview_id] = record
        self.questions[interview_id] = questions
        self.answers[interview_id] = []
        self.audit_events.append((interview_id, AuditAction.INTERVIEW_CREATED))
        return self.interview_read(record)

    def grant_consent(self, interview_id: str, consent: ConsentRequest) -> InterviewRead:
        record = self.require_interview(interview_id)
        if not consent.ai_processing or not consent.data_processing:
            record.status = transition(record.status, InterviewStatus.ABORTED)
            return self.interview_read(record)
        record.status = transition(record.status, InterviewStatus.CONSENTED)
        record.status = transition(record.status, InterviewStatus.INTAKE_IN_PROGRESS)
        record.active_consent = True
        self.audit_events.append((interview_id, AuditAction.CONSENT_GRANTED))
        return self.interview_read(record)

    def revoke_consent(self, interview_id: str) -> InterviewRead:
        record = self.require_interview(interview_id)
        record.status = transition(record.status, InterviewStatus.CONSENT_REVOKED)
        record.active_consent = False
        self.audit_events.append((interview_id, AuditAction.CONSENT_REVOKED))
        return self.interview_read(record)

    def record_answer(self, interview_id: str, answer: AnswerCreate) -> AnswerRead:
        record = self.require_interview(interview_id)
        if not can_accept_answer(record.status, record.active_consent):
            raise ConsentRequiredError(interview_id=interview_id)
        self.require_question(interview_id, answer.question_id)
        turn_id = str(uuid4())
        answer_id = str(uuid4())
        created = utc_now()
        answer_read = AnswerRead(
            id=answer_id,
            turn_id=turn_id,
            question_id=answer.question_id,
            text=answer.text,
            status=answer.status,
            revision_of=answer.revision_of,
            source_refs=(f"turn:{turn_id}",),
            created_at=created,
        )
        self.answers[interview_id].append(answer_read)
        if answer.status in {AnswerStatus.ANSWERED, AnswerStatus.UNKNOWN, AnswerStatus.SKIPPED}:
            record.answered_questions.add(answer.question_id)
        if len(record.answered_questions) >= len(self.questions[interview_id]):
            record.status = transition(record.status, InterviewStatus.MODEL_BUILDING)
        self.audit_events.append((interview_id, AuditAction.ANSWER_RECORDED))
        return answer_read

    def get_work_model(self, project_id: str) -> WorkModelRead:
        self.require_project(project_id)
        existing = self.work_models.get(project_id)
        if existing is not None:
            return existing
        model = WorkModelRead(
            project_id=project_id,
            version=1,
            payload={"version": "work-model-v1", "process": {}, "steps": []},
            schema_valid=False,
            created_at=utc_now(),
        )
        self.work_models[project_id] = model
        return model

    def replace_work_model(
        self,
        project_id: str,
        payload: JsonObject,
        valid: bool,
    ) -> WorkModelRead:
        self.require_project(project_id)
        model = WorkModelRead(
            project_id=project_id,
            version=self.get_work_model(project_id).version + 1,
            payload=payload,
            schema_valid=valid,
            created_at=utc_now(),
        )
        self.work_models[project_id] = model
        self.audit_events.append((project_id, AuditAction.WORK_MODEL_VALIDATED))
        return model

    def require_project(self, project_id: str) -> ProjectRead:
        project = self.projects.get(project_id)
        if project is None:
            message = f"project {project_id} not found"
            raise KeyError(message)
        return project

    def require_interview(self, interview_id: str) -> InterviewRecord:
        record = self.interviews.get(interview_id)
        if record is None:
            message = f"interview {interview_id} not found"
            raise KeyError(message)
        return record

    def require_question(self, interview_id: str, question_id: str) -> QuestionRead:
        for question in self.questions[interview_id]:
            if question.id == question_id:
                return question
        message = f"question {question_id} not found"
        raise KeyError(message)

    def interview_read(self, record: InterviewRecord) -> InterviewRead:
        return InterviewRead(
            id=record.id,
            project_id=record.project_id,
            status=record.status,
            active_consent=record.active_consent,
            answered_count=len(record.answered_questions),
            created_at=utc_now(),
        )
