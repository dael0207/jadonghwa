from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

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


@dataclass(slots=True)
class InterviewRecord:
    id: str
    project_id: str
    status: InterviewStatus
    active_consent: bool
    created_at: datetime
    answered_questions: set[str] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class AnswerEventInput:
    question_id: str
    text: str
    status: AnswerStatus
    revision_of: str | None
    source_refs: tuple[str, ...]


@dataclass(slots=True)
class MemoryStore:
    projects: dict[str, ProjectRead] = field(default_factory=dict)
    interviews: dict[str, InterviewRecord] = field(default_factory=dict)
    questions: dict[str, tuple[QuestionRead, ...]] = field(default_factory=dict)
    answers: dict[str, list[AnswerRead]] = field(default_factory=dict)
    work_models: dict[str, list[WorkModelRead]] = field(default_factory=dict)
    opportunities: dict[str, list[OpportunityRead]] = field(default_factory=dict)
    design_packages: dict[str, list[DesignPackageRead]] = field(default_factory=dict)
    audit_events: list[AuditEventRead] = field(default_factory=list)

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
        self.record_audit(
            project_id,
            AuditAction.PROJECT_CREATED,
            {"project_id": project_id, "workspace_id": workspace_id},
        )
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
            created_at=utc_now(),
        )
        self.interviews[interview_id] = record
        self.questions[interview_id] = questions
        self.answers[interview_id] = []
        self.record_audit(
            interview_id,
            AuditAction.INTERVIEW_CREATED,
            {"project_id": project_id, "interview_id": interview_id},
        )
        return self.interview_read(record)

    def get_interview(self, interview_id: str) -> InterviewRead:
        return self.interview_read(self.require_interview(interview_id))

    def list_project_interviews(self, project_id: str) -> tuple[InterviewRead, ...]:
        self.require_project(project_id)
        records = [
            record
            for record in self.interviews.values()
            if record.project_id == project_id
        ]
        return tuple(
            self.interview_read(record)
            for record in sorted(records, key=lambda item: item.created_at)
        )

    def grant_consent(self, interview_id: str, consent: ConsentRequest) -> InterviewRead:
        record = self.require_interview(interview_id)
        if not consent.ai_processing or not consent.data_processing:
            record.status = transition(record.status, InterviewStatus.ABORTED)
            self.record_audit(
                interview_id,
                AuditAction.CONSENT_REVOKED,
                {
                    "project_id": record.project_id,
                    "interview_id": interview_id,
                    "reason": "declined",
                },
            )
            return self.interview_read(record)
        record.status = transition(record.status, InterviewStatus.CONSENTED)
        record.status = transition(record.status, InterviewStatus.INTAKE_IN_PROGRESS)
        record.active_consent = True
        self.record_audit(
            interview_id,
            AuditAction.CONSENT_GRANTED,
            {
                "project_id": record.project_id,
                "interview_id": interview_id,
                "audio_recording": consent.audio_recording,
            },
        )
        return self.interview_read(record)

    def revoke_consent(self, interview_id: str) -> InterviewRead:
        record = self.require_interview(interview_id)
        record.status = transition(record.status, InterviewStatus.CONSENT_REVOKED)
        record.active_consent = False
        self.record_audit(
            interview_id,
            AuditAction.CONSENT_REVOKED,
            {"project_id": record.project_id, "interview_id": interview_id},
        )
        return self.interview_read(record)

    def get_questions(self, interview_id: str) -> tuple[QuestionRead, ...]:
        self.require_interview(interview_id)
        return self.questions[interview_id]

    def record_answer(self, interview_id: str, answer: AnswerCreate) -> AnswerRead:
        record = self.require_interview(interview_id)
        if not can_accept_answer(record.status, record.active_consent):
            raise ConsentRequiredError(interview_id=interview_id)
        self.require_question(interview_id, answer.question_id)
        answer_read = self.append_answer(
            interview_id,
            AnswerEventInput(
                question_id=answer.question_id,
                text=answer.text,
                status=answer.status,
                revision_of=answer.revision_of,
                source_refs=(),
            ),
        )
        if answer.status in {AnswerStatus.ANSWERED, AnswerStatus.UNKNOWN, AnswerStatus.SKIPPED}:
            record.answered_questions.add(answer.question_id)
        if len(record.answered_questions) >= len(self.questions[interview_id]):
            record.status = transition(record.status, InterviewStatus.MODEL_BUILDING)
        self.record_audit(
            interview_id,
            AuditAction.ANSWER_RECORDED,
            {
                "project_id": record.project_id,
                "interview_id": interview_id,
                "question_id": answer.question_id,
                "answer_id": answer_read.id,
            },
        )
        return answer_read

    def record_evidence(self, interview_id: str, evidence: EvidenceCreate) -> AnswerRead:
        record = self.require_interview(interview_id)
        if not record.active_consent:
            raise ConsentRequiredError(interview_id=interview_id)
        if not can_accept_evidence(record.status, record.active_consent):
            transition(record.status, InterviewStatus.NEEDS_EVIDENCE)
        question_id = evidence.question_id or self.questions[interview_id][0].id
        self.require_question(interview_id, question_id)
        answer_read = self.append_answer(
            interview_id,
            AnswerEventInput(
                question_id=question_id,
                text=evidence.text,
                status=AnswerStatus.ANSWERED,
                revision_of=None,
                source_refs=("evidence",),
            ),
        )
        self.record_audit(
            interview_id,
            AuditAction.EVIDENCE_ADDED,
            {
                "project_id": record.project_id,
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
        record = self.require_interview(interview_id)
        if not record.active_consent:
            raise ConsentRequiredError(interview_id=interview_id)
        if not can_accept_evidence(record.status, record.active_consent):
            transition(record.status, InterviewStatus.NEEDS_EVIDENCE)
        original = self.require_answer(interview_id, answer_id)
        answer_read = self.append_answer(
            interview_id,
            AnswerEventInput(
                question_id=original.question_id,
                text=revision.text,
                status=revision.status,
                revision_of=answer_id,
                source_refs=(f"revision:{answer_id}",),
            ),
        )
        self.record_audit(
            interview_id,
            AuditAction.ANSWER_REVISED,
            {
                "project_id": record.project_id,
                "interview_id": interview_id,
                "question_id": original.question_id,
                "answer_id": answer_read.id,
                "revision_of": answer_id,
            },
        )
        return answer_read

    def list_answers(self, interview_id: str) -> tuple[AnswerRead, ...]:
        self.require_interview(interview_id)
        return tuple(self.answers[interview_id])

    def get_work_model(self, project_id: str) -> WorkModelRead:
        self.require_project(project_id)
        existing = self.work_models.get(project_id)
        if existing:
            return existing[-1]
        return WorkModelRead(
            project_id=project_id,
            version=1,
            payload={"version": "work-model-v1", "process": {}, "steps": []},
            schema_valid=False,
            created_at=utc_now(),
        )

    def get_work_model_version(self, project_id: str, version: int) -> WorkModelRead:
        self.require_project(project_id)
        for model in self.work_models.get(project_id, ()):
            if model.version == version:
                return model
        message = f"work model {project_id} version {version} not found"
        raise KeyError(message)

    def get_interview_work_model(self, interview_id: str) -> WorkModelRead:
        record = self.require_interview(interview_id)
        return self.get_work_model(record.project_id)

    def list_work_models(self, project_id: str) -> tuple[WorkModelRead, ...]:
        self.require_project(project_id)
        return tuple(self.work_models.get(project_id, ()))

    def replace_work_model(
        self,
        project_id: str,
        payload: JsonObject,
        valid: bool,
    ) -> WorkModelRead:
        self.require_project(project_id)
        previous = self.work_models.get(project_id, [])
        model = WorkModelRead(
            project_id=project_id,
            version=len(previous) + 1,
            payload=payload,
            schema_valid=valid,
            created_at=utc_now(),
        )
        self.work_models.setdefault(project_id, []).append(model)
        self.record_audit(
            project_id,
            AuditAction.WORK_MODEL_VALIDATED,
            {"project_id": project_id, "valid": valid},
        )
        return model

    def save_opportunity(
        self,
        project_id: str,
        work_model_version: int,
        payload: JsonObject,
        valid: bool,
    ) -> OpportunityRead:
        self.require_project(project_id)
        opportunity = OpportunityRead(
            id=str(uuid4()),
            project_id=project_id,
            work_model_version=work_model_version,
            payload=payload,
            schema_valid=valid,
            created_at=utc_now(),
        )
        self.opportunities.setdefault(project_id, []).append(opportunity)
        return opportunity

    def get_opportunity(self, opportunity_id: str) -> OpportunityRead:
        for opportunities in self.opportunities.values():
            for opportunity in opportunities:
                if opportunity.id == opportunity_id:
                    return opportunity
        message = f"opportunity {opportunity_id} not found"
        raise KeyError(message)

    def list_opportunities(self, project_id: str) -> tuple[OpportunityRead, ...]:
        self.require_project(project_id)
        return tuple(self.opportunities.get(project_id, ()))

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
        package = DesignPackageRead(
            id=str(uuid4()),
            project_id=project_id,
            opportunity_id=opportunity_id,
            work_model_version=work_model_version,
            payload=payload,
            schema_valid=valid,
            created_at=utc_now(),
        )
        self.design_packages.setdefault(project_id, []).append(package)
        return package

    def get_design_package(self, package_id: str) -> DesignPackageRead:
        for packages in self.design_packages.values():
            for package in packages:
                if package.id == package_id:
                    return package
        message = f"design package {package_id} not found"
        raise KeyError(message)

    def list_project_design_packages(self, project_id: str) -> tuple[DesignPackageRead, ...]:
        self.require_project(project_id)
        return tuple(self.design_packages.get(project_id, ()))

    def list_opportunity_design_packages(
        self,
        opportunity_id: str,
    ) -> tuple[DesignPackageRead, ...]:
        opportunity = self.get_opportunity(opportunity_id)
        return tuple(
            package
            for package in self.design_packages.get(opportunity.project_id, ())
            if package.opportunity_id == opportunity_id
        )

    def transition_interview(
        self,
        interview_id: str,
        target: InterviewStatus,
    ) -> InterviewRead:
        record = self.require_interview(interview_id)
        record.status = transition(record.status, target)
        return self.interview_read(record)

    def record_audit(
        self,
        subject_id: str,
        action: AuditAction,
        metadata: JsonObject,
    ) -> AuditEventRead:
        event = AuditEventRead(
            id=str(uuid4()),
            subject_id=subject_id,
            action=action,
            metadata=metadata,
            created_at=utc_now(),
        )
        self.audit_events.append(event)
        return event

    def list_interview_audit_events(self, interview_id: str) -> tuple[AuditEventRead, ...]:
        self.require_interview(interview_id)
        return tuple(
            event
            for event in self.audit_events
            if event.subject_id == interview_id
            or event.metadata.get("interview_id") == interview_id
        )

    def list_project_audit_events(self, project_id: str) -> tuple[AuditEventRead, ...]:
        self.require_project(project_id)
        return tuple(
            event
            for event in self.audit_events
            if event.subject_id == project_id or event.metadata.get("project_id") == project_id
        )

    def append_answer(
        self,
        interview_id: str,
        answer: AnswerEventInput,
    ) -> AnswerRead:
        turn_id = str(uuid4())
        answer_read = AnswerRead(
            id=str(uuid4()),
            turn_id=turn_id,
            question_id=answer.question_id,
            text=answer.text,
            status=answer.status,
            revision_of=answer.revision_of,
            source_refs=(f"turn:{turn_id}", *answer.source_refs),
            created_at=utc_now(),
        )
        self.answers[interview_id].append(answer_read)
        return answer_read

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

    def require_answer(self, interview_id: str, answer_id: str) -> AnswerRead:
        for answer in self.answers[interview_id]:
            if answer.id == answer_id:
                return answer
        message = f"answer {answer_id} not found"
        raise KeyError(message)

    def interview_read(self, record: InterviewRecord) -> InterviewRead:
        return InterviewRead(
            id=record.id,
            project_id=record.project_id,
            status=record.status,
            active_consent=record.active_consent,
            answered_count=len(record.answered_questions),
            created_at=record.created_at,
        )
