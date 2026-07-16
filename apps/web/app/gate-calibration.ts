import type { Opportunity, Readiness } from "./api-client"

export type GateCalibration = {
  readonly gate: string
  readonly feasibility: string
  readonly evidenceConfidence: string
  readonly residualRisk: string
  readonly confirmedControls: readonly string[]
  readonly unresolvedItems: readonly string[]
  readonly safetyPolicies: readonly string[]
  readonly fullG1Status: string
}

export function gateCalibrationFrom(
  opportunity: Opportunity | null,
  readiness: Readiness | null,
): GateCalibration {
  const scores = recordValue(opportunity?.payload["scores"])
  const risk = recordValue(opportunity?.payload["risk_profile"])
  const gate = readiness?.result ?? stringValue(recordValue(opportunity?.payload["gate"])["result"])
  const confirmedControls = [
    ...stringArray(risk["controlled_risk_constraints"]),
    ...stringArray(risk["controlled_exceptions"]),
    ...stringArray(risk["authority_controls"]),
  ]
  const unresolvedItems = [
    ...stringArray(risk["unresolved_risk_constraints"]),
    ...stringArray(risk["unresolved_exceptions"]),
  ]
  return {
    gate: gate || "미분석",
    feasibility: displayValue(scores["feasibility"]),
    evidenceConfidence: displayValue(scores["evidence_confidence"]),
    residualRisk: displayValue(risk["residual_risk"] ?? scores["risk"]),
    confirmedControls,
    unresolvedItems,
    safetyPolicies: stringArray(risk["safety_policy_constraints"]),
    fullG1Status: fullG1Status(gate),
  }
}

function fullG1Status(gate: string): string {
  if (gate === "READY_FOR_DESIGN") {
    return "FULL_G1 및 FULL_G1_BLUEPRINT 생성 가능"
  }
  if (gate === "ENABLE_FIRST") {
    return "ENABLEMENT_PREP만 생성 가능"
  }
  return "Discovery recovery 완료 전 생성 차단"
}

function recordValue(value: unknown): Record<string, unknown> {
  if (isRecord(value)) {
    return value
  }
  return {}
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function stringArray(value: unknown): readonly string[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter((item): item is string => typeof item === "string" && item.length > 0)
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : ""
}

function displayValue(value: unknown): string {
  return typeof value === "number" || typeof value === "string" ? String(value) : "-"
}
