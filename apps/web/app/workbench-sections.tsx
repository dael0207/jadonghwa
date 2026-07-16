"use client"

import type {
  Answer,
  AnswerStatus,
  AuditEvent,
  Blueprint,
  Coverage,
  DesignPackage,
  EvaluationRun,
  Interview,
  NextQuestion,
  Opportunity,
  OpportunityDiff,
  OpportunityDraft,
  Project,
  Question,
  Readiness,
  ReleaseReadinessReport,
  ValidationResult,
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

type M4PanelProps = {
  readonly project: Project | null
  readonly opportunities: readonly Opportunity[]
  readonly latestOpportunity: Opportunity | null
  readonly readiness: Readiness | null
  readonly opportunityDiff: OpportunityDiff | null
  readonly onAnalyze: () => void
  readonly onValidate: () => void
  readonly onReadiness: () => void
  readonly onDiff: () => void
}

export function M4Panel(props: M4PanelProps) {
  const canUseProject = Boolean(props.project)
  const scoreEntries = Object.entries(props.readiness?.score_summary ?? {})
  return (
    <section className="panel stack wide">
      <h2>5. M4 Opportunity scoring</h2>
      <div className="cluster">
        <button onClick={props.onAnalyze} disabled={!canUseProject}>
          Opportunity 분석
        </button>
        <button onClick={props.onReadiness} disabled={!canUseProject || !props.latestOpportunity}>
          Readiness 확인
        </button>
        <button onClick={props.onValidate} disabled={!props.latestOpportunity}>
          Opportunity 검증
        </button>
        <button onClick={props.onDiff} disabled={!canUseProject || props.opportunities.length < 2}>
          이전 분석과 Diff
        </button>
      </div>
      <div className="metric-grid">
        <p className="metric">
          <strong>Gate</strong>
          <span className="status">{props.readiness?.result ?? "미분석"}</span>
        </p>
        <p className="metric">
          <strong>G1 readiness</strong>
          <span className="status">{props.readiness?.ready_for_g1 ? "READY" : "NOT READY"}</span>
        </p>
        <p className="metric">
          <strong>Opportunity versions</strong>
          <span>{props.opportunities.length}</span>
        </p>
      </div>
      {scoreEntries.length > 0 ? (
        <div className="metric-grid">
          {scoreEntries.map(([key, value]) => (
            <p className="metric" key={key}>
              <strong>{key}</strong>
              <span>{String(value)}</span>
            </p>
          ))}
        </div>
      ) : null}
      <div className="split equal">
        <ListBlock title="Blocking reasons" items={props.readiness?.blocking_reasons ?? []} />
        <ListBlock title="Missing evidence" items={props.readiness?.missing_evidence ?? []} />
        <ListBlock title="Required follow-ups" items={props.readiness?.required_followups ?? []} />
      </div>
      <div className="split equal">
        <div className="stack">
          <strong>Opportunity list</strong>
          {props.opportunities.length === 0 ? (
            <p className="muted">아직 저장된 opportunity가 없습니다.</p>
          ) : null}
          {props.opportunities.map((opportunity) => (
            <p className="list-row" key={opportunity.id}>
              <span className="status">v{opportunity.work_model_version}</span>
              <span>{opportunity.id.slice(0, 8)}</span>
              <span className={opportunity.schema_valid ? "success" : "error"}>
                {opportunity.schema_valid ? "schema valid" : "schema invalid"}
              </span>
            </p>
          ))}
        </div>
        <pre>
          {props.latestOpportunity
            ? JSON.stringify(props.latestOpportunity.payload, null, 2)
            : "아직 분석된 opportunity가 없습니다."}
        </pre>
      </div>
      <pre>
        {props.opportunityDiff
          ? JSON.stringify(props.opportunityDiff, null, 2)
          : "Diff는 저장된 opportunity가 2개 이상일 때 확인할 수 있습니다."}
      </pre>
    </section>
  )
}

type M5PanelProps = {
  readonly project: Project | null
  readonly latestOpportunity: Opportunity | null
  readonly designPackages: readonly DesignPackage[]
  readonly latestDesignPackage: DesignPackage | null
  readonly validation: ValidationResult | null
  readonly onCreate: () => void
  readonly onValidate: () => void
}

export function M5Panel(props: M5PanelProps) {
  const acceptanceTests = acceptanceTestsFrom(props.latestDesignPackage)
  const gateResult = opportunityGate(props.latestOpportunity)
  const canCreate =
    Boolean(props.project && props.latestOpportunity?.schema_valid) &&
    (gateResult === "READY_FOR_DESIGN" || gateResult === "ENABLE_FIRST")
  return (
    <section className="panel stack wide">
      <h2>6. M5 Design package</h2>
      <div className="cluster">
        <button onClick={props.onCreate} disabled={!canCreate}>
          Design Package 생성
        </button>
        <button onClick={props.onValidate} disabled={!props.latestDesignPackage}>
          Package 검증
        </button>
      </div>
      {!canCreate && props.latestOpportunity ? (
        <p className="error">
          Gate가 {gateResult}이므로 Design Package를 만들 수 없습니다. Discovery recovery를 먼저 완료하세요.
        </p>
      ) : null}
      <div className="metric-grid">
        <p className="metric">
          <strong>Package type</strong>
          <span className="status">{packageString(props.latestDesignPackage, "package_type")}</span>
        </p>
        <p className="metric">
          <strong>Readiness</strong>
          <span className="status">{packageString(props.latestDesignPackage, "readiness_result")}</span>
        </p>
        <p className="metric">
          <strong>Packages</strong>
          <span>{props.designPackages.length}</span>
        </p>
        <p className="metric">
          <strong>Schema</strong>
          <span className={props.latestDesignPackage?.schema_valid ? "success" : "status"}>
            {props.latestDesignPackage?.schema_valid ? "valid" : "not generated"}
          </span>
        </p>
      </div>
      {props.validation ? (
        <p className={props.validation.valid ? "success" : "error"}>
          {props.validation.valid
            ? `${props.validation.schema_name} 통과`
            : (props.validation.error ?? "검증 실패")}
        </p>
      ) : null}
      <div className="split equal">
        <div className="stack list-block">
          <strong>Package list</strong>
          {props.designPackages.length === 0 ? (
            <p className="muted">생성된 패키지가 없습니다.</p>
          ) : null}
          {props.designPackages.map((item) => (
            <p className="list-row" key={item.id}>
              <span className="status">{packageString(item, "package_type")}</span>
              <span>{item.id.slice(0, 8)}</span>
              <span>WM v{item.work_model_version}</span>
            </p>
          ))}
        </div>
        <div className="stack list-block">
          <strong>Acceptance tests</strong>
          {acceptanceTests.length === 0 ? <p className="muted">패키지 생성 후 표시됩니다.</p> : null}
          <div className="acceptance-list">
            {acceptanceTests.map((item) => (
              <article className="acceptance-item" key={item.id}>
                <strong>{item.scenario}</strong>
                <dl>
                  <div>
                    <dt>Given</dt>
                    <dd>{item.given}</dd>
                  </div>
                  <div>
                    <dt>When</dt>
                    <dd>{item.when}</dd>
                  </div>
                  <div>
                    <dt>Then</dt>
                    <dd>{item.then}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        </div>
      </div>
      <pre>
        {props.latestDesignPackage
          ? JSON.stringify(props.latestDesignPackage.payload, null, 2)
          : "생성된 패키지가 없습니다."}
      </pre>
    </section>
  )
}

type M6PanelProps = {
  readonly project: Project | null
  readonly latestDesignPackage: DesignPackage | null
  readonly blueprints: readonly Blueprint[]
  readonly latestBlueprint: Blueprint | null
  readonly validation: ValidationResult | null
  readonly markdown: string
  readonly onCreate: () => void
  readonly onValidate: () => void
  readonly onMarkdown: () => void
}

export function M6Panel(props: M6PanelProps) {
  const quality = qualityCriteriaFrom(props.latestBlueprint)
  return (
    <section className="panel stack wide">
      <h2>7. M6 Blueprint</h2>
      <div className="cluster">
        <button onClick={props.onCreate} disabled={!props.project || !props.latestDesignPackage}>
          Blueprint 생성
        </button>
        <button onClick={props.onValidate} disabled={!props.latestBlueprint}>
          Blueprint 검증
        </button>
        <button onClick={props.onMarkdown} disabled={!props.latestBlueprint}>
          Markdown 미리보기
        </button>
      </div>
      <div className="metric-grid">
        <Metric label="Blueprint type" value={payloadString(props.latestBlueprint, "blueprint_type")} />
        <Metric label="Export ready" value={props.latestBlueprint?.export_ready ? "READY" : "NOT READY"} />
        <Metric label="Blueprints" value={String(props.blueprints.length)} />
        <Metric label="Schema" value={props.latestBlueprint?.schema_valid ? "valid" : "not generated"} />
      </div>
      <ValidationMessage validation={props.validation} />
      <div className="split equal">
        <div className="stack list-block">
          <strong>Blueprint list</strong>
          {props.blueprints.length === 0 ? <p className="muted">생성된 blueprint가 없습니다.</p> : null}
          {props.blueprints.map((item) => (
            <p className="list-row" key={item.id}>
              <span className="status">{payloadString(item, "blueprint_type")}</span>
              <span>{item.id.slice(0, 8)}</span>
              <span>{item.export_ready ? "export ready" : "limited"}</span>
            </p>
          ))}
        </div>
        <div className="stack list-block">
          <strong>Quality gate</strong>
          {quality.length === 0 ? <p className="muted">Blueprint 생성 후 표시됩니다.</p> : null}
          {quality.map((item) => (
            <p className="list-row" key={item.key}>
              <span className={item.passed ? "success" : "error"}>{item.passed ? "PASS" : "BLOCKED"}</span>
              <span>{item.key}</span>
              <span className="muted">{item.detail}</span>
            </p>
          ))}
        </div>
      </div>
      <div className="split equal">
        <pre>
          {props.latestBlueprint
            ? JSON.stringify(props.latestBlueprint.payload, null, 2)
            : "생성된 blueprint가 없습니다."}
        </pre>
        <pre>{props.markdown || "Markdown export preview는 버튼을 누르면 표시됩니다."}</pre>
      </div>
    </section>
  )
}

type M7PanelProps = {
  readonly project: Project | null
  readonly evaluationRuns: readonly EvaluationRun[]
  readonly latestEvaluationRun: EvaluationRun | null
  readonly validation: ValidationResult | null
  readonly onCreate: () => void
  readonly onValidate: () => void
}

export function M7Panel(props: M7PanelProps) {
  const summary = recordValue(props.latestEvaluationRun?.payload["score_summary"])
  const criteria = criteriaFrom(props.latestEvaluationRun)
  const failed = stringArray(props.latestEvaluationRun?.payload["failed_criteria"])
  return (
    <section className="panel stack wide">
      <h2>8. M7 Evaluation</h2>
      <div className="cluster">
        <button onClick={props.onCreate} disabled={!props.project}>
          Evaluation run 생성
        </button>
        <button onClick={props.onValidate} disabled={!props.latestEvaluationRun}>
          Evaluation 검증
        </button>
      </div>
      <div className="metric-grid">
        <Metric label="Average" value={stringFrom(summary["average_score"], "미생성")} />
        <Metric label="Passed" value={`${stringFrom(summary["passed_count"], "0")} / ${stringFrom(summary["total_count"], "0")}`} />
        <Metric label="Corpus" value={stringFrom(props.latestEvaluationRun?.payload["item_count"], "0")} />
        <Metric label="Runs" value={String(props.evaluationRuns.length)} />
      </div>
      <ValidationMessage validation={props.validation} />
      <div className="split equal">
        <div className="stack list-block">
          <strong>Criteria</strong>
          {criteria.length === 0 ? <p className="muted">Evaluation run 생성 후 표시됩니다.</p> : null}
          {criteria.map((item) => (
            <p className="list-row" key={item.key}>
              <span className={item.passed ? "success" : "error"}>{item.passed ? "PASS" : "FAIL"}</span>
              <span>{item.label}</span>
              <span className="muted">
                {item.score} / {item.threshold}
              </span>
            </p>
          ))}
        </div>
        <ListBlock title="Failed criteria" items={failed} />
      </div>
      <pre>
        {props.latestEvaluationRun
          ? JSON.stringify(props.latestEvaluationRun.payload, null, 2)
          : "생성된 evaluation run이 없습니다."}
      </pre>
    </section>
  )
}

type M8PanelProps = {
  readonly project: Project | null
  readonly reports: readonly ReleaseReadinessReport[]
  readonly latestReport: ReleaseReadinessReport | null
  readonly validation: ValidationResult | null
  readonly onCreate: () => void
  readonly onValidate: () => void
}

export function M8Panel(props: M8PanelProps) {
  const checklist = checklistFrom(props.latestReport)
  const blockers = stringArray(props.latestReport?.payload["blocking_items"])
  return (
    <section className="panel stack wide">
      <h2>9. M8 Release readiness</h2>
      <div className="cluster">
        <button onClick={props.onCreate} disabled={!props.project}>
          Readiness report 생성
        </button>
        <button onClick={props.onValidate} disabled={!props.latestReport}>
          Readiness 검증
        </button>
      </div>
      <div className="metric-grid">
        <Metric label="Status" value={payloadString(props.latestReport, "readiness_status")} />
        <Metric label="Reports" value={String(props.reports.length)} />
        <Metric label="Blockers" value={String(blockers.length)} />
        <Metric label="Schema" value={props.latestReport?.schema_valid ? "valid" : "not generated"} />
      </div>
      <ValidationMessage validation={props.validation} />
      <div className="split equal">
        <div className="stack list-block">
          <strong>Checklist</strong>
          {checklist.length === 0 ? <p className="muted">리포트 생성 후 표시됩니다.</p> : null}
          {checklist.map((item) => (
            <p className="list-row" key={item.key}>
              <span className={item.status === "PASS" ? "success" : "error"}>{item.status}</span>
              <span>{item.label}</span>
              <span className="muted">{item.details}</span>
            </p>
          ))}
        </div>
        <ListBlock title="Blocking items" items={blockers} />
      </div>
      <pre>
        {props.latestReport
          ? JSON.stringify(props.latestReport.payload, null, 2)
          : "생성된 readiness report가 없습니다."}
      </pre>
    </section>
  )
}

export function AuditPanel({ events }: { readonly events: readonly AuditEvent[] }) {
  return (
    <section className="panel stack">
      <h2>10. Audit events</h2>
      {events.length === 0 ? <p className="muted">아직 표시할 감사 이벤트가 없습니다.</p> : null}
      {events.map((event) => (
        <p key={event.id}>
          <span className="status">{event.action}</span> <span className="muted">{event.created_at}</span>
        </p>
      ))}
    </section>
  )
}

function Metric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <p className="metric">
      <strong>{label}</strong>
      <span className="status">{value}</span>
    </p>
  )
}

function opportunityGate(opportunity: Opportunity | null): string {
  const gate = opportunity?.payload["gate"]
  if (typeof gate !== "object" || gate === null || Array.isArray(gate)) {
    return "UNKNOWN"
  }
  const result = (gate as Record<string, unknown>)["result"]
  return typeof result === "string" ? result : "UNKNOWN"
}

function ValidationMessage({ validation }: { readonly validation: ValidationResult | null }) {
  if (!validation) {
    return null
  }
  return (
    <p className={validation.valid ? "success" : "error"}>
      {validation.valid ? `${validation.schema_name} 통과` : (validation.error ?? "검증 실패")}
    </p>
  )
}

type AcceptanceTestSummary = {
  readonly id: string
  readonly scenario: string
  readonly given: string
  readonly when: string
  readonly then: string
}

function acceptanceTestsFrom(packageItem: DesignPackage | null): AcceptanceTestSummary[] {
  const value = packageItem?.payload["acceptance_tests"]
  if (!Array.isArray(value)) {
    return []
  }
  return value.slice(0, 4).map((item, index) => {
    if (typeof item === "string") {
      return {
        id: `acceptance-${index + 1}`,
        scenario: item,
        given: "패키지 초안",
        when: "검증 실행",
        then: "조건 충족",
      }
    }
    const record = recordValue(item)
    return {
      id: stringField(record, "id", `acceptance-${index + 1}`),
      scenario: stringField(record, "scenario", `Acceptance test ${index + 1}`),
      given: stringField(record, "given", "패키지 초안"),
      when: stringField(record, "when", "검증 실행"),
      then: stringField(record, "then", "조건 충족"),
    }
  })
}

function packageString(packageItem: DesignPackage | null, key: string): string {
  const value = packageItem?.payload[key]
  if (typeof value === "string" && value.length > 0) {
    return value
  }
  return "미생성"
}

function payloadString(
  item: Blueprint | ReleaseReadinessReport | null,
  key: string,
): string {
  return stringFrom(item?.payload[key], "미생성")
}

type QualityCriterion = {
  readonly key: string
  readonly passed: boolean
  readonly detail: string
}

function qualityCriteriaFrom(blueprint: Blueprint | null): QualityCriterion[] {
  const gate = recordValue(blueprint?.payload["quality_gate"])
  return recordArray(gate["criteria"]).map((item, index) => ({
    key: stringField(item, "key", `criterion-${index + 1}`),
    passed: item["passed"] === true,
    detail: stringField(item, "detail", "상세 없음"),
  }))
}

type EvaluationCriterion = {
  readonly key: string
  readonly label: string
  readonly score: string
  readonly threshold: string
  readonly passed: boolean
}

function criteriaFrom(run: EvaluationRun | null): EvaluationCriterion[] {
  return recordArray(run?.payload["criteria_results"]).map((item, index) => ({
    key: stringField(item, "key", `criterion-${index + 1}`),
    label: stringField(item, "label", `Criterion ${index + 1}`),
    score: stringFrom(item["score"], "0"),
    threshold: stringFrom(item["threshold"], "0"),
    passed: item["passed"] === true,
  }))
}

type ReadinessChecklist = {
  readonly key: string
  readonly label: string
  readonly status: string
  readonly details: string
}

function checklistFrom(report: ReleaseReadinessReport | null): ReadinessChecklist[] {
  return recordArray(report?.payload["checklist"]).map((item, index) => ({
    key: stringField(item, "key", `check-${index + 1}`),
    label: stringField(item, "label", `Check ${index + 1}`),
    status: stringField(item, "status", "BLOCKED"),
    details: stringField(item, "details", "상세 없음"),
  }))
}

function recordValue(value: unknown): Record<string, unknown> {
  if (isRecord(value)) {
    return value
  }
  return {}
}

function recordArray(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter(isRecord)
}

function stringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter((item): item is string => typeof item === "string" && item.length > 0)
}

function stringFrom(value: unknown, fallback: string): string {
  if (typeof value === "string" && value.length > 0) {
    return value
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value)
  }
  return fallback
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function stringField(record: Record<string, unknown>, key: string, fallback: string): string {
  const value = record[key]
  if (typeof value === "string" && value.length > 0) {
    return value
  }
  return fallback
}

function ListBlock({ title, items }: { readonly title: string; readonly items: readonly string[] }) {
  return (
    <div className="stack list-block">
      <strong>{title}</strong>
      {items.length === 0 ? <p className="muted">없음</p> : null}
      {items.map((item) => (
        <p className="list-row" key={item}>
          {item}
        </p>
      ))}
    </div>
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
