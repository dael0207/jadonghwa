from __future__ import annotations

from collections.abc import Sequence

from fastapi import FastAPI, HTTPException, status

from work_discovery_api.contracts import ContractPaths, validate_payload
from work_discovery_api.design_package_builder import (
    DesignPackageBlockedError,
    DesignPackageBuildInput,
    DeterministicDesignPackageBuilder,
)
from work_discovery_api.domain import AuditAction
from work_discovery_api.models import DesignPackageRead, InterviewRead, ValidationRead
from work_discovery_api.opportunity_readiness import readiness_from_opportunity
from work_discovery_api.repository import WorkDiscoveryRepository


def register_m5_routes(
    app: FastAPI,
    app_store: WorkDiscoveryRepository,
    paths: ContractPaths,
    builder: DeterministicDesignPackageBuilder,
) -> None:
    @app.post(
        "/v1/opportunities/{opportunity_id}/design-package",
        response_model=DesignPackageRead,
        status_code=status.HTTP_201_CREATED,
    )
    def create_design_package(opportunity_id: str) -> DesignPackageRead:
        try:
            opportunity = app_store.get_opportunity(opportunity_id)
            if not opportunity.schema_valid:
                detail = "schema-valid opportunity is required before design package generation"
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
            model = app_store.get_work_model_version(
                opportunity.project_id,
                opportunity.work_model_version,
            )
            interview = latest_project_interview(app_store, opportunity.project_id)
            readiness = readiness_from_opportunity(
                opportunity.project_id,
                interview.id if interview else None,
                opportunity,
            )
            package_payload = builder.build(
                DesignPackageBuildInput(
                    opportunity=opportunity,
                    work_model=model,
                    readiness=readiness,
                ),
            )
            validation_error = validate_payload(paths.design_package_schema, package_payload)
            if validation_error is not None:
                detail = f"generated design package failed schema validation: {validation_error}"
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
            package = app_store.save_design_package(
                opportunity.project_id,
                opportunity.id,
                opportunity.work_model_version,
                package_payload,
                valid=True,
            )
            app_store.record_audit(
                package.id,
                AuditAction.DESIGN_PACKAGE_CREATED,
                {
                    "project_id": opportunity.project_id,
                    "opportunity_id": opportunity.id,
                    "design_package_id": package.id,
                    "package_type": package_payload["package_type"],
                    "readiness_result": readiness.result,
                },
            )
            return package
        except DesignPackageBlockedError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.get(
        "/v1/opportunities/{opportunity_id}/design-packages",
        response_model=list[DesignPackageRead],
    )
    def list_opportunity_design_packages(opportunity_id: str) -> Sequence[DesignPackageRead]:
        try:
            return app_store.list_opportunity_design_packages(opportunity_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.get("/v1/projects/{project_id}/design-packages", response_model=list[DesignPackageRead])
    def list_project_design_packages(project_id: str) -> Sequence[DesignPackageRead]:
        try:
            return app_store.list_project_design_packages(project_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.get("/v1/design-packages/{package_id}", response_model=DesignPackageRead)
    def get_design_package(package_id: str) -> DesignPackageRead:
        try:
            return app_store.get_design_package(package_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.post("/v1/design-packages/{package_id}/validate", response_model=ValidationRead)
    def validate_design_package(package_id: str) -> ValidationRead:
        try:
            package = app_store.get_design_package(package_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        validation_error = validate_payload(paths.design_package_schema, package.payload)
        app_store.record_audit(
            package.id,
            AuditAction.DESIGN_PACKAGE_VALIDATED,
            {
                "project_id": package.project_id,
                "opportunity_id": package.opportunity_id,
                "design_package_id": package.id,
                "valid": validation_error is None,
            },
        )
        return ValidationRead(
            valid=validation_error is None,
            schema_name="design-package-v1.schema.json",
            error=validation_error,
        )


def latest_project_interview(
    app_store: WorkDiscoveryRepository,
    project_id: str,
) -> InterviewRead | None:
    interviews = app_store.list_project_interviews(project_id)
    if len(interviews) == 0:
        return None
    return interviews[-1]
