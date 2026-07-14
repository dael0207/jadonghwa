from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from work_discovery_api.domain import AnswerStatus, InterviewStatus

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
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


class WorkModelValidateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    payload: JsonObject


class ValidationRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    schema_name: str
    error: str | None = None
