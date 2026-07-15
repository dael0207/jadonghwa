from __future__ import annotations

from collections.abc import Sequence

from fastapi import FastAPI, HTTPException, Response, status

from work_discovery_api.blueprint_builder import (
    BlueprintBlockedError,
    BlueprintBuildInput,
    DeterministicBlueprintBuilder,
)
from work_discovery_api.blueprint_export import blueprint_json_export, blueprint_markdown_export
from work_discovery_api.contracts import ContractPaths, validate_payload
from work_discovery_api.domain import AuditAction
from work_discovery_api.models import BlueprintRead, JsonObject, ValidationRead
from work_discovery_api.repository import WorkDiscoveryRepository


def register_m6_routes(
    app: FastAPI,
    app_store: WorkDiscoveryRepository,
    paths: ContractPaths,
    builder: DeterministicBlueprintBuilder,
) -> None:
    @app.post(
        "/v1/design-packages/{package_id}/blueprint",
        response_model=BlueprintRead,
        status_code=status.HTTP_201_CREATED,
    )
    def create_blueprint(package_id: str) -> BlueprintRead:
        try:
            package = app_store.get_design_package(package_id)
            if not package.schema_valid:
                detail = "schema-valid design package is required before blueprint generation"
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
            payload = builder.build(BlueprintBuildInput(package=package))
            validation_error = validate_payload(paths.blueprint_schema, payload)
            if validation_error is not None:
                detail = f"generated blueprint failed schema validation: {validation_error}"
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
            blueprint = app_store.save_blueprint(
                package.project_id,
                package.id,
                payload,
                valid=True,
                export_ready=payload.get("export_ready") is True,
            )
            app_store.record_audit(
                blueprint.id,
                AuditAction.BLUEPRINT_CREATED,
                {
                    "project_id": package.project_id,
                    "design_package_id": package.id,
                    "blueprint_id": blueprint.id,
                    "blueprint_type": payload["blueprint_type"],
                    "export_ready": blueprint.export_ready,
                },
            )
            return blueprint
        except BlueprintBlockedError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.get(
        "/v1/design-packages/{package_id}/blueprints",
        response_model=list[BlueprintRead],
    )
    def list_design_package_blueprints(package_id: str) -> Sequence[BlueprintRead]:
        try:
            return app_store.list_design_package_blueprints(package_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.get("/v1/projects/{project_id}/blueprints", response_model=list[BlueprintRead])
    def list_project_blueprints(project_id: str) -> Sequence[BlueprintRead]:
        try:
            return app_store.list_project_blueprints(project_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.get("/v1/blueprints/{blueprint_id}", response_model=BlueprintRead)
    def get_blueprint(blueprint_id: str) -> BlueprintRead:
        try:
            return app_store.get_blueprint(blueprint_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.post("/v1/blueprints/{blueprint_id}/validate", response_model=ValidationRead)
    def validate_blueprint(blueprint_id: str) -> ValidationRead:
        try:
            blueprint = app_store.get_blueprint(blueprint_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        validation_error = validate_payload(paths.blueprint_schema, blueprint.payload)
        app_store.record_audit(
            blueprint.id,
            AuditAction.BLUEPRINT_VALIDATED,
            {
                "project_id": blueprint.project_id,
                "design_package_id": blueprint.design_package_id,
                "blueprint_id": blueprint.id,
                "valid": validation_error is None,
            },
        )
        return ValidationRead(
            valid=validation_error is None,
            schema_name="blueprint-v1.schema.json",
            error=validation_error,
        )

    @app.get("/v1/blueprints/{blueprint_id}/export/json")
    def export_blueprint_json(blueprint_id: str) -> JsonObject:
        try:
            blueprint = app_store.get_blueprint(blueprint_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        record_export(app_store, blueprint, "json")
        return blueprint_json_export(blueprint)

    @app.get("/v1/blueprints/{blueprint_id}/export/markdown")
    def export_blueprint_markdown(blueprint_id: str) -> Response:
        try:
            blueprint = app_store.get_blueprint(blueprint_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        record_export(app_store, blueprint, "markdown")
        return Response(
            content=blueprint_markdown_export(blueprint),
            media_type="text/markdown; charset=utf-8",
        )


def record_export(
    app_store: WorkDiscoveryRepository,
    blueprint: BlueprintRead,
    export_format: str,
) -> None:
    app_store.record_audit(
        blueprint.id,
        AuditAction.BLUEPRINT_EXPORTED,
        {
            "project_id": blueprint.project_id,
            "design_package_id": blueprint.design_package_id,
            "blueprint_id": blueprint.id,
            "format": export_format,
            "export_ready": blueprint.export_ready,
        },
    )
