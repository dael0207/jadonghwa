from __future__ import annotations

from collections.abc import Sequence

from fastapi import FastAPI, HTTPException, status

from work_discovery_api.contracts import ContractPaths, validate_payload
from work_discovery_api.domain import AuditAction, ConsentRequiredError, InterviewStatus
from work_discovery_api.models import (
    InterviewRead,
    OpportunityDiffRead,
    OpportunityRead,
    OpportunityValidateRequest,
    ReadinessRead,
    ValidationRead,
)
from work_discovery_api.opportunity_analyzer import (
    DeterministicOpportunityAnalyzer,
    OpportunityAnalysisInput,
)
from work_discovery_api.opportunity_readiness import diff_opportunities, readiness_from_opportunity
from work_discovery_api.repository import WorkDiscoveryRepository


def register_m4_routes(
    app: FastAPI,
    app_store: WorkDiscoveryRepository,
    paths: ContractPaths,
    analyzer: DeterministicOpportunityAnalyzer,
) -> None:
    @app.post(
        "/v1/projects/{project_id}/opportunities/analyze",
        response_model=OpportunityRead,
        status_code=status.HTTP_201_CREATED,
    )
    def analyze_opportunity(project_id: str) -> OpportunityRead:
        try:
            interview = active_project_interview(app_store, project_id)
            model = app_store.get_work_model(project_id)
            if not model.schema_valid:
                detail = "schema-valid Work Model is required before opportunity analysis"
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
            payload = analyzer.draft(OpportunityAnalysisInput(work_model=model))
            validation_error = validate_payload(paths.opportunity_schema, payload)
            if validation_error is not None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=validation_error,
                )
            opportunity = app_store.save_opportunity(project_id, model.version, payload, valid=True)
            app_store.record_audit(
                project_id,
                AuditAction.OPPORTUNITY_ANALYZED,
                {
                    "project_id": project_id,
                    "interview_id": interview.id if interview else None,
                    "work_model_version": model.version,
                    "opportunity_id": opportunity.id,
                },
            )
            return opportunity
        except ConsentRequiredError as error:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.get("/v1/projects/{project_id}/opportunities", response_model=list[OpportunityRead])
    def list_opportunities(project_id: str) -> Sequence[OpportunityRead]:
        try:
            return app_store.list_opportunities(project_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.get("/v1/opportunities/{opportunity_id}", response_model=OpportunityRead)
    def get_opportunity(opportunity_id: str) -> OpportunityRead:
        try:
            return app_store.get_opportunity(opportunity_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.post("/v1/opportunities/{opportunity_id}/validate", response_model=ValidationRead)
    def validate_opportunity(
        opportunity_id: str,
        payload: OpportunityValidateRequest,
    ) -> ValidationRead:
        try:
            opportunity = app_store.get_opportunity(opportunity_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        validation_error = validate_payload(paths.opportunity_schema, opportunity.payload)
        app_store.record_audit(
            opportunity.id,
            AuditAction.OPPORTUNITY_VALIDATED,
            {
                "project_id": opportunity.project_id,
                "opportunity_id": opportunity.id,
                "accepted": payload.accepted,
                "notes": payload.notes,
                "valid": validation_error is None,
            },
        )
        return ValidationRead(
            valid=validation_error is None,
            schema_name="opportunity-v1.schema.json",
            error=validation_error,
        )

    @app.get("/v1/interviews/{interview_id}/readiness", response_model=ReadinessRead)
    def get_interview_readiness(interview_id: str) -> ReadinessRead:
        try:
            interview = app_store.get_interview(interview_id)
            readiness = latest_readiness(app_store, interview.project_id, interview_id)
            app_store.record_audit(
                interview_id,
                AuditAction.READINESS_EVALUATED,
                {
                    "project_id": interview.project_id,
                    "interview_id": interview_id,
                    "result": readiness.result,
                    "ready_for_g1": readiness.ready_for_g1,
                },
            )
            return readiness
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @app.get("/v1/projects/{project_id}/readiness", response_model=ReadinessRead)
    def get_project_readiness(project_id: str) -> ReadinessRead:
        try:
            interview = latest_project_interview(app_store, project_id)
            readiness = latest_readiness(
                app_store,
                project_id,
                interview.id if interview else None,
            )
            app_store.record_audit(
                project_id,
                AuditAction.READINESS_EVALUATED,
                {
                    "project_id": project_id,
                    "interview_id": interview.id if interview else None,
                    "result": readiness.result,
                    "ready_for_g1": readiness.ready_for_g1,
                },
            )
            return readiness
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @app.get("/v1/projects/{project_id}/opportunities/diff", response_model=OpportunityDiffRead)
    def get_opportunity_diff(project_id: str) -> OpportunityDiffRead:
        try:
            opportunities = app_store.list_opportunities(project_id)
            if len(opportunities) < 2:
                detail = "at least two opportunity analyses are required for diff"
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
            diff = diff_opportunities(project_id, opportunities[-2], opportunities[-1])
            app_store.record_audit(
                project_id,
                AuditAction.OPPORTUNITY_DIFF_GENERATED,
                {
                    "project_id": project_id,
                    "previous_opportunity_id": diff.previous_opportunity_id,
                    "latest_opportunity_id": diff.latest_opportunity_id,
                },
            )
            return diff
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


def active_project_interview(
    app_store: WorkDiscoveryRepository,
    project_id: str,
) -> InterviewRead | None:
    interview = latest_project_interview(app_store, project_id)
    if interview is None:
        return None
    if interview.status == InterviewStatus.CONSENT_REVOKED or not interview.active_consent:
        raise ConsentRequiredError(interview_id=interview.id)
    return interview


def latest_project_interview(
    app_store: WorkDiscoveryRepository,
    project_id: str,
) -> InterviewRead | None:
    interviews = app_store.list_project_interviews(project_id)
    if len(interviews) == 0:
        return None
    return interviews[-1]


def latest_readiness(
    app_store: WorkDiscoveryRepository,
    project_id: str,
    interview_id: str | None,
) -> ReadinessRead:
    opportunities = app_store.list_opportunities(project_id)
    if not opportunities:
        message = "opportunity analysis is required before readiness evaluation"
        raise ValueError(message)
    return readiness_from_opportunity(project_id, interview_id, opportunities[-1])
