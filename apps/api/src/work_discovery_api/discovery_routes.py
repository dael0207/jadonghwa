from __future__ import annotations

from fastapi import FastAPI, HTTPException, status

from work_discovery_api.contracts import ContractPaths, validate_payload
from work_discovery_api.discovery_guidance import (
    RECOVERY_RESULTS,
    DiscoveryGuidanceInput,
    build_discovery_guidance,
)
from work_discovery_api.domain import (
    AuditAction,
    ConsentRequiredError,
    InterviewStatus,
    InvalidTransitionError,
)
from work_discovery_api.m4_routes import latest_project_interview, latest_readiness
from work_discovery_api.models import (
    DiscoveryGuidanceRead,
    InterviewRead,
    OpportunityRead,
    WorkModelRead,
)
from work_discovery_api.opportunity_analyzer import (
    DeterministicOpportunityAnalyzer,
    OpportunityAnalysisInput,
)
from work_discovery_api.repository import WorkDiscoveryRepository

FORBIDDEN_RECOVERY_STATUSES = frozenset(
    {
        InterviewStatus.CONSENT_REVOKED,
        InterviewStatus.DELETION_PENDING,
        InterviewStatus.ABORTED,
    },
)


def register_discovery_routes(
    app: FastAPI,
    app_store: WorkDiscoveryRepository,
    paths: ContractPaths,
    analyzer: DeterministicOpportunityAnalyzer,
) -> None:
    @app.get(
        "/v1/projects/{project_id}/discovery-guidance",
        response_model=DiscoveryGuidanceRead,
    )
    def get_discovery_guidance(project_id: str) -> DiscoveryGuidanceRead:
        try:
            app_store.require_project(project_id)
            interview = latest_project_interview(app_store, project_id)
            opportunity = require_latest_opportunity(app_store, project_id)
            readiness = latest_readiness(
                app_store,
                project_id,
                interview.id if interview else None,
            )
            work_model = optional_work_model(app_store, project_id)
            return build_discovery_guidance(
                DiscoveryGuidanceInput(
                    paths=paths,
                    project_id=project_id,
                    interview=interview,
                    opportunity=opportunity,
                    readiness=readiness,
                    work_model=work_model,
                ),
            )
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @app.post(
        "/v1/projects/{project_id}/discovery/reopen",
        response_model=InterviewRead,
    )
    def reopen_discovery(project_id: str) -> InterviewRead:
        try:
            app_store.require_project(project_id)
            interview = require_latest_interview(app_store, project_id)
            if interview.status in FORBIDDEN_RECOVERY_STATUSES:
                message = f"discovery recovery is forbidden from {interview.status}"
                raise ValueError(message)
            if not interview.active_consent:
                raise ConsentRequiredError(interview_id=interview.id)
            opportunity = require_latest_opportunity(app_store, project_id)
            readiness = latest_readiness(app_store, project_id, interview.id)
            if readiness.result not in RECOVERY_RESULTS:
                message = f"discovery recovery is not required for {readiness.result}"
                raise ValueError(message)
            reopened = app_store.reopen_interview_for_discovery(interview.id)
            app_store.record_audit(
                interview.id,
                AuditAction.DISCOVERY_REOPENED,
                {
                    "project_id": project_id,
                    "interview_id": interview.id,
                    "opportunity_id": opportunity.id,
                    "gate_result": readiness.result,
                    "previous_status": interview.status,
                    "status": reopened.status,
                },
            )
            return reopened
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except (ConsentRequiredError, InvalidTransitionError, ValueError) as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @app.post(
        "/v1/projects/{project_id}/discovery/reanalyze",
        response_model=OpportunityRead,
        status_code=status.HTTP_201_CREATED,
    )
    def reanalyze_discovery(project_id: str) -> OpportunityRead:
        try:
            app_store.require_project(project_id)
            interview = require_latest_interview(app_store, project_id)
            previous = require_latest_opportunity(app_store, project_id)
            previous_readiness = latest_readiness(app_store, project_id, interview.id)
            if previous_readiness.result not in RECOVERY_RESULTS:
                message = f"discovery reanalysis is not required for {previous_readiness.result}"
                raise ValueError(message)
            if not interview.active_consent:
                raise ConsentRequiredError(interview_id=interview.id)
            if interview.status != InterviewStatus.FINALIZED:
                message = "playback confirmation must finish before discovery reanalysis"
                raise ValueError(message)
            model = app_store.get_work_model(project_id)
            if not model.schema_valid or model.payload.get("model_status") != "CONFIRMED":
                message = "a schema-valid confirmed Work Model is required for reanalysis"
                raise ValueError(message)
            if model.version <= previous.work_model_version:
                message = "new confirmed evidence is required before discovery reanalysis"
                raise ValueError(message)
            payload = analyzer.draft(OpportunityAnalysisInput(work_model=model))
            validation_error = validate_payload(paths.opportunity_schema, payload)
            if validation_error is not None:
                message = f"reanalyzed opportunity is invalid: {validation_error}"
                raise ValueError(message)
            opportunity = app_store.save_opportunity(project_id, model.version, payload, valid=True)
            app_store.record_audit(
                project_id,
                AuditAction.DISCOVERY_REANALYZED,
                {
                    "project_id": project_id,
                    "interview_id": interview.id,
                    "previous_opportunity_id": previous.id,
                    "opportunity_id": opportunity.id,
                    "previous_gate_result": previous_readiness.result,
                    "work_model_version": model.version,
                },
            )
            return opportunity
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except (ConsentRequiredError, ValueError) as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


def require_latest_interview(
    app_store: WorkDiscoveryRepository,
    project_id: str,
) -> InterviewRead:
    interview = latest_project_interview(app_store, project_id)
    if interview is None:
        message = "an interview is required for discovery recovery"
        raise ValueError(message)
    return interview


def require_latest_opportunity(
    app_store: WorkDiscoveryRepository,
    project_id: str,
) -> OpportunityRead:
    opportunities = app_store.list_opportunities(project_id)
    if not opportunities:
        message = "opportunity analysis is required before discovery recovery"
        raise ValueError(message)
    return opportunities[-1]


def optional_work_model(
    app_store: WorkDiscoveryRepository,
    project_id: str,
) -> WorkModelRead | None:
    try:
        return app_store.get_work_model(project_id)
    except KeyError:
        return None
