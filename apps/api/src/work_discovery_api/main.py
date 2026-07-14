from __future__ import annotations

from collections.abc import Sequence

from fastapi import FastAPI, HTTPException, Response, status

from work_discovery_api.contracts import default_contract_paths, initial_questions, validate_payload
from work_discovery_api.domain import ConsentRequiredError, InvalidTransitionError
from work_discovery_api.models import (
    AnswerCreate,
    AnswerRead,
    ConsentRequest,
    InterviewRead,
    ProjectCreate,
    ProjectRead,
    QuestionRead,
    ValidationRead,
    WorkModelRead,
    WorkModelValidateRequest,
)
from work_discovery_api.store import MemoryStore


def create_app(store: MemoryStore | None = None) -> FastAPI:
    app_store = store or MemoryStore()
    app = FastAPI(
        title="Work Discovery AI M0 API",
        version="0.1.0",
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
            return app_store.interview_read(app_store.require_interview(interview_id))
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
            app_store.require_interview(interview_id)
            return app_store.questions[interview_id]
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

    return app


app = create_app()
