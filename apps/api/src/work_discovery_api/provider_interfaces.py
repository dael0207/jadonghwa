from __future__ import annotations

from typing import Protocol

from work_discovery_api.models import (
    AnswerRead,
    JsonObject,
    NextQuestionRead,
    QuestionRead,
    WorkModelRead,
)
from work_discovery_api.work_model_builder import WorkModelBuildInput


class SpeechToTextProvider(Protocol):
    def transcribe(self, audio_uri: str) -> str: ...


class LlmWorkModelProvider(Protocol):
    def build(self, source: WorkModelBuildInput) -> JsonObject: ...


class AdaptiveQuestionProvider(Protocol):
    def next_question(
        self,
        interview_id: str,
        questions: tuple[QuestionRead, ...],
        answers: tuple[AnswerRead, ...],
    ) -> NextQuestionRead: ...


class OpportunityAnalysisProvider(Protocol):
    def draft(self, work_model: WorkModelRead) -> JsonObject: ...
