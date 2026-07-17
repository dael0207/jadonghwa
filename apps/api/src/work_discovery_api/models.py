from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from work_discovery_api.domain import (
    AnswerStatus,
    AuditAction,
    EvidenceFileRole,
    ImplementationReadinessStatus,
    InterviewStatus,
)

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | Sequence[JsonValue] | Mapping[str, JsonValue]
type JsonObject = dict[str, JsonValue]


def utc_now() -> datetime:
    return datetime.now(UTC)


class ProjectCreate(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    workspace_name: str = Field(default="Local Workspace", min_length=1)


class ProjectRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    workspace_id: str
    workspace_name: str
    created_at: datetime


class InterviewRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    project_id: str
    status: InterviewStatus
    active_consent: bool
    answered_count: int
    created_at: datetime


class ConsentRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    ai_processing: bool
    data_processing: bool
    audio_recording: bool = False
    retention_days: int = Field(default=0, ge=0)


class QuestionRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    stage: str
    dimension: str
    text: str
    required: bool
    position: int


class AnswerCreate(BaseModel):
    model_config = ConfigDict(frozen=True)

    question_id: str
    text: str = ""
    status: AnswerStatus = AnswerStatus.ANSWERED
    revision_of: str | None = None


class EvidenceCreate(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1)
    question_id: str | None = None


class AnswerRevisionCreate(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1)
    status: AnswerStatus = AnswerStatus.ANSWERED


class AnswerRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    turn_id: str
    question_id: str
    text: str
    status: AnswerStatus
    revision_of: str | None
    source_refs: tuple[str, ...]
    created_at: datetime


class WorkModelRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str
    version: int
    payload: JsonObject
    schema_valid: bool
    created_at: datetime


class AuditEventRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    subject_id: str
    action: AuditAction
    metadata: JsonObject
    created_at: datetime


class CoverageItemRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    status: str
    evidence_count: int
    question_ids: tuple[str, ...]


class CoverageRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    interview_id: str
    covered_count: int
    total_count: int
    items: tuple[CoverageItemRead, ...]


class NextQuestionRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    interview_id: str
    complete: bool
    coverage_key: str | None
    question_id: str | None
    text: str | None
    reason: str


class OpportunityDraftRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str
    interview_id: str
    schema_valid: bool
    payload: JsonObject
    created_at: datetime


class OpportunityRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    project_id: str
    work_model_version: int
    payload: JsonObject
    schema_valid: bool
    created_at: datetime


class DesignPackageRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    project_id: str
    opportunity_id: str
    work_model_version: int
    payload: JsonObject
    schema_valid: bool
    created_at: datetime


class BlueprintRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    project_id: str
    design_package_id: str
    payload: JsonObject
    schema_valid: bool
    export_ready: bool
    created_at: datetime


class EvaluationRunRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    project_id: str
    payload: JsonObject
    schema_valid: bool
    created_at: datetime


class ReleaseReadinessRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    project_id: str
    payload: JsonObject
    schema_valid: bool
    created_at: datetime


class EvidenceFileUpload(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: EvidenceFileRole
    filename: str = Field(min_length=1, max_length=200)
    content_type: str = Field(min_length=1, max_length=100)
    content_base64: str = Field(min_length=1)


class EvidenceFileConfirm(BaseModel):
    model_config = ConfigDict(frozen=True)

    confirmed: bool
    confirmed_by: str = Field(default="local-user", min_length=1, max_length=100)


class EvidenceFileRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    project_id: str
    role: EvidenceFileRole
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    content: bytes = Field(exclude=True, repr=False)
    extracted_schema: JsonObject
    sample_values: JsonObject
    confirmed: bool
    created_at: datetime


class EvidenceFileStoreCreate(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str
    role: EvidenceFileRole
    filename: str
    content_type: str
    content: bytes
    sha256: str
    extracted_schema: JsonObject
    sample_values: JsonObject


class ImplementationRequirementsCreate(BaseModel):
    model_config = ConfigDict(frozen=True)

    payload: JsonObject
    confirmed: bool = False


class ImplementationRequirementsRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    project_id: str
    payload: JsonObject
    confirmed: bool
    created_at: datetime


class ImplementationPackageRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    project_id: str
    blueprint_id: str
    payload: JsonObject
    schema_valid: bool
    readiness_status: ImplementationReadinessStatus
    created_at: datetime


class ImplementationPackageStoreCreate(BaseModel):
    model_config = ConfigDict(frozen=True)

    package_id: str
    project_id: str
    blueprint_id: str
    payload: JsonObject
    valid: bool
    readiness_status: ImplementationReadinessStatus


class CodegenReadinessRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    package_id: str
    project_id: str
    status: ImplementationReadinessStatus
    codegen_ready: bool
    blockers: tuple[str, ...]
    follow_up_questions: tuple[str, ...]
    checks: tuple[JsonObject, ...]
    evaluated_at: datetime


class OpportunityValidateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    accepted: bool = True
    notes: str = ""


class ReadinessRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str
    interview_id: str | None
    work_model_version: int | None
    ready_for_g1: bool
    result: str
    blocking_reasons: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    required_followups: tuple[str, ...]
    score_summary: JsonObject
    created_at: datetime


class DiscoveryDimensionRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    reason: str


class DiscoveryQuestionRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    dimension: str
    text: str
    source: str = "question-bank-v1"


class DiscoveryGuidanceRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str
    interview_id: str | None
    interview_status: InterviewStatus | None
    gate_result: str
    recovery_required: bool
    missing_dimensions: tuple[DiscoveryDimensionRead, ...]
    recommended_questions: tuple[DiscoveryQuestionRead, ...]
    suggested_evidence_prompt: str
    can_reopen: bool
    can_reanalyze: bool
    latest_work_model_version: int | None
    latest_opportunity_id: str | None
    latest_opportunity_work_model_version: int | None


class OpportunityDiffRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str
    previous_opportunity_id: str
    latest_opportunity_id: str
    score_changes: JsonObject
    gate_result_changed: bool
    previous_gate_result: str
    latest_gate_result: str
    added_evidence_refs: tuple[str, ...]
    removed_evidence_refs: tuple[str, ...]
    changed_blocked_reasons: tuple[str, ...]
    recommendation_changed: bool
    created_at: datetime


class WorkModelValidateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    payload: JsonObject


class ValidationRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    schema_name: str
    error: str | None = None
