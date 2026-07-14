"use client"

import { useState } from "react"

import { api, errorMessage, type AnswerStatus, type AuditEvent, type Interview, type Project, type Question, type WorkModel } from "./api-client"

export default function Page() {
  const [projectName, setProjectName] = useState("월간 보고 업무")
  const [project, setProject] = useState<Project | null>(null)
  const [interview, setInterview] = useState<Interview | null>(null)
  const [questions, setQuestions] = useState<readonly Question[]>([])
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [statuses, setStatuses] = useState<Record<string, AnswerStatus>>({})
  const [workModel, setWorkModel] = useState<WorkModel | null>(null)
  const [auditEvents, setAuditEvents] = useState<readonly AuditEvent[]>([])
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")

  async function run(action: () => Promise<void>) {
    setError("")
    setMessage("")
    try {
      await action()
    } catch (caught) {
      setError(await errorMessage(caught))
    }
  }

  async function createFlow() {
    await run(async () => {
      const created = await api.post("v1/projects", { json: { name: projectName } }).json<Project>()
      const session = await api.post(`v1/projects/${created.id}/interviews`).json<Interview>()
      const loadedQuestions = await api.get(`v1/interviews/${session.id}/questions`).json<Question[]>()
      setProject(created)
      setInterview(session)
      setQuestions(loadedQuestions)
      setWorkModel(null)
      setAuditEvents([])
      setMessage("프로젝트와 인터뷰를 만들었습니다.")
    })
  }

  async function grantConsent() {
    if (!interview) return
    await run(async () => {
      const next = await api
        .post(`v1/interviews/${interview.id}/consent`, {
          json: { ai_processing: true, data_processing: true },
        })
        .json<Interview>()
      setInterview(next)
      await refreshAudit(next.project_id)
      setMessage("동의가 기록되었습니다.")
    })
  }

  async function revokeConsent() {
    if (!interview) return
    await run(async () => {
      const next = await api.post(`v1/interviews/${interview.id}/consent/revoke`).json<Interview>()
      setInterview(next)
      await refreshAudit(next.project_id)
      setMessage("동의가 철회되었습니다.")
    })
  }

  async function submitAnswer(question: Question) {
    if (!interview) return
    await run(async () => {
      await api.post(`v1/interviews/${interview.id}/answers`, {
        json: {
          question_id: question.id,
          text: answers[question.id] ?? "",
          status: statuses[question.id] ?? "ANSWERED",
        },
      })
      const next = await api.get(`v1/interviews/${interview.id}`).json<Interview>()
      setInterview(next)
      await refreshAudit(next.project_id)
      setMessage(`${question.position}번 답변을 저장했습니다.`)
    })
  }

  async function buildWorkModel() {
    if (!interview) return
    await run(async () => {
      const model = await api.post(`v1/interviews/${interview.id}/build-work-model`).json<WorkModel>()
      const next = await api.get(`v1/interviews/${interview.id}`).json<Interview>()
      setWorkModel(model)
      setInterview(next)
      await refreshAudit(next.project_id)
      setMessage("Work Model 초안을 생성했습니다.")
    })
  }

  async function confirmPlayback() {
    if (!interview) return
    await run(async () => {
      const next = await api.post(`v1/interviews/${interview.id}/playback/confirm`).json<Interview>()
      const model = await api.get(`v1/interviews/${interview.id}/work-model`).json<WorkModel>()
      setInterview(next)
      setWorkModel(model)
      await refreshAudit(next.project_id)
      setMessage("Playback을 승인해 FINALIZED 상태가 되었습니다.")
    })
  }

  async function rejectPlayback() {
    if (!interview) return
    await run(async () => {
      const next = await api.post(`v1/interviews/${interview.id}/playback/reject`).json<Interview>()
      const model = await api.get(`v1/interviews/${interview.id}/work-model`).json<WorkModel>()
      setInterview(next)
      setWorkModel(model)
      await refreshAudit(next.project_id)
      setMessage("Playback을 거절해 NEEDS_EVIDENCE 상태가 되었습니다.")
    })
  }

  async function refreshAudit(projectId: string) {
    const events = await api.get(`v1/projects/${projectId}/audit-events`).json<AuditEvent[]>()
    setAuditEvents(events)
  }

  return (
    <main className="shell">
      <header className="header">
        <h1>Work Discovery AI</h1>
        <p>M1/M2 검증용 인터뷰 작업 화면</p>
      </header>
      <div className="grid">
        <section className="panel stack">
          <h2>1. 프로젝트</h2>
          <label>
            <span className="muted">프로젝트 이름</span>
            <input value={projectName} onChange={(event) => setProjectName(event.target.value)} />
          </label>
          <button onClick={createFlow}>프로젝트와 인터뷰 생성</button>
          <Status project={project} interview={interview} />
          <div className="cluster">
            <button onClick={grantConsent} disabled={!interview || interview.active_consent}>
              동의하기
            </button>
            <button className="danger" onClick={revokeConsent} disabled={!interview}>
              동의 철회
            </button>
          </div>
          {message ? <p className="success">{message}</p> : null}
          {error ? <p className="error panel">{error}</p> : null}
        </section>

        <section className="panel stack">
          <h2>2. 질문 10개</h2>
          {questions.length === 0 ? <p className="muted">인터뷰를 생성하면 질문이 표시됩니다.</p> : null}
          {questions.map((question) => (
            <div className="question stack" key={question.id}>
              <strong>
                {question.position}. {question.text}
              </strong>
              <span className="muted">
                {question.stage} · {question.dimension}
              </span>
              <select
                value={statuses[question.id] ?? "ANSWERED"}
                onChange={(event) =>
                  setStatuses({ ...statuses, [question.id]: event.target.value as AnswerStatus })
                }
              >
                <option value="ANSWERED">답변</option>
                <option value="UNKNOWN">모름</option>
                <option value="SKIPPED">건너뛰기</option>
              </select>
              <textarea
                value={answers[question.id] ?? ""}
                onChange={(event) => setAnswers({ ...answers, [question.id]: event.target.value })}
              />
              <button onClick={() => submitAnswer(question)} disabled={!interview?.active_consent}>
                답변 저장
              </button>
            </div>
          ))}
        </section>

        <section className="panel stack">
          <h2>3. Work Model</h2>
          <button onClick={buildWorkModel} disabled={interview?.status !== "MODEL_BUILDING"}>
            Work Model 생성
          </button>
          <div className="cluster">
            <button onClick={confirmPlayback} disabled={interview?.status !== "PLAYBACK_CONFIRMATION"}>
              Playback 승인
            </button>
            <button
              className="secondary"
              onClick={rejectPlayback}
              disabled={interview?.status !== "PLAYBACK_CONFIRMATION"}
            >
              Playback 거절
            </button>
          </div>
          <pre>{workModel ? JSON.stringify(workModel.payload, null, 2) : "아직 생성된 모델이 없습니다."}</pre>
        </section>

        <section className="panel stack">
          <h2>4. Audit events</h2>
          {auditEvents.length === 0 ? <p className="muted">아직 표시할 감사 이벤트가 없습니다.</p> : null}
          {auditEvents.map((event) => (
            <p key={event.id}>
              <span className="status">{event.action}</span> <span className="muted">{event.created_at}</span>
            </p>
          ))}
        </section>
      </div>
    </main>
  )
}

function Status({ project, interview }: { readonly project: Project | null; readonly interview: Interview | null }) {
  return (
    <div className="stack">
      <p>
        프로젝트: <strong>{project?.name ?? "없음"}</strong>
      </p>
      <p>
        상태: <span className="status">{interview?.status ?? "미생성"}</span>
      </p>
      <p className="muted">답변 수: {interview?.answered_count ?? 0} / 10</p>
    </div>
  )
}
