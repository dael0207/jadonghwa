from __future__ import annotations

from typing import Protocol

from work_discovery_api.domain import (
    AuditAction,
    InterviewStatus,
)
from work_discovery_api.models import (
    AnswerCreate,
    AnswerRead,
    AnswerRevisionCreate,
    AuditEventRead,
    BlueprintRead,
    ConsentRequest,
    DesignPackageRead,
    EvaluationRunRead,
    EvidenceCreate,
    EvidenceFileConfirm,
    EvidenceFileRead,
    EvidenceFileStoreCreate,
    ImplementationPackageRead,
    ImplementationPackageStoreCreate,
    ImplementationRequirementsRead,
    InterviewRead,
    JsonObject,
    OpportunityRead,
    ProjectRead,
    QuestionRead,
    ReleaseReadinessRead,
    WorkModelRead,
)


class WorkDiscoveryRepository(Protocol):
    def create_project(self, name: str, workspace_name: str) -> ProjectRead: ...
    def require_project(self, project_id: str) -> ProjectRead: ...
    def create_interview(
        self,
        project_id: str,
        questions: tuple[QuestionRead, ...],
    ) -> InterviewRead: ...
    def get_interview(self, interview_id: str) -> InterviewRead: ...
    def list_project_interviews(self, project_id: str) -> tuple[InterviewRead, ...]: ...
    def grant_consent(self, interview_id: str, consent: ConsentRequest) -> InterviewRead: ...
    def revoke_consent(self, interview_id: str) -> InterviewRead: ...
    def get_questions(self, interview_id: str) -> tuple[QuestionRead, ...]: ...
    def record_answer(self, interview_id: str, answer: AnswerCreate) -> AnswerRead: ...
    def record_evidence(self, interview_id: str, evidence: EvidenceCreate) -> AnswerRead: ...
    def revise_answer(
        self,
        interview_id: str,
        answer_id: str,
        revision: AnswerRevisionCreate,
    ) -> AnswerRead: ...
    def list_answers(self, interview_id: str) -> tuple[AnswerRead, ...]: ...
    def get_work_model(self, project_id: str) -> WorkModelRead: ...
    def get_work_model_version(self, project_id: str, version: int) -> WorkModelRead: ...
    def get_interview_work_model(self, interview_id: str) -> WorkModelRead: ...
    def list_work_models(self, project_id: str) -> tuple[WorkModelRead, ...]: ...
    def replace_work_model(
        self,
        project_id: str,
        payload: JsonObject,
        valid: bool,
    ) -> WorkModelRead: ...
    def save_opportunity(
        self,
        project_id: str,
        work_model_version: int,
        payload: JsonObject,
        valid: bool,
    ) -> OpportunityRead: ...
    def get_opportunity(self, opportunity_id: str) -> OpportunityRead: ...
    def list_opportunities(self, project_id: str) -> tuple[OpportunityRead, ...]: ...
    def save_design_package(
        self,
        project_id: str,
        opportunity_id: str,
        work_model_version: int,
        payload: JsonObject,
        valid: bool,
    ) -> DesignPackageRead: ...
    def get_design_package(self, package_id: str) -> DesignPackageRead: ...
    def list_project_design_packages(self, project_id: str) -> tuple[DesignPackageRead, ...]: ...
    def list_opportunity_design_packages(
        self,
        opportunity_id: str,
    ) -> tuple[DesignPackageRead, ...]: ...
    def save_blueprint(
        self,
        project_id: str,
        design_package_id: str,
        payload: JsonObject,
        valid: bool,
        export_ready: bool,
    ) -> BlueprintRead: ...
    def get_blueprint(self, blueprint_id: str) -> BlueprintRead: ...
    def list_project_blueprints(self, project_id: str) -> tuple[BlueprintRead, ...]: ...
    def list_design_package_blueprints(
        self,
        design_package_id: str,
    ) -> tuple[BlueprintRead, ...]: ...
    def save_evaluation_run(
        self,
        project_id: str,
        payload: JsonObject,
        valid: bool,
    ) -> EvaluationRunRead: ...
    def get_evaluation_run(self, run_id: str) -> EvaluationRunRead: ...
    def list_project_evaluation_runs(self, project_id: str) -> tuple[EvaluationRunRead, ...]: ...
    def save_release_readiness_report(
        self,
        project_id: str,
        payload: JsonObject,
        valid: bool,
    ) -> ReleaseReadinessRead: ...
    def get_release_readiness_report(self, report_id: str) -> ReleaseReadinessRead: ...
    def list_project_release_readiness_reports(
        self,
        project_id: str,
    ) -> tuple[ReleaseReadinessRead, ...]: ...
    def save_evidence_file(self, payload: EvidenceFileStoreCreate) -> EvidenceFileRead: ...
    def confirm_evidence_file(
        self,
        evidence_file_id: str,
        confirmation: EvidenceFileConfirm,
    ) -> EvidenceFileRead: ...
    def get_evidence_file(self, evidence_file_id: str) -> EvidenceFileRead: ...
    def list_project_evidence_files(self, project_id: str) -> tuple[EvidenceFileRead, ...]: ...
    def save_implementation_requirements(
        self,
        project_id: str,
        payload: JsonObject,
        confirmed: bool,
    ) -> ImplementationRequirementsRead: ...
    def get_latest_implementation_requirements(
        self,
        project_id: str,
    ) -> ImplementationRequirementsRead | None: ...
    def save_implementation_package(
        self,
        payload: ImplementationPackageStoreCreate,
    ) -> ImplementationPackageRead: ...
    def get_implementation_package(self, package_id: str) -> ImplementationPackageRead: ...
    def list_project_implementation_packages(
        self,
        project_id: str,
    ) -> tuple[ImplementationPackageRead, ...]: ...
    def transition_interview(
        self,
        interview_id: str,
        target: InterviewStatus,
    ) -> InterviewRead: ...
    def reopen_interview_for_discovery(self, interview_id: str) -> InterviewRead: ...
    def record_audit(
        self,
        subject_id: str,
        action: AuditAction,
        metadata: JsonObject,
    ) -> AuditEventRead: ...
    def list_interview_audit_events(self, interview_id: str) -> tuple[AuditEventRead, ...]: ...
    def list_project_audit_events(self, project_id: str) -> tuple[AuditEventRead, ...]: ...
