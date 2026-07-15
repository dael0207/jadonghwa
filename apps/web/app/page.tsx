"use client"

import { useState } from "react"

import {
  api,
  errorMessage,
  type Answer,
  type AnswerStatus,
  type AuditEvent,
  type Blueprint,
  type Coverage,
  type DesignPackage,
  type EvaluationRun,
  type Interview,
  type NextQuestion,
  type Opportunity,
  type OpportunityDiff,
  type OpportunityDraft,
  type Project,
  type Question,
  type Readiness,
  type ReleaseReadinessReport,
  type ValidationResult,
  type WorkModel,
} from "./api-client"
import {
  AuditPanel,
  M3Panel,
  M4Panel,
  M5Panel,
  M6Panel,
  M7Panel,
  M8Panel,
  ProjectPanel,
  QuestionsPanel,
  WorkModelPanel,
} from "./workbench-sections"

export default function Page() {
  const [projectName, setProjectName] = useState("월간 보고 업무")
  const [project, setProject] = useState<Project | null>(null)
  const [interview, setInterview] = useState<Interview | null>(null)
  const [questions, setQuestions] = useState<readonly Question[]>([])
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [statuses, setStatuses] = useState<Record<string, AnswerStatus>>({})
  const [answerHistory, setAnswerHistory] = useState<readonly Answer[]>([])
  const [workModel, setWorkModel] = useState<WorkModel | null>(null)
  const [workModels, setWorkModels] = useState<readonly WorkModel[]>([])
  const [coverage, setCoverage] = useState<Coverage | null>(null)
  const [nextQuestion, setNextQuestion] = useState<NextQuestion | null>(null)
  const [opportunityDraft, setOpportunityDraft] = useState<OpportunityDraft | null>(null)
  const [opportunities, setOpportunities] = useState<readonly Opportunity[]>([])
  const [latestOpportunity, setLatestOpportunity] = useState<Opportunity | null>(null)
  const [designPackages, setDesignPackages] = useState<readonly DesignPackage[]>([])
  const [latestDesignPackage, setLatestDesignPackage] = useState<DesignPackage | null>(null)
  const [designPackageValidation, setDesignPackageValidation] = useState<ValidationResult | null>(null)
  const [blueprints, setBlueprints] = useState<readonly Blueprint[]>([])
  const [latestBlueprint, setLatestBlueprint] = useState<Blueprint | null>(null)
  const [blueprintValidation, setBlueprintValidation] = useState<ValidationResult | null>(null)
  const [blueprintMarkdown, setBlueprintMarkdown] = useState("")
  const [evaluationRuns, setEvaluationRuns] = useState<readonly EvaluationRun[]>([])
  const [latestEvaluationRun, setLatestEvaluationRun] = useState<EvaluationRun | null>(null)
  const [evaluationValidation, setEvaluationValidation] = useState<ValidationResult | null>(null)
  const [releaseReports, setReleaseReports] = useState<readonly ReleaseReadinessReport[]>([])
  const [latestReleaseReport, setLatestReleaseReport] = useState<ReleaseReadinessReport | null>(null)
  const [releaseValidation, setReleaseValidation] = useState<ValidationResult | null>(null)
  const [readiness, setReadiness] = useState<Readiness | null>(null)
  const [opportunityDiff, setOpportunityDiff] = useState<OpportunityDiff | null>(null)
  const [auditEvents, setAuditEvents] = useState<readonly AuditEvent[]>([])
  const [evidenceText, setEvidenceText] = useState("")
  const [revisionAnswerId, setRevisionAnswerId] = useState("")
  const [revisionText, setRevisionText] = useState("")
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

  async function refreshDerived(next: Interview) {
    const [
      events,
      history,
      coverageBody,
      nextBody,
      answerList,
      opportunityList,
      packageList,
      blueprintList,
      evaluationList,
      releaseList,
    ] = await Promise.all([
      api.get(`v1/projects/${next.project_id}/audit-events`).json<AuditEvent[]>(),
      api.get(`v1/projects/${next.project_id}/work-models`).json<WorkModel[]>(),
      api.get(`v1/interviews/${next.id}/coverage`).json<Coverage>(),
      api.get(`v1/interviews/${next.id}/next-question`).json<NextQuestion>(),
      api.get(`v1/interviews/${next.id}/answers`).json<Answer[]>(),
      api.get(`v1/projects/${next.project_id}/opportunities`).json<Opportunity[]>(),
      api.get(`v1/projects/${next.project_id}/design-packages`).json<DesignPackage[]>(),
      api.get(`v1/projects/${next.project_id}/blueprints`).json<Blueprint[]>(),
      api.get(`v1/projects/${next.project_id}/evaluation-runs`).json<EvaluationRun[]>(),
      api.get(`v1/projects/${next.project_id}/release-readiness`).json<ReleaseReadinessReport[]>(),
    ])
    setAuditEvents(events)
    setWorkModels(history)
    setCoverage(coverageBody)
    setNextQuestion(nextBody)
    setAnswerHistory(answerList)
    setOpportunities(opportunityList)
    setLatestOpportunity(latestItem(opportunityList))
    setDesignPackages(packageList)
    setLatestDesignPackage(latestItem(packageList))
    setBlueprints(blueprintList)
    setLatestBlueprint(latestItem(blueprintList))
    setEvaluationRuns(evaluationList)
    setLatestEvaluationRun(latestItem(evaluationList))
    setReleaseReports(releaseList)
    setLatestReleaseReport(latestItem(releaseList))
    if (opportunityList.length === 0) {
      setReadiness(null)
      setOpportunityDiff(null)
    }
  }

  async function refreshInterview(interviewId: string) {
    const next = await api.get(`v1/interviews/${interviewId}`).json<Interview>()
    setInterview(next)
    await refreshDerived(next)
    return next
  }

  async function createFlow() {
    await run(async () => {
      const created = await api.post("v1/projects", { json: { name: projectName } }).json<Project>()
      const session = await api.post(`v1/projects/${created.id}/interviews`).json<Interview>()
      const loadedQuestions = await api.get(`v1/interviews/${session.id}/questions`).json<Question[]>()
      setProject(created)
      setInterview(session)
      setQuestions(loadedQuestions)
      setAnswers({})
      setStatuses({})
      setWorkModel(null)
      setOpportunityDraft(null)
      setOpportunities([])
      setLatestOpportunity(null)
      setDesignPackages([])
      setLatestDesignPackage(null)
      setDesignPackageValidation(null)
      setBlueprints([])
      setLatestBlueprint(null)
      setBlueprintValidation(null)
      setBlueprintMarkdown("")
      setEvaluationRuns([])
      setLatestEvaluationRun(null)
      setEvaluationValidation(null)
      setReleaseReports([])
      setLatestReleaseReport(null)
      setReleaseValidation(null)
      setReadiness(null)
      setOpportunityDiff(null)
      setEvidenceText("")
      setRevisionText("")
      setRevisionAnswerId("")
      await refreshDerived(session)
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
      await refreshDerived(next)
      setMessage("동의가 기록되었습니다.")
    })
  }

  async function revokeConsent() {
    if (!interview) return
    await run(async () => {
      const next = await api.post(`v1/interviews/${interview.id}/consent/revoke`).json<Interview>()
      setInterview(next)
      await refreshDerived(next)
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
      const next = await refreshInterview(interview.id)
      setMessage(`${question.position}번 답변을 저장했습니다. 현재 상태: ${next.status}`)
    })
  }

  async function buildWorkModel() {
    if (!interview) return
    await run(async () => {
      const model = await api.post(`v1/interviews/${interview.id}/build-work-model`).json<WorkModel>()
      setWorkModel(model)
      const next = await refreshInterview(interview.id)
      setMessage(`Work Model v${model.version}을 생성했습니다. 현재 상태: ${next.status}`)
    })
  }

  async function confirmPlayback() {
    if (!interview) return
    await run(async () => {
      const next = await api.post(`v1/interviews/${interview.id}/playback/confirm`).json<Interview>()
      const model = await api.get(`v1/interviews/${interview.id}/work-model`).json<WorkModel>()
      setInterview(next)
      setWorkModel(model)
      await refreshDerived(next)
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
      await refreshDerived(next)
      setMessage("Playback을 거절해 NEEDS_EVIDENCE 상태가 되었습니다.")
    })
  }

  async function addEvidence() {
    if (!interview) return
    await run(async () => {
      await api.post(`v1/interviews/${interview.id}/evidence`, { json: { text: evidenceText } })
      setEvidenceText("")
      await refreshInterview(interview.id)
      setMessage("추가 증거를 저장했습니다.")
    })
  }

  async function reviseAnswer() {
    if (!interview || !revisionAnswerId) return
    await run(async () => {
      await api.post(`v1/interviews/${interview.id}/answers/${revisionAnswerId}/revise`, {
        json: { text: revisionText },
      })
      setRevisionText("")
      setRevisionAnswerId("")
      await refreshInterview(interview.id)
      setMessage("수정 답변을 새 turn으로 저장했습니다.")
    })
  }

  async function resumeModelBuilding() {
    if (!interview) return
    await run(async () => {
      const next = await api.post(`v1/interviews/${interview.id}/resume-model-building`).json<Interview>()
      setInterview(next)
      await refreshDerived(next)
      setMessage("MODEL_BUILDING으로 돌아갔습니다.")
    })
  }

  async function refreshM3() {
    if (!interview) return
    await run(async () => {
      await refreshDerived(interview)
      setMessage("Coverage와 다음 질문을 새로 불러왔습니다.")
    })
  }

  async function loadOpportunityDraft() {
    if (!interview) return
    await run(async () => {
      const draft = await api
        .get(`v1/interviews/${interview.id}/opportunities/draft`)
        .json<OpportunityDraft>()
      setOpportunityDraft(draft)
      await refreshInterview(interview.id)
      setMessage("Opportunity draft를 생성했습니다.")
    })
  }

  async function analyzeOpportunity() {
    if (!project) return
    await run(async () => {
      const opportunity = await api
        .post(`v1/projects/${project.id}/opportunities/analyze`)
        .json<Opportunity>()
      setLatestOpportunity(opportunity)
      await refreshProjectM4(project.id)
      if (interview) {
        await refreshDerived(interview)
      }
      setMessage(`Opportunity ${opportunity.id.slice(0, 8)} 분석을 저장했습니다.`)
    })
  }

  async function createDesignPackage() {
    if (!latestOpportunity) return
    await run(async () => {
      const created = await api
        .post(`v1/opportunities/${latestOpportunity.id}/design-package`)
        .json<DesignPackage>()
      setLatestDesignPackage(created)
      setDesignPackageValidation(null)
      if (project) {
        await refreshProjectM5(project.id)
      }
      if (interview) {
        await refreshDerived(interview)
      }
      setMessage(`Design Package ${created.id.slice(0, 8)} 초안을 생성했습니다.`)
    })
  }

  async function validateDesignPackage() {
    if (!latestDesignPackage) return
    await run(async () => {
      const validation = await api
        .post(`v1/design-packages/${latestDesignPackage.id}/validate`)
        .json<ValidationResult>()
      setDesignPackageValidation(validation)
      if (project) {
        await refreshProjectM5(project.id)
      }
      if (interview) {
        await refreshDerived(interview)
      }
      setMessage(
        validation.valid ? "Design Package schema 검증을 통과했습니다." : "Design Package 검증 실패",
      )
    })
  }

  async function createBlueprint() {
    if (!latestDesignPackage) return
    await run(async () => {
      const created = await api
        .post(`v1/design-packages/${latestDesignPackage.id}/blueprint`)
        .json<Blueprint>()
      setLatestBlueprint(created)
      setBlueprintValidation(null)
      setBlueprintMarkdown("")
      if (project) {
        await refreshProjectM6(project.id)
      }
      if (interview) {
        await refreshDerived(interview)
      }
      setMessage(`Blueprint ${created.id.slice(0, 8)} preview를 생성했습니다.`)
    })
  }

  async function validateBlueprint() {
    if (!latestBlueprint) return
    await run(async () => {
      const validation = await api
        .post(`v1/blueprints/${latestBlueprint.id}/validate`)
        .json<ValidationResult>()
      setBlueprintValidation(validation)
      if (project) {
        await refreshProjectM6(project.id)
      }
      if (interview) {
        await refreshDerived(interview)
      }
      setMessage(validation.valid ? "Blueprint schema 검증을 통과했습니다." : "Blueprint 검증 실패")
    })
  }

  async function loadBlueprintMarkdown() {
    if (!latestBlueprint) return
    await run(async () => {
      const markdown = await api.get(`v1/blueprints/${latestBlueprint.id}/export/markdown`).text()
      setBlueprintMarkdown(markdown)
      if (interview) {
        await refreshDerived(interview)
      }
      setMessage("Blueprint Markdown export preview를 불러왔습니다.")
    })
  }

  async function createEvaluationRun() {
    if (!project) return
    await run(async () => {
      const created = await api.post(`v1/projects/${project.id}/evaluation-runs`).json<EvaluationRun>()
      setLatestEvaluationRun(created)
      setEvaluationValidation(null)
      await refreshProjectM7(project.id)
      if (interview) {
        await refreshDerived(interview)
      }
      setMessage(`Evaluation run ${created.id.slice(0, 8)}을 생성했습니다.`)
    })
  }

  async function validateEvaluationRun() {
    if (!latestEvaluationRun) return
    await run(async () => {
      const validation = await api
        .post(`v1/evaluation-runs/${latestEvaluationRun.id}/validate`)
        .json<ValidationResult>()
      setEvaluationValidation(validation)
      if (project) {
        await refreshProjectM7(project.id)
      }
      if (interview) {
        await refreshDerived(interview)
      }
      setMessage(validation.valid ? "Evaluation schema 검증을 통과했습니다." : "Evaluation 검증 실패")
    })
  }

  async function createReleaseReadiness() {
    if (!project) return
    await run(async () => {
      const created = await api
        .post(`v1/projects/${project.id}/release-readiness`)
        .json<ReleaseReadinessReport>()
      setLatestReleaseReport(created)
      setReleaseValidation(null)
      await refreshProjectM8(project.id)
      if (interview) {
        await refreshDerived(interview)
      }
      setMessage(`Release readiness ${created.id.slice(0, 8)} 리포트를 생성했습니다.`)
    })
  }

  async function validateReleaseReadiness() {
    if (!latestReleaseReport) return
    await run(async () => {
      const validation = await api
        .post(`v1/release-readiness/${latestReleaseReport.id}/validate`)
        .json<ValidationResult>()
      setReleaseValidation(validation)
      if (project) {
        await refreshProjectM8(project.id)
      }
      if (interview) {
        await refreshDerived(interview)
      }
      setMessage(validation.valid ? "Release readiness schema 검증을 통과했습니다." : "Release 검증 실패")
    })
  }

  async function validateOpportunity() {
    if (!latestOpportunity) return
    await run(async () => {
      const validation = await api
        .post(`v1/opportunities/${latestOpportunity.id}/validate`, {
          json: { accepted: true, notes: "validated in local UI" },
        })
        .json<ValidationResult>()
      if (project) {
        await refreshProjectM4(project.id)
      }
      if (interview) {
        await refreshDerived(interview)
      }
      setMessage(validation.valid ? "Opportunity schema 검증을 통과했습니다." : "Opportunity 검증 실패")
    })
  }

  async function loadReadiness() {
    if (!project) return
    await run(async () => {
      const body = await api.get(`v1/projects/${project.id}/readiness`).json<Readiness>()
      setReadiness(body)
      if (interview) {
        await refreshDerived(interview)
      }
      setMessage(`Readiness 결과: ${body.result}`)
    })
  }

  async function loadOpportunityDiff() {
    if (!project) return
    await run(async () => {
      const body = await api.get(`v1/projects/${project.id}/opportunities/diff`).json<OpportunityDiff>()
      setOpportunityDiff(body)
      if (interview) {
        await refreshDerived(interview)
      }
      setMessage("Opportunity diff를 불러왔습니다.")
    })
  }

  async function refreshProjectM4(projectId: string) {
    const opportunityList = await api.get(`v1/projects/${projectId}/opportunities`).json<Opportunity[]>()
    setOpportunities(opportunityList)
    setLatestOpportunity(latestItem(opportunityList))
    if (opportunityList.length === 0) {
      setReadiness(null)
      setOpportunityDiff(null)
      return
    }
    const body = await api.get(`v1/projects/${projectId}/readiness`).json<Readiness>()
    setReadiness(body)
    if (opportunityList.length >= 2) {
      const diff = await api.get(`v1/projects/${projectId}/opportunities/diff`).json<OpportunityDiff>()
      setOpportunityDiff(diff)
    } else {
      setOpportunityDiff(null)
    }
  }

  async function refreshProjectM5(projectId: string) {
    const packageList = await api.get(`v1/projects/${projectId}/design-packages`).json<DesignPackage[]>()
    setDesignPackages(packageList)
    setLatestDesignPackage(latestItem(packageList))
  }

  async function refreshProjectM6(projectId: string) {
    const blueprintList = await api.get(`v1/projects/${projectId}/blueprints`).json<Blueprint[]>()
    setBlueprints(blueprintList)
    setLatestBlueprint(latestItem(blueprintList))
  }

  async function refreshProjectM7(projectId: string) {
    const runList = await api.get(`v1/projects/${projectId}/evaluation-runs`).json<EvaluationRun[]>()
    setEvaluationRuns(runList)
    setLatestEvaluationRun(latestItem(runList))
  }

  async function refreshProjectM8(projectId: string) {
    const reportList = await api
      .get(`v1/projects/${projectId}/release-readiness`)
      .json<ReleaseReadinessReport[]>()
    setReleaseReports(reportList)
    setLatestReleaseReport(latestItem(reportList))
  }

  return (
    <main className="shell">
      <header className="header">
        <h1>Work Discovery AI</h1>
        <p>M8 인터뷰, blueprint, evaluation, release readiness 작업 화면</p>
      </header>
      <div className="grid">
        <ProjectPanel
          projectName={projectName}
          project={project}
          interview={interview}
          message={message}
          error={error}
          onProjectName={setProjectName}
          onCreateFlow={createFlow}
          onGrantConsent={grantConsent}
          onRevokeConsent={revokeConsent}
        />
        <QuestionsPanel
          interview={interview}
          questions={questions}
          answers={answers}
          statuses={statuses}
          onAnswer={(questionId, text) => setAnswers((current) => ({ ...current, [questionId]: text }))}
          onStatus={(questionId, status) => setStatuses((current) => ({ ...current, [questionId]: status }))}
          onSubmitAnswer={submitAnswer}
        />
        <WorkModelPanel
          interview={interview}
          workModel={workModel}
          onBuildWorkModel={buildWorkModel}
          onConfirmPlayback={confirmPlayback}
          onRejectPlayback={rejectPlayback}
        />
        <M3Panel
          interview={interview}
          answerHistory={answerHistory}
          evidenceText={evidenceText}
          revisionAnswerId={revisionAnswerId}
          revisionText={revisionText}
          coverage={coverage}
          nextQuestion={nextQuestion}
          opportunityDraft={opportunityDraft}
          workModels={workModels}
          onEvidenceText={setEvidenceText}
          onRevisionAnswerId={setRevisionAnswerId}
          onRevisionText={setRevisionText}
          onAddEvidence={addEvidence}
          onReviseAnswer={reviseAnswer}
          onResumeModelBuilding={resumeModelBuilding}
          onRefreshCoverage={refreshM3}
          onLoadOpportunity={loadOpportunityDraft}
        />
        <M4Panel
          project={project}
          opportunities={opportunities}
          latestOpportunity={latestOpportunity}
          readiness={readiness}
          opportunityDiff={opportunityDiff}
          onAnalyze={analyzeOpportunity}
          onValidate={validateOpportunity}
          onReadiness={loadReadiness}
          onDiff={loadOpportunityDiff}
        />
        <M5Panel
          project={project}
          latestOpportunity={latestOpportunity}
          designPackages={designPackages}
          latestDesignPackage={latestDesignPackage}
          validation={designPackageValidation}
          onCreate={createDesignPackage}
          onValidate={validateDesignPackage}
        />
        <M6Panel
          project={project}
          latestDesignPackage={latestDesignPackage}
          blueprints={blueprints}
          latestBlueprint={latestBlueprint}
          validation={blueprintValidation}
          markdown={blueprintMarkdown}
          onCreate={createBlueprint}
          onValidate={validateBlueprint}
          onMarkdown={loadBlueprintMarkdown}
        />
        <M7Panel
          project={project}
          evaluationRuns={evaluationRuns}
          latestEvaluationRun={latestEvaluationRun}
          validation={evaluationValidation}
          onCreate={createEvaluationRun}
          onValidate={validateEvaluationRun}
        />
        <M8Panel
          project={project}
          reports={releaseReports}
          latestReport={latestReleaseReport}
          validation={releaseValidation}
          onCreate={createReleaseReadiness}
          onValidate={validateReleaseReadiness}
        />
        <AuditPanel events={auditEvents} />
      </div>
    </main>
  )
}

function latestItem<T>(items: readonly T[]): T | null {
  if (items.length === 0) {
    return null
  }
  return items[items.length - 1] ?? null
}
