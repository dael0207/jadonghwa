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
