"use client"

import ky, { HTTPError } from "ky"

export type AnswerStatus = "ANSWERED" | "UNKNOWN" | "SKIPPED"

export type Project = {
  readonly id: string
  readonly name: string
}

export type Interview = {
  readonly id: string
  readonly project_id: string
  readonly status: string
  readonly active_consent: boolean
  readonly answered_count: number
}

export type Question = {
  readonly id: string
  readonly text: string
  readonly stage: string
  readonly dimension: string
  readonly position: number
}

export type WorkModel = {
  readonly version: number
  readonly schema_valid: boolean
  readonly payload: Record<string, unknown>
}

export type Answer = {
  readonly id: string
  readonly turn_id: string
  readonly question_id: string
  readonly text: string
  readonly status: AnswerStatus
  readonly revision_of: string | null
  readonly source_refs: readonly string[]
  readonly created_at: string
}

export type CoverageItem = {
  readonly key: string
  readonly label: string
  readonly status: string
  readonly evidence_count: number
  readonly question_ids: readonly string[]
}

export type Coverage = {
  readonly interview_id: string
  readonly covered_count: number
  readonly total_count: number
  readonly items: readonly CoverageItem[]
}

export type NextQuestion = {
  readonly interview_id: string
  readonly complete: boolean
  readonly coverage_key: string | null
  readonly question_id: string | null
  readonly text: string | null
  readonly reason: string
}

export type OpportunityDraft = {
  readonly project_id: string
  readonly interview_id: string
  readonly schema_valid: boolean
  readonly payload: Record<string, unknown>
  readonly created_at: string
}

export type Opportunity = {
  readonly id: string
  readonly project_id: string
  readonly work_model_version: number
  readonly payload: Record<string, unknown>
  readonly schema_valid: boolean
  readonly created_at: string
}

export type DesignPackage = {
  readonly id: string
  readonly project_id: string
  readonly opportunity_id: string
  readonly work_model_version: number
  readonly payload: Record<string, unknown>
  readonly schema_valid: boolean
  readonly created_at: string
}

export type Blueprint = {
  readonly id: string
  readonly project_id: string
  readonly design_package_id: string
  readonly payload: Record<string, unknown>
  readonly schema_valid: boolean
  readonly export_ready: boolean
  readonly created_at: string
}

export type EvaluationRun = {
  readonly id: string
  readonly project_id: string
  readonly payload: Record<string, unknown>
  readonly schema_valid: boolean
  readonly created_at: string
}

export type ReleaseReadinessReport = {
  readonly id: string
  readonly project_id: string
  readonly payload: Record<string, unknown>
  readonly schema_valid: boolean
  readonly created_at: string
}

export type Readiness = {
  readonly project_id: string
  readonly interview_id: string | null
  readonly work_model_version: number | null
  readonly ready_for_g1: boolean
  readonly result: string
  readonly blocking_reasons: readonly string[]
  readonly missing_evidence: readonly string[]
  readonly required_followups: readonly string[]
  readonly score_summary: Record<string, unknown>
  readonly created_at: string
}

export type OpportunityDiff = {
  readonly project_id: string
  readonly previous_opportunity_id: string
  readonly latest_opportunity_id: string
  readonly score_changes: Record<string, unknown>
  readonly gate_result_changed: boolean
  readonly previous_gate_result: string
  readonly latest_gate_result: string
  readonly added_evidence_refs: readonly string[]
  readonly removed_evidence_refs: readonly string[]
  readonly changed_blocked_reasons: readonly string[]
  readonly recommendation_changed: boolean
  readonly created_at: string
}

export type ValidationResult = {
  readonly valid: boolean
  readonly schema_name: string
  readonly error: string | null
}

export type AuditEvent = {
  readonly id: string
  readonly action: string
  readonly created_at: string
}

type ErrorBody = {
  readonly detail?: string
}

export const api = ky.create({
  prefixUrl: process.env["NEXT_PUBLIC_API_BASE_URL"] ?? "http://127.0.0.1:8000",
})

export async function errorMessage(caught: unknown): Promise<string> {
  if (caught instanceof HTTPError) {
    const body = await caught.response.json<ErrorBody>()
    return body.detail ?? caught.message
  }
  if (caught instanceof Error) {
    return caught.message
  }
  return "알 수 없는 오류가 발생했습니다."
}
