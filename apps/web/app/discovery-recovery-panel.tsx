"use client"

import { useEffect, useState } from "react"

import {
  api,
  errorMessage,
  type DiscoveryGuidance,
  type Interview,
  type Opportunity,
  type Project,
  type Readiness,
} from "./api-client"

type DiscoveryRecoveryPanelProps = {
  readonly project: Project | null
  readonly interview: Interview | null
  readonly latestOpportunity: Opportunity | null
  readonly readiness: Readiness | null
  readonly onWorkflowChanged: () => Promise<void>
}

export function DiscoveryRecoveryPanel(props: DiscoveryRecoveryPanelProps) {
  const [guidance, setGuidance] = useState<DiscoveryGuidance | null>(null)
  const [evidenceText, setEvidenceText] = useState("")
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let active = true
    if (!props.project || !props.latestOpportunity) {
      setGuidance(null)
      return () => {
        active = false
      }
    }
    void api
      .get(`v1/projects/${props.project.id}/discovery-guidance`)
      .json<DiscoveryGuidance>()
      .then((body) => {
        if (active) setGuidance(body)
      })
      .catch(async (caught: unknown) => {
        if (active) setError(await errorMessage(caught))
      })
    return () => {
      active = false
    }
  }, [props.interview?.status, props.latestOpportunity?.id, props.project, props.readiness?.result])

  async function execute(action: () => Promise<void>, success: string) {
    setBusy(true)
    setError("")
    setMessage("")
    try {
      await action()
      await props.onWorkflowChanged()
      setMessage(success)
    } catch (caught) {
      setError(await errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  async function reopen() {
    if (!props.project) return
    await execute(
      async () => {
        await api.post(`v1/projects/${props.project?.id}/discovery/reopen`)
      },
      "추가 발견을 시작했습니다. 증거를 보완하세요.",
    )
  }

  async function saveEvidence() {
    if (!props.interview) return
    await execute(
      async () => {
        await api.post(`v1/interviews/${props.interview?.id}/evidence`, {
          json: { text: evidenceText },
        })
        setEvidenceText("")
      },
      "추가 증거를 불변 turn으로 저장했습니다.",
    )
  }

  async function resumeBuild() {
    if (!props.interview) return
    await execute(
      async () => {
        await api.post(`v1/interviews/${props.interview?.id}/resume-model-building`)
      },
      "MODEL_BUILDING으로 전환했습니다. 위의 Work Model 생성 버튼을 사용하세요.",
    )
  }

  async function reanalyze() {
    if (!props.project) return
    await execute(
      async () => {
        await api.post(`v1/projects/${props.project?.id}/discovery/reanalyze`)
      },
      "새 Work Model 버전으로 opportunity를 재분석했습니다.",
    )
  }

  const needsEvidence = props.interview?.status === "NEEDS_EVIDENCE"
  const recoveryRequired = guidance?.recovery_required ?? false
  return (
    <section className="panel stack wide">
      <h2>5.1 Discovery recovery</h2>
      <div className="metric-grid">
        <p className="metric">
          <strong>Gate</strong>
          <span className="status">{guidance?.gate_result ?? props.readiness?.result ?? "미분석"}</span>
        </p>
        <p className="metric">
          <strong>Interview</strong>
          <span className="status">{props.interview?.status ?? "없음"}</span>
        </p>
        <p className="metric">
          <strong>Recovery</strong>
          <span className={recoveryRequired ? "error" : "success"}>
            {recoveryRequired ? "추가 발견 필요" : "추가 발견 불필요"}
          </span>
        </p>
      </div>
      {recoveryRequired ? (
        <>
          <div className="coverage-grid">
            {guidance?.missing_dimensions.map((dimension) => (
              <p className="coverage-item" key={dimension.key}>
                <strong>{dimension.label}</strong>
                <span className="muted">{dimension.reason}</span>
              </p>
            ))}
          </div>
          <div className="stack list-block">
            <strong>권장 추가 질문</strong>
            {guidance?.recommended_questions.map((question) => (
              <p className="list-row" key={question.id}>
                <span className="status">{question.dimension}</span>
                <span>{question.text}</span>
              </p>
            ))}
          </div>
          <p className="muted">{guidance?.suggested_evidence_prompt}</p>
          <label>
            <span className="muted">추가 증거</span>
            <textarea
              value={evidenceText}
              onChange={(event) => setEvidenceText(event.target.value)}
              placeholder={RECOVERY_TEMPLATE}
              disabled={!needsEvidence || busy}
            />
          </label>
          <div className="cluster">
            <button onClick={reopen} disabled={!guidance?.can_reopen || busy}>
              복구 시작
            </button>
            <button onClick={saveEvidence} disabled={!needsEvidence || !evidenceText.trim() || busy}>
              추가 증거 저장
            </button>
            <button onClick={resumeBuild} disabled={!needsEvidence || busy}>
              Work Model 재생성 준비
            </button>
            <button onClick={reanalyze} disabled={!guidance?.can_reanalyze || busy}>
              Opportunity 재분석
            </button>
          </div>
          <p className="muted">
            재분석 전 Work Model 생성과 Playback 승인을 완료해야 합니다.
          </p>
        </>
      ) : (
        <p className="muted">현재 gate에서는 추가 발견 루프가 필요하지 않습니다.</p>
      )}
      {message ? <p className="success">{message}</p> : null}
      {error ? <p className="error">{error}</p> : null}
    </section>
  )
}

const RECOVERY_TEMPLATE = `시스템/도구:
입력:
출력:
규칙/판단 기준:
예외/복구:
승인/권한:
성과지표:
비범위:
근거:`
