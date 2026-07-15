from __future__ import annotations

from dataclasses import dataclass

from work_discovery_api.models import JsonObject, WorkModelRead
from work_discovery_api.opportunity_payload import build_opportunity_payload
from work_discovery_api.opportunity_scoring import score_profile
from work_discovery_api.work_model_evidence import evidence_profile


@dataclass(frozen=True, slots=True)
class OpportunityAnalysisInput:
    work_model: WorkModelRead


class DeterministicOpportunityAnalyzer:
    def draft(self, source: OpportunityAnalysisInput) -> JsonObject:
        profile = evidence_profile(source.work_model)
        decision = score_profile(profile)
        return build_opportunity_payload(profile, decision)
