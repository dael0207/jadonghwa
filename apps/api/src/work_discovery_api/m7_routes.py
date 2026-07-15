from __future__ import annotations

from collections.abc import Sequence

from fastapi import FastAPI, HTTPException, status

from work_discovery_api.contracts import ContractPaths, validate_payload
from work_discovery_api.domain import AuditAction
from work_discovery_api.evaluation_runner import (
    DeterministicEvaluationRunner,
    EvaluationRunInput,
)
from work_discovery_api.models import EvaluationRunRead, ValidationRead
from work_discovery_api.repository import WorkDiscoveryRepository
from work_discovery_api.work_model_evidence import object_value


def register_m7_routes(
    app: FastAPI,
    app_store: WorkDiscoveryRepository,
    paths: ContractPaths,
    runner: DeterministicEvaluationRunner,
) -> None:
    @app.post(
        "/v1/projects/{project_id}/evaluation-runs",
        response_model=EvaluationRunRead,
        status_code=status.HTTP_201_CREATED,
    )
    def create_evaluation_run(project_id: str) -> EvaluationRunRead:
        try:
            app_store.require_project(project_id)
            payload = runner.run(
                EvaluationRunInput(
                    project_id=project_id,
                    interviews=app_store.list_project_interviews(project_id),
                    work_models=app_store.list_work_models(project_id),
                    opportunities=app_store.list_opportunities(project_id),
                    design_packages=app_store.list_project_design_packages(project_id),
                    blueprints=app_store.list_project_blueprints(project_id),
                    audit_events=app_store.list_project_audit_events(project_id),
                ),
            )
            validation_error = validate_payload(paths.evaluation_run_schema, payload)
            if validation_error is not None:
                detail = f"generated evaluation run failed schema validation: {validation_error}"
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
            run = app_store.save_evaluation_run(project_id, payload, valid=True)
            app_store.record_audit(
                run.id,
                AuditAction.EVALUATION_RUN_CREATED,
                {
                    "project_id": project_id,
                    "evaluation_run_id": run.id,
                    "overall_passed": object_value(payload.get("score_summary")).get(
                        "overall_passed",
                    ),
                },
            )
            return run
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.get(
        "/v1/projects/{project_id}/evaluation-runs",
        response_model=list[EvaluationRunRead],
    )
    def list_evaluation_runs(project_id: str) -> Sequence[EvaluationRunRead]:
        try:
            return app_store.list_project_evaluation_runs(project_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.get("/v1/evaluation-runs/{run_id}", response_model=EvaluationRunRead)
    def get_evaluation_run(run_id: str) -> EvaluationRunRead:
        try:
            return app_store.get_evaluation_run(run_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.post("/v1/evaluation-runs/{run_id}/validate", response_model=ValidationRead)
    def validate_evaluation_run(run_id: str) -> ValidationRead:
        try:
            run = app_store.get_evaluation_run(run_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        validation_error = validate_payload(paths.evaluation_run_schema, run.payload)
        app_store.record_audit(
            run.id,
            AuditAction.EVALUATION_RUN_VALIDATED,
            {
                "project_id": run.project_id,
                "evaluation_run_id": run.id,
                "valid": validation_error is None,
            },
        )
        return ValidationRead(
            valid=validation_error is None,
            schema_name="evaluation-run-v1.schema.json",
            error=validation_error,
        )
