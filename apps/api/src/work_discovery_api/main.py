from __future__ import annotations

from collections.abc import Sequence

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware

from work_discovery_api.adaptive_interview import DeterministicAdaptiveQuestionSelector
from work_discovery_api.blueprint_builder import DeterministicBlueprintBuilder
from work_discovery_api.contracts import default_contract_paths, initial_questions, validate_payload
from work_discovery_api.design_package_builder import DeterministicDesignPackageBuilder
from work_discovery_api.discovery_routes import register_discovery_routes
from work_discovery_api.domain import (
    AuditAction,
    ConsentRequiredError,
    InterviewStatus,
    InvalidTransitionError,
)
from work_discovery_api.evaluation_runner import DeterministicEvaluationRunner
from work_discovery_api.implementation_package_builder import (
    DeterministicImplementationPackageBuilder,
)
from work_discovery_api.m3_routes import register_m3_routes
from work_discovery_api.m4_routes import register_m4_routes
from work_discovery_api.m5_routes import register_m5_routes
from work_discovery_api.m6_routes import register_m6_routes
from work_discovery_api.m7_routes import register_m7_routes
from work_discovery_api.m8_routes import register_m8_routes
from work_discovery_api.m9_routes import register_m9_routes
from work_discovery_api.models import (
    AnswerCreate,
    AnswerRead,
    AuditEventRead,
    ConsentRequest,
    InterviewRead,
    JsonObject,
    ProjectCreate,
    ProjectRead,
    QuestionRead,
    ValidationRead,
    WorkModelRead,
    WorkModelValidateRequest,
    utc_now,
)
from work_discovery_api.opportunity_analyzer import DeterministicOpportunityAnalyzer
from work_discovery_api.release_readiness import DeterministicReleaseReadinessEvaluator
from work_discovery_api.repository import WorkDiscoveryRepository
from work_discovery_api.repository_factory import create_repository
from work_discovery_api.work_model_builder import (
    DeterministicWorkModelBuilder,
    InsufficientAnswersError,
    WorkModelBuildInput,
)


def create_app(store: WorkDiscoveryRepository | None = None) -> FastAPI:
    app_store = store or create_repository()
    builder = DeterministicWorkModelBuilder()
    selector = DeterministicAdaptiveQuestionSelector()
    analyzer = DeterministicOpportunityAnalyzer()
    design_builder = DeterministicDesignPackageBuilder()
    blueprint_builder = DeterministicBlueprintBuilder()
    evaluation_runner = DeterministicEvaluationRunner()
    release_evaluator = DeterministicReleaseReadinessEvaluator()
    implementation_builder = DeterministicImplementationPackageBuilder()
    app = FastAPI(
        title="Work Discovery AI API",
        version="0.9.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    paths = default_contract_paths()

    def questions_for_interview() -> tuple[QuestionRead, ...]:
        questions = []
        for position, raw in enumerate(initial_questions(paths), start=1):
            questions.append(
                QuestionRead(
                    id=str(raw.get("id", f"Q-M0-{position:03d}")),
                    stage=str(raw.get("stage", "INTAKE")),
                    dimension=str(raw.get("dimension", "GENERAL")),
                    text=str(raw.get("text", "")),
                    required=bool(raw.get("critical", position <= 10)),
                    position=position,
                ),
            )
        return tuple(questions)

    @app.post("/v1/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
    def create_project(payload: ProjectCreate) -> ProjectRead:
        return app_store.create_project(payload.name, payload.workspace_name)

    @app.get("/v1/projects/{project_id}", response_model=ProjectRead)
    def get_project(project_id: str) -> ProjectRead:
        try:
            return app_store.require_project(project_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.post(
        "/v1/projects/{project_id}/interviews",
        response_model=InterviewRead,
        status_code=status.HTTP_201_CREATED,
    )
    def create_interview(project_id: str) -> InterviewRead:
        try:
            return app_store.create_interview(project_id, questions_for_interview())
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.get("/v1/interviews/{interview_id}", response_model=InterviewRead)
    def get_interview(interview_id: str) -> InterviewRead:
        try:
            return app_store.get_interview(interview_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.post("/v1/interviews/{interview_id}/consent", response_model=InterviewRead)
    def grant_consent(interview_id: str, payload: ConsentRequest) -> InterviewRead:
        try:
            return app_store.grant_consent(interview_id, payload)
        except (InvalidTransitionError, KeyError) as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @app.post("/v1/interviews/{interview_id}/consent/revoke", response_model=InterviewRead)
    def revoke_consent(interview_id: str) -> InterviewRead:
        try:
            return app_store.revoke_consent(interview_id)
        except (InvalidTransitionError, KeyError) as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @app.delete("/v1/interviews/{interview_id}/consent", status_code=status.HTTP_204_NO_CONTENT)
    def delete_consent(interview_id: str) -> Response:
        revoke_consent(interview_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get("/v1/interviews/{interview_id}/questions", response_model=list[QuestionRead])
    def get_questions(interview_id: str) -> Sequence[QuestionRead]:
        try:
            return app_store.get_questions(interview_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.post(
        "/v1/interviews/{interview_id}/answers",
        response_model=AnswerRead,
        status_code=status.HTTP_201_CREATED,
    )
    def record_answer(interview_id: str, payload: AnswerCreate) -> AnswerRead:
        try:
            return app_store.record_answer(interview_id, payload)
        except ConsentRequiredError as error:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except InvalidTransitionError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @app.get("/v1/projects/{project_id}/work-model", response_model=WorkModelRead)
    def get_work_model(project_id: str) -> WorkModelRead:
        try:
            return app_store.get_work_model(project_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.post("/v1/interviews/{interview_id}/build-work-model", response_model=WorkModelRead)
    def build_work_model(interview_id: str) -> WorkModelRead:
        try:
            interview = app_store.get_interview(interview_id)
            if not interview.active_consent:
                raise ConsentRequiredError(interview_id=interview_id)
            if interview.status != InterviewStatus.MODEL_BUILDING:
                detail = f"interview must be MODEL_BUILDING, got {interview.status}"
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
            project = app_store.require_project(interview.project_id)
            previous_versions = app_store.list_work_models(interview.project_id)
            payload = builder.build(
                WorkModelBuildInput(
                    project=project,
                    interview=interview,
                    questions=app_store.get_questions(interview_id),
                    answers=app_store.list_answers(interview_id),
                ),
            )
            validation_error = validate_payload(paths.work_model_schema, payload)
            if validation_error is not None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=validation_error,
                )
            model = app_store.replace_work_model(interview.project_id, payload, valid=True)
            app_store.transition_interview(interview_id, InterviewStatus.PLAYBACK_CONFIRMATION)
            action = (
                AuditAction.WORK_MODEL_REBUILT
                if len(previous_versions) > 0
                else AuditAction.WORK_MODEL_BUILT
            )
            app_store.record_audit(
                interview_id,
                action,
                {
                    "project_id": interview.project_id,
                    "interview_id": interview_id,
                    "work_model_version": model.version,
                },
            )
            return model
        except ConsentRequiredError as error:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
        except InsufficientAnswersError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except InvalidTransitionError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @app.get("/v1/interviews/{interview_id}/work-model", response_model=WorkModelRead)
    def get_interview_work_model(interview_id: str) -> WorkModelRead:
        try:
            return app_store.get_interview_work_model(interview_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.post("/v1/interviews/{interview_id}/playback/confirm", response_model=InterviewRead)
    def confirm_playback(interview_id: str) -> InterviewRead:
        try:
            interview = app_store.get_interview(interview_id)
            if interview.status != InterviewStatus.PLAYBACK_CONFIRMATION:
                detail = f"interview must be PLAYBACK_CONFIRMATION, got {interview.status}"
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
            model = app_store.get_work_model(interview.project_id)
            payload = playback_payload(model.payload, confirmed=True)
            app_store.replace_work_model(interview.project_id, payload, valid=True)
            app_store.transition_interview(interview_id, InterviewStatus.OPPORTUNITY_ANALYSIS_READY)
            finalized = app_store.transition_interview(interview_id, InterviewStatus.FINALIZED)
            app_store.record_audit(
                interview_id,
                AuditAction.PLAYBACK_CONFIRMED,
                {"project_id": interview.project_id, "interview_id": interview_id},
            )
            return finalized
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except InvalidTransitionError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @app.post("/v1/interviews/{interview_id}/playback/reject", response_model=InterviewRead)
    def reject_playback(interview_id: str) -> InterviewRead:
        try:
            interview = app_store.get_interview(interview_id)
            if interview.status != InterviewStatus.PLAYBACK_CONFIRMATION:
                detail = f"interview must be PLAYBACK_CONFIRMATION, got {interview.status}"
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
            model = app_store.get_work_model(interview.project_id)
            payload = playback_payload(model.payload, confirmed=False)
            app_store.replace_work_model(interview.project_id, payload, valid=True)
            rejected = app_store.transition_interview(interview_id, InterviewStatus.NEEDS_EVIDENCE)
            app_store.record_audit(
                interview_id,
                AuditAction.PLAYBACK_REJECTED,
                {"project_id": interview.project_id, "interview_id": interview_id},
            )
            return rejected
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except InvalidTransitionError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @app.get("/v1/interviews/{interview_id}/audit-events", response_model=list[AuditEventRead])
    def get_interview_audit_events(interview_id: str) -> Sequence[AuditEventRead]:
        try:
            return app_store.list_interview_audit_events(interview_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.get("/v1/projects/{project_id}/audit-events", response_model=list[AuditEventRead])
    def get_project_audit_events(project_id: str) -> Sequence[AuditEventRead]:
        try:
            return app_store.list_project_audit_events(project_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.post("/v1/projects/{project_id}/work-model/validate", response_model=ValidationRead)
    def validate_work_model(project_id: str, payload: WorkModelValidateRequest) -> ValidationRead:
        try:
            app_store.require_project(project_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        validation_error = validate_payload(paths.work_model_schema, payload.payload)
        app_store.replace_work_model(project_id, payload.payload, validation_error is None)
        return ValidationRead(
            valid=validation_error is None,
            schema_name="work-model-v1.schema.json",
            error=validation_error,
        )

    register_m3_routes(app, app_store, paths, selector, analyzer)
    register_m4_routes(app, app_store, paths, analyzer)
    register_discovery_routes(app, app_store, paths, analyzer)
    register_m5_routes(app, app_store, paths, design_builder)
    register_m6_routes(app, app_store, paths, blueprint_builder)
    register_m7_routes(app, app_store, paths, evaluation_runner)
    register_m8_routes(app, app_store, paths, release_evaluator)
    register_m9_routes(app, app_store, paths, implementation_builder)

    return app


def playback_payload(payload: JsonObject, confirmed: bool) -> JsonObject:
    updated = dict(payload)
    gate = updated.get("understanding_gate")
    updated["model_status"] = "CONFIRMED" if confirmed else "DISPUTED"
    if isinstance(gate, dict):
        gate["playback_confirmed"] = confirmed
        gate["result"] = "READY_FOR_ANALYSIS" if confirmed else "NEEDS_EVIDENCE"
        updated["understanding_gate"] = gate
    updated["updated_at"] = utc_now().isoformat()
    return updated


app = create_app()
