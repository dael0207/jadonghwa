"use client"

import type {
  Answer,
  AnswerStatus,
  AuditEvent,
  Coverage,
  Interview,
  NextQuestion,
  OpportunityDraft,
  Project,
  Question,
  WorkModel,
} from "./api-client"

export function answerStatus(value: string): AnswerStatus {
  if (value === "UNKNOWN" || value === "SKIPPED") {
    return value
  }
  return "ANSWERED"
}

type ProjectPanelProps = {
  readonly projectName: string
  readonly project: Project | null
  readonly interview: Interview | null
  readonly message: string
  readonly error: string
  readonly onProjectName: (value: string) => void
  readonly onCreateFlow: () => void
  readonly onGrantConsent: () => void
  readonly onRevokeConsent: () => void
}

export function ProjectPanel(props: ProjectPanelProps) {
  return (
    <section className="panel stack">
      <h2>1. 프로젝트</h2>
      <label>
        <span className="muted">프로젝트 이름</span>
        <input value={props.projectName} onChange={(event) => props.onProjectName(event.target.value)} />
      </label>
      <button onClick={props.onCreateFlow}>프로젝트와 인터뷰 생성</button>
      <Status project={props.project} interview={props.interview} />
      <div className="cluster">
        <button onClick={props.onGrantConsent} disabled={!props.interview || props.interview.active_consent}>
          동의하기
        </button>
        <button className="danger" onClick={props.onRevokeConsent} disabled={!props.interview}>
          동의 철회
        </button>
      </div>
      {props.message ? <p className="success">{props.message}</p> : null}
      {props.error ? <p className="error">{props.error}</p> : null}
    </section>
  )
}

type QuestionsPanelProps = {
  readonly interview: Interview | null
  readonly questions: readonly Question[]
  readonly answers: Readonly<Record<string, string>>
  readonly statuses: Readonly<Record<string, AnswerStatus>>
  readonly onAnswer: (questionId: string, text: string) => void
  readonly onStatus: (questionId: string, status: AnswerStatus) => void
  readonly onSubmitAnswer: (question: Question) => void
}

export function QuestionsPanel(props: QuestionsPanelProps) {
  return (
    <section className="panel stack">
      <h2>2. 질문 10개</h2>
      {props.questions.length === 0 ? <p className="muted">인터뷰를 생성하면 질문이 표시됩니다.</p> : null}
      {props.questions.map((question) => (
        <div className="question stack" key={question.id}>
          <strong>
            {question.position}. {question.text}
          </strong>
          <span className="muted">
            {question.stage} · {question.dimension}
          </span>
          <select
            value={props.statuses[question.id] ?? "ANSWERED"}
            onChange={(event) => props.onStatus(question.id, answerStatus(event.target.value))}
          >
            <option value="ANSWERED">답변</option>
            <option value="UNKNOWN">모름</option>
            <option value="SKIPPED">건너뛰기</option>
          </select>
          <textarea
            value={props.answers[question.id] ?? ""}
            onChange={(event) => props.onAnswer(question.id, event.target.value)}
          />
          <button onClick={() => props.onSubmitAnswer(question)} disabled={!props.interview?.active_consent}>
            답변 저장
          </button>
        </div>
      ))}
    </section>
  )
}

type WorkModelPanelProps = {
  readonly interview: Interview | null
  readonly workModel: WorkModel | null
  readonly onBuildWorkModel: () => void
  readonly onConfirmPlayback: () => void
  readonly onRejectPlayback: () => void
}

export function WorkModelPanel(props: WorkModelPanelProps) {
  return (
    <section className="panel stack">
      <h2>3. Work Model</h2>
      <button onClick={props.onBuildWorkModel} disabled={props.interview?.status !== "MODEL_BUILDING"}>
        Work Model 생성
      </button>
      <div className="cluster">
        <button
          onClick={props.onConfirmPlayback}
          disabled={props.interview?.status !== "PLAYBACK_CONFIRMATION"}
        >
          Playback 승인
        </button>
        <button
          className="secondary"
          onClick={props.onRejectPlayback}
          disabled={props.interview?.status !== "PLAYBACK_CONFIRMATION"}
        >
          Playback 거절
        </button>
      </div>
      <pre>{props.workModel ? JSON.stringify(props.workModel.payload, null, 2) : "아직 생성된 모델이 없습니다."}</pre>
    </section>
  )
}

type M3PanelProps = {
  readonly interview: Interview | null
  readonly answerHistory: readonly Answer[]
  readonly evidenceText: string
  readonly revisionAnswerId: string
  readonly revisionText: string
  readonly coverage: Coverage | null
  readonly nextQuestion: NextQuestion | null
  readonly opportunityDraft: OpportunityDraft | null
  readonly workModels: readonly WorkModel[]
  readonly onEvidenceText: (value: string) => void
  readonly onRevisionAnswerId: (value: string) => void
  readonly onRevisionText: (value: string) => void
  readonly onAddEvidence: () => void
  readonly onReviseAnswer: () => void
  readonly onResumeModelBuilding: () => void
  readonly onRefreshCoverage: () => void
  readonly onLoadOpportunity: () => void
}

export function M3Panel(props: M3PanelProps) {
  const needsEvidence = props.interview?.status === "NEEDS_EVIDENCE"
  return (
    <section className="panel stack wide">
      <h2>4. M3 루프</h2>
      <div className="cluster">
        <button onClick={props.onRefreshCoverage} disabled={!props.interview}>
          Coverage / Next question
        </button>
        <button onClick={props.onResumeModelBuilding} disabled={!needsEvidence}>
          재빌드 재개
        </button>
        <button onClick={props.onLoadOpportunity} disabled={!props.interview}>
          Opportunity draft
        </button>
      </div>
      <div className="coverage-grid">
        {props.coverage?.items.map((item) => (
          <p className="coverage-item" key={item.key}>
            <strong>{item.label}</strong>
            <span className="status">{item.status}</span>
            <span className="muted">근거 {item.evidence_count}</span>
          </p>
        ))}
      </div>
      {props.nextQuestion ? (
        <p>
          <span className="status">{props.nextQuestion.coverage_key ?? "complete"}</span>{" "}
          {props.nextQuestion.text ?? props.nextQuestion.reason}
        </p>
      ) : null}
      <div className="split">
        <label>
          <span className="muted">추가 증거</span>
          <textarea value={props.evidenceText} onChange={(event) => props.onEvidenceText(event.target.value)} />
        </label>
        <button onClick={props.onAddEvidence} disabled={!needsEvidence || props.evidenceText.length === 0}>
          증거 저장
        </button>
      </div>
      <div className="split">
        <label>
          <span className="muted">수정 대상 답변</span>
          <select
            value={props.revisionAnswerId}
            onChange={(event) => props.onRevisionAnswerId(event.target.value)}
          >
            <option value="">선택</option>
            {props.answerHistory.map((answer) => (
              <option key={answer.id} value={answer.id}>
                {answer.question_id} · {answer.text.slice(0, 36)}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="muted">수정 답변</span>
          <textarea value={props.revisionText} onChange={(event) => props.onRevisionText(event.target.value)} />
        </label>
        <button
          onClick={props.onReviseAnswer}
          disabled={!needsEvidence || !props.revisionAnswerId || props.revisionText.length === 0}
        >
          수정 저장
        </button>
      </div>
      <p className="muted">
        Work Model versions: {props.workModels.map((model) => `v${model.version}`).join(", ") || "없음"}
      </p>
      <pre>
        {props.opportunityDraft
          ? JSON.stringify(props.opportunityDraft.payload, null, 2)
          : "아직 생성된 opportunity draft가 없습니다."}
      </pre>
    </section>
  )
}

export function AuditPanel({ events }: { readonly events: readonly AuditEvent[] }) {
  return (
    <section className="panel stack">
      <h2>5. Audit events</h2>
      {events.length === 0 ? <p className="muted">아직 표시할 감사 이벤트가 없습니다.</p> : null}
      {events.map((event) => (
        <p key={event.id}>
          <span className="status">{event.action}</span> <span className="muted">{event.created_at}</span>
        </p>
      ))}
    </section>
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
