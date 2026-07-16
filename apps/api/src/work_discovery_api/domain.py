from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import assert_never


class InterviewStatus(StrEnum):
    CREATED = "CREATED"
    CONSENT_PENDING = "CONSENT_PENDING"
    CONSENTED = "CONSENTED"
    INTAKE_IN_PROGRESS = "INTAKE_IN_PROGRESS"
    MODEL_BUILDING = "MODEL_BUILDING"
    PLAYBACK_CONFIRMATION = "PLAYBACK_CONFIRMATION"
    OPPORTUNITY_ANALYSIS_READY = "OPPORTUNITY_ANALYSIS_READY"
    FINALIZED = "FINALIZED"
    PAUSED = "PAUSED"
    NEEDS_EVIDENCE = "NEEDS_EVIDENCE"
    CONSENT_REVOKED = "CONSENT_REVOKED"
    DELETION_PENDING = "DELETION_PENDING"
    ABORTED = "ABORTED"


class AnswerStatus(StrEnum):
    ANSWERED = "ANSWERED"
    UNKNOWN = "UNKNOWN"
    SKIPPED = "SKIPPED"


class AuditAction(StrEnum):
    PROJECT_CREATED = "PROJECT_CREATED"
    INTERVIEW_CREATED = "INTERVIEW_CREATED"
    CONSENT_GRANTED = "CONSENT_GRANTED"
    CONSENT_REVOKED = "CONSENT_REVOKED"
    ANSWER_RECORDED = "ANSWER_RECORDED"
    WORK_MODEL_VALIDATED = "WORK_MODEL_VALIDATED"
    WORK_MODEL_BUILT = "WORK_MODEL_BUILT"
    WORK_MODEL_REBUILD_REQUESTED = "WORK_MODEL_REBUILD_REQUESTED"
    WORK_MODEL_REBUILT = "WORK_MODEL_REBUILT"
    PLAYBACK_CONFIRMED = "PLAYBACK_CONFIRMED"
    PLAYBACK_REJECTED = "PLAYBACK_REJECTED"
    EVIDENCE_ADDED = "EVIDENCE_ADDED"
    ANSWER_REVISED = "ANSWER_REVISED"
    OPPORTUNITY_DRAFT_GENERATED = "OPPORTUNITY_DRAFT_GENERATED"
    OPPORTUNITY_ANALYZED = "OPPORTUNITY_ANALYZED"
    OPPORTUNITY_VALIDATED = "OPPORTUNITY_VALIDATED"
    READINESS_EVALUATED = "READINESS_EVALUATED"
    OPPORTUNITY_DIFF_GENERATED = "OPPORTUNITY_DIFF_GENERATED"
    DISCOVERY_REOPENED = "DISCOVERY_REOPENED"
    DISCOVERY_REANALYZED = "DISCOVERY_REANALYZED"
    DESIGN_PACKAGE_CREATED = "DESIGN_PACKAGE_CREATED"
    DESIGN_PACKAGE_VALIDATED = "DESIGN_PACKAGE_VALIDATED"
    BLUEPRINT_CREATED = "BLUEPRINT_CREATED"
    BLUEPRINT_VALIDATED = "BLUEPRINT_VALIDATED"
    BLUEPRINT_EXPORTED = "BLUEPRINT_EXPORTED"
    EVALUATION_RUN_CREATED = "EVALUATION_RUN_CREATED"
    EVALUATION_RUN_VALIDATED = "EVALUATION_RUN_VALIDATED"
    RELEASE_READINESS_CREATED = "RELEASE_READINESS_CREATED"
    RELEASE_READINESS_VALIDATED = "RELEASE_READINESS_VALIDATED"


@dataclass(frozen=True, slots=True)
class InvalidTransitionError(Exception):
    current: InterviewStatus
    target: InterviewStatus

    def __str__(self) -> str:
        return f"invalid transition from {self.current} to {self.target}"


@dataclass(frozen=True, slots=True)
class ConsentRequiredError(Exception):
    interview_id: str

    def __str__(self) -> str:
        return f"interview {self.interview_id} requires active consent"


def allowed_targets(current: InterviewStatus) -> frozenset[InterviewStatus]:
    match current:
        case InterviewStatus.CREATED:
            return frozenset({InterviewStatus.CONSENT_PENDING})
        case InterviewStatus.CONSENT_PENDING:
            return frozenset({InterviewStatus.CONSENTED, InterviewStatus.ABORTED})
        case InterviewStatus.CONSENTED:
            return frozenset({InterviewStatus.INTAKE_IN_PROGRESS, InterviewStatus.CONSENT_REVOKED})
        case InterviewStatus.INTAKE_IN_PROGRESS:
            return frozenset(
                {
                    InterviewStatus.MODEL_BUILDING,
                    InterviewStatus.PAUSED,
                    InterviewStatus.CONSENT_REVOKED,
                },
            )
        case InterviewStatus.MODEL_BUILDING:
            return frozenset(
                {
                    InterviewStatus.PLAYBACK_CONFIRMATION,
                    InterviewStatus.NEEDS_EVIDENCE,
                    InterviewStatus.CONSENT_REVOKED,
                },
            )
        case InterviewStatus.PLAYBACK_CONFIRMATION:
            return frozenset(
                {
                    InterviewStatus.OPPORTUNITY_ANALYSIS_READY,
                    InterviewStatus.NEEDS_EVIDENCE,
                    InterviewStatus.CONSENT_REVOKED,
                },
            )
        case InterviewStatus.OPPORTUNITY_ANALYSIS_READY:
            return frozenset({InterviewStatus.FINALIZED})
        case InterviewStatus.PAUSED:
            return frozenset({InterviewStatus.INTAKE_IN_PROGRESS, InterviewStatus.CONSENT_REVOKED})
        case InterviewStatus.NEEDS_EVIDENCE:
            return frozenset(
                {
                    InterviewStatus.INTAKE_IN_PROGRESS,
                    InterviewStatus.MODEL_BUILDING,
                    InterviewStatus.PAUSED,
                },
            )
        case InterviewStatus.CONSENT_REVOKED:
            return frozenset({InterviewStatus.DELETION_PENDING})
        case InterviewStatus.DELETION_PENDING | InterviewStatus.ABORTED | InterviewStatus.FINALIZED:
            return frozenset()
        case unreachable:
            assert_never(unreachable)


def transition(current: InterviewStatus, target: InterviewStatus) -> InterviewStatus:
    if target in allowed_targets(current):
        return target
    raise InvalidTransitionError(current=current, target=target)


def reopen_for_discovery(current: InterviewStatus) -> InterviewStatus:
    recoverable = frozenset(
        {
            InterviewStatus.PLAYBACK_CONFIRMATION,
            InterviewStatus.OPPORTUNITY_ANALYSIS_READY,
            InterviewStatus.FINALIZED,
        },
    )
    if current in recoverable:
        return InterviewStatus.NEEDS_EVIDENCE
    raise InvalidTransitionError(current=current, target=InterviewStatus.NEEDS_EVIDENCE)


def can_accept_answer(status: InterviewStatus, active_consent: bool) -> bool:
    if not active_consent:
        return False
    return status == InterviewStatus.INTAKE_IN_PROGRESS


def can_accept_evidence(status: InterviewStatus, active_consent: bool) -> bool:
    if not active_consent:
        return False
    return status == InterviewStatus.NEEDS_EVIDENCE
