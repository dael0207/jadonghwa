from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, NoReturn
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Response, status

from work_discovery_api.contracts import ContractPaths, read_json, validate_payload
from work_discovery_api.domain import AuditAction
from work_discovery_api.evidence_files import EvidenceFileError, decode_and_extract
from work_discovery_api.implementation_export import (
    ExportValidationError,
    ImplementationExportSources,
    build_implementation_export,
)
from work_discovery_api.implementation_package_builder import (
    DeterministicImplementationPackageBuilder,
    ImplementationPackageInput,
)
from work_discovery_api.models import (
    BlueprintRead,
    CodegenReadinessRead,
    DesignPackageRead,
    EvidenceFileConfirm,
    EvidenceFileRead,
    EvidenceFileStoreCreate,
    EvidenceFileUpload,
    ImplementationPackageRead,
    ImplementationPackageStoreCreate,
    ImplementationRequirementsCreate,
    ImplementationRequirementsRead,
    JsonObject,
    OpportunityRead,
    ValidationRead,
    WorkModelRead,
)
from work_discovery_api.repository import WorkDiscoveryRepository


class M9PrerequisiteError(ValueError):
    pass


def _abort(message: str) -> NoReturn:
    raise M9PrerequisiteError(message)


def register_m9_routes(
    app: FastAPI,
    app_store: WorkDiscoveryRepository,
    paths: ContractPaths,
    builder: DeterministicImplementationPackageBuilder,
) -> None:
    @app.get("/v1/implementation-requirements/template", response_model=dict[str, object])
    def get_implementation_requirements_template() -> JsonObject:
        return read_json(
            paths.root
            / "examples"
            / "m9"
            / "monthly-report-implementation-requirements.json",
        )

    @app.post(
        "/v1/projects/{project_id}/evidence-files",
        response_model=EvidenceFileRead,
        status_code=status.HTTP_201_CREATED,
    )
    def upload_evidence_file(
        project_id: str,
        payload: EvidenceFileUpload,
    ) -> EvidenceFileRead:
        try:
            app_store.require_project(project_id)
            extracted = decode_and_extract(payload)
            evidence = app_store.save_evidence_file(
                EvidenceFileStoreCreate(
                    project_id=project_id,
                    role=payload.role,
                    filename=extracted.filename,
                    content_type=extracted.content_type,
                    content=extracted.content,
                    sha256=extracted.sha256,
                    extracted_schema=extracted.extracted_schema,
                    sample_values=extracted.sample_values,
                ),
            )
            app_store.record_audit(
                evidence.id,
                AuditAction.EVIDENCE_FILE_UPLOADED,
                {
                    "project_id": project_id,
                    "evidence_file_id": evidence.id,
                    "role": evidence.role.value,
                    "sha256": evidence.sha256,
                },
            )
            return evidence
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except EvidenceFileError as error:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=str(error),
            ) from error

    @app.get(
        "/v1/projects/{project_id}/evidence-files",
        response_model=list[EvidenceFileRead],
    )
    def list_evidence_files(project_id: str) -> Sequence[EvidenceFileRead]:
        try:
            return app_store.list_project_evidence_files(project_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.post("/v1/evidence-files/{evidence_file_id}/confirm", response_model=EvidenceFileRead)
    def confirm_evidence_file(
        evidence_file_id: str,
        payload: EvidenceFileConfirm,
    ) -> EvidenceFileRead:
        try:
            evidence = app_store.confirm_evidence_file(evidence_file_id, payload)
            app_store.record_audit(
                evidence.id,
                AuditAction.EVIDENCE_FILE_CONFIRMED,
                {
                    "project_id": evidence.project_id,
                    "evidence_file_id": evidence.id,
                    "confirmed": payload.confirmed,
                    "confirmed_by": payload.confirmed_by,
                },
            )
            return evidence
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.post(
        "/v1/projects/{project_id}/implementation-requirements",
        response_model=ImplementationRequirementsRead,
        status_code=status.HTTP_201_CREATED,
    )
    def record_implementation_requirements(
        project_id: str,
        payload: ImplementationRequirementsCreate,
    ) -> ImplementationRequirementsRead:
        try:
            requirements = app_store.save_implementation_requirements(
                project_id,
                payload.payload,
                payload.confirmed,
            )
            app_store.record_audit(
                requirements.id,
                AuditAction.IMPLEMENTATION_REQUIREMENTS_RECORDED,
                {
                    "project_id": project_id,
                    "implementation_requirements_id": requirements.id,
                    "confirmed": requirements.confirmed,
                },
            )
            return requirements
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.get(
        "/v1/projects/{project_id}/implementation-requirements/latest",
        response_model=ImplementationRequirementsRead,
    )
    def get_latest_implementation_requirements(
        project_id: str,
    ) -> ImplementationRequirementsRead:
        try:
            requirements = app_store.get_latest_implementation_requirements(project_id)
            if requirements is None:
                _abort("implementation requirements have not been recorded")
            return requirements
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except M9PrerequisiteError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.post(
        "/v1/projects/{project_id}/implementation-packages",
        response_model=ImplementationPackageRead,
        status_code=status.HTTP_201_CREATED,
    )
    def create_implementation_package(project_id: str) -> ImplementationPackageRead:
        try:
            project = app_store.require_project(project_id)
            work_model, opportunity, design_package, blueprint = _latest_sources(
                app_store,
                project_id,
            )
            package_id = str(uuid4())
            built = builder.build(
                ImplementationPackageInput(
                    package_id=package_id,
                    project=project,
                    work_model=work_model,
                    opportunity=opportunity,
                    design_package=design_package,
                    blueprint=blueprint,
                    requirements=app_store.get_latest_implementation_requirements(project_id),
                    evidence_files=app_store.list_project_evidence_files(project_id),
                ),
            )
            validation_error = validate_payload(paths.implementation_package_schema, built.payload)
            if validation_error is not None:
                detail = f"generated implementation package failed validation: {validation_error}"
                raise M9PrerequisiteError(detail)
            readiness = built.payload["codegen_readiness"]
            if not isinstance(readiness, dict):
                _abort("generated codegen readiness is not an object")
            readiness_error = validate_payload(paths.codegen_readiness_schema, readiness)
            if readiness_error is not None:
                detail = f"generated codegen readiness failed validation: {readiness_error}"
                raise M9PrerequisiteError(detail)
            package = app_store.save_implementation_package(
                ImplementationPackageStoreCreate(
                    package_id=package_id,
                    project_id=project_id,
                    blueprint_id=blueprint.id,
                    payload=built.payload,
                    valid=True,
                    readiness_status=built.readiness_status,
                ),
            )
            app_store.record_audit(
                package.id,
                AuditAction.IMPLEMENTATION_PACKAGE_CREATED,
                {
                    "project_id": project_id,
                    "implementation_package_id": package.id,
                    "readiness_status": package.readiness_status.value,
                },
            )
            app_store.record_audit(
                package.id,
                AuditAction.CODEGEN_READINESS_EVALUATED,
                {
                    "project_id": project_id,
                    "implementation_package_id": package.id,
                    "readiness_status": package.readiness_status.value,
                },
            )
            return package
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except M9PrerequisiteError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @app.get(
        "/v1/projects/{project_id}/implementation-packages",
        response_model=list[ImplementationPackageRead],
    )
    def list_implementation_packages(
        project_id: str,
    ) -> Sequence[ImplementationPackageRead]:
        try:
            return app_store.list_project_implementation_packages(project_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.get(
        "/v1/implementation-packages/{package_id}",
        response_model=ImplementationPackageRead,
    )
    def get_implementation_package(package_id: str) -> ImplementationPackageRead:
        try:
            return app_store.get_implementation_package(package_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.post(
        "/v1/implementation-packages/{package_id}/validate",
        response_model=ValidationRead,
    )
    def validate_implementation_package(package_id: str) -> ValidationRead:
        try:
            package = app_store.get_implementation_package(package_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        validation_error = validate_payload(paths.implementation_package_schema, package.payload)
        app_store.record_audit(
            package.id,
            AuditAction.IMPLEMENTATION_PACKAGE_VALIDATED,
            {
                "project_id": package.project_id,
                "implementation_package_id": package.id,
                "valid": validation_error is None,
            },
        )
        return ValidationRead(
            valid=validation_error is None,
            schema_name="implementation-package-v1.schema.json",
            error=validation_error,
        )

    @app.get(
        "/v1/implementation-packages/{package_id}/codegen-readiness",
        response_model=CodegenReadinessRead,
    )
    def get_codegen_readiness(package_id: str) -> CodegenReadinessRead:
        try:
            package = app_store.get_implementation_package(package_id)
            readiness = package.payload.get("codegen_readiness")
            if not isinstance(readiness, dict):
                _abort("package has no codegen readiness object")
            return CodegenReadinessRead.model_validate(readiness)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except (M9PrerequisiteError, ValueError) as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @app.get("/v1/implementation-packages/{package_id}/export.zip")
    def export_implementation_package(
        package_id: str,
        mode: Literal["draft", "codegen"] = "codegen",
    ) -> Response:
        try:
            package = app_store.get_implementation_package(package_id)
            sources = _sources_for_package(app_store, package)
            content = build_implementation_export(
                package,
                sources,
                paths,
                draft=mode == "draft",
            )
            app_store.record_audit(
                package.id,
                AuditAction.IMPLEMENTATION_PACKAGE_EXPORTED,
                {
                    "project_id": package.project_id,
                    "implementation_package_id": package.id,
                    "mode": mode,
                },
            )
            filename = f"implementation-package-{package.id[:8]}-{mode}.zip"
            return Response(
                content=content,
                media_type="application/zip",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except ExportValidationError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


def _latest_sources(
    app_store: WorkDiscoveryRepository,
    project_id: str,
) -> tuple[WorkModelRead, OpportunityRead, DesignPackageRead, BlueprintRead]:
    opportunities = app_store.list_opportunities(project_id)
    if not opportunities:
        _abort("M9 전에 READY_FOR_DESIGN opportunity를 생성해 주세요.")
    opportunity = opportunities[-1]
    packages = app_store.list_opportunity_design_packages(opportunity.id)
    if not packages:
        _abort("M9 전에 FULL_G1 design package를 생성해 주세요.")
    design_package = packages[-1]
    blueprints = app_store.list_design_package_blueprints(design_package.id)
    if not blueprints:
        _abort("M9 전에 export-ready FULL_G1 blueprint를 생성해 주세요.")
    blueprint = blueprints[-1]
    gate = opportunity.payload.get("gate")
    gate_result = gate.get("result") if isinstance(gate, dict) else None
    package_type = design_package.payload.get("package_type")
    if gate_result != "READY_FOR_DESIGN" or package_type != "FULL_G1" or not blueprint.export_ready:
        _abort(
            "M9에는 READY_FOR_DESIGN, FULL_G1, export-ready blueprint가 모두 필요합니다.",
        )
    work_model = app_store.get_work_model_version(
        project_id,
        opportunity.work_model_version,
    )
    return work_model, opportunity, design_package, blueprint


def _sources_for_package(
    app_store: WorkDiscoveryRepository,
    package: ImplementationPackageRead,
) -> ImplementationExportSources:
    payload = package.payload
    work_model_version = payload.get("source_work_model_version")
    if not isinstance(work_model_version, int):
        message = "source work model version is unresolved"
        raise ExportValidationError(message)
    opportunity_id = payload.get("source_opportunity_id")
    design_package_id = payload.get("source_design_package_id")
    blueprint_id = payload.get("source_blueprint_id")
    if not all(
        isinstance(value, str) for value in (opportunity_id, design_package_id, blueprint_id)
    ):
        message = "source artifact references are unresolved"
        raise ExportValidationError(message)
    return ImplementationExportSources(
        work_model=app_store.get_work_model_version(
            package.project_id,
            work_model_version,
        ),
        opportunity=app_store.get_opportunity(str(opportunity_id)),
        design_package=app_store.get_design_package(str(design_package_id)),
        blueprint=app_store.get_blueprint(str(blueprint_id)),
        evidence_files=app_store.list_project_evidence_files(package.project_id),
    )
