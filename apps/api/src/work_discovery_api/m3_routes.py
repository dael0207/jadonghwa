from __future__ import annotations

from collections.abc import Sequence

from fastapi import FastAPI, HTTPException, status

from work_discovery_api.adaptive_interview import DeterministicAdaptiveQuestionSelector
from work_discovery_api.contracts import ContractPaths, validate_payload
from work_discovery_api.domain import (
    AuditAction,
    ConsentRequiredError,
    InterviewStatus,
    InvalidTransitionError,
)
from work_discovery_api.models import (
    AnswerRead,
    AnswerRevisionCreate,
    CoverageRead,
    EvidenceCreate,
    InterviewRead,
    NextQuestionRead,
    OpportunityDraftRead,
    WorkModelRead,
    utc_now,
)
from work_discovery_api.opportunity_analyzer import (
    DeterministicOpportunityAnalyzer,
    OpportunityAnalysisInput,
)
from work_discovery_api.repository import WorkDiscoveryRepository


def register_m3_routes(
    app: FastAPI,
    app_store: WorkDiscoveryRepository,
    paths: ContractPaths,
    selector: DeterministicAdaptiveQuestionSelector,
    analyzer: DeterministicOpportunityAnalyzer,
) -> None:
    @app.get("/v1/interviews/{interview_id}/answers", response_model=list[AnswerRead])
    def list_answers(interview_id: str) -> Sequence[AnswerRead]:
        try:
            return app_store.list_answers(interview_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.post(
        "/v1/interviews/{interview_id}/evidence",
        response_model=AnswerRead,
        status_code=status.HTTP_201_CREATED,
    )
    def record_evidence(interview_id: str, payload: EvidenceCreate) -> AnswerRead:
        try:
            return app_store.record_evidence(interview_id, payload)
        except ConsentRequiredError as error:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except InvalidTransitionError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @app.post("/v1/interviews/{interview_id}/answers/{answer_id}/revise", response_model=AnswerRead)
    def revise_answer(
        interview_id: str,
        answer_id: str,
        payload: AnswerRevisionCreate,
    ) -> AnswerRead:
        try:
            return app_store.revise_answer(interview_id, answer_id, payload)
        except ConsentRequiredError as error:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except InvalidTransitionError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @app.post("/v1/interviews/{interview_id}/resume-model-building", response_model=InterviewRead)
    def resume_model_building(interview_id: str) -> InterviewRead:
        try:
            interview = app_store.get_interview(interview_id)
            if not interview.active_consent:
                raise ConsentRequiredError(interview_id=interview_id)
            if interview.status != InterviewStatus.NEEDS_EVIDENCE:
                detail = f"interview must be NEEDS_EVIDENCE, got {interview.status}"
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
            resumed = app_store.transition_interview(interview_id, InterviewStatus.MODEL_BUILDING)
            app_store.record_audit(
                interview_id,
                AuditAction.WORK_MODEL_REBUILD_REQUESTED,
                {"project_id": interview.project_id, "interview_id": interview_id},
            )
            return resumed
        except ConsentRequiredError as error:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except InvalidTransitionError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @app.get("/v1/projects/{project_id}/work-models", response_model=list[WorkModelRead])
    def list_work_models(project_id: str) -> Sequence[WorkModelRead]:
        try:
            return app_store.list_work_models(project_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.get("/v1/interviews/{interview_id}/coverage", response_model=CoverageRead)
    def get_coverage(interview_id: str) -> CoverageRead:
        try:
            return selector.coverage(interview_id, app_store.list_answers(interview_id))
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.get("/v1/interviews/{interview_id}/next-question", response_model=NextQuestionRead)
    def get_next_question(interview_id: str) -> NextQuestionRead:
        try:
            return selector.next_question(
                interview_id,
                app_store.get_questions(interview_id),
                app_store.list_answers(interview_id),
            )
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.get(
        "/v1/interviews/{interview_id}/opportunities/draft",
        response_model=OpportunityDraftRead,
    )
    def get_opportunity_draft(interview_id: str) -> OpportunityDraftRead:
        try:
            interview = app_store.get_interview(interview_id)
            if not interview.active_consent:
                raise ConsentRequiredError(interview_id=interview_id)
            model = app_store.get_work_model(interview.project_id)
            if not model.schema_valid:
                detail = "schema-valid Work Model is required before opportunity draft"
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
            payload = analyzer.draft(OpportunityAnalysisInput(work_model=model))
            validation_error = validate_payload(paths.opportunity_schema, payload)
            if validation_error is not None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=validation_error,
                )
            app_store.record_audit(
                interview_id,
                AuditAction.OPPORTUNITY_DRAFT_GENERATED,
                {
                    "project_id": interview.project_id,
                    "interview_id": interview_id,
                    "work_model_version": model.version,
                },
            )
            return OpportunityDraftRead(
                project_id=interview.project_id,
                interview_id=interview_id,
                schema_valid=True,
                payload=payload,
                created_at=utc_now(),
            )
        except ConsentRequiredError as error:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
