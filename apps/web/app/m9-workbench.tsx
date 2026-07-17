"use client"

import { useEffect, useRef, useState } from "react"

import {
  api,
  errorMessage,
  type AuditEvent,
  type EvidenceFile,
  type EvidenceFileRole,
  type ImplementationPackage,
  type ImplementationRequirements,
  type Project,
  type ValidationResult,
} from "./api-client"

type M9WorkbenchProps = {
  readonly project: Project | null
}

export function M9Workbench({ project }: M9WorkbenchProps) {
  const fileInput = useRef<HTMLInputElement>(null)
  const [packages, setPackages] = useState<readonly ImplementationPackage[]>([])
  const [evidenceFiles, setEvidenceFiles] = useState<readonly EvidenceFile[]>([])
  const [auditEvents, setAuditEvents] = useState<readonly AuditEvent[]>([])
  const [requirementsText, setRequirementsText] = useState("{}")
  const [fileRole, setFileRole] = useState<EvidenceFileRole>("INPUT")
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [validation, setValidation] = useState<ValidationResult | null>(null)
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)

  const latest = packages.at(-1) ?? null
  const payload = latest?.payload ?? {}
  const readiness = recordValue(payload["codegen_readiness"])
  const blockers = stringArray(readiness["blockers"])
  const followUps = stringArray(readiness["follow_up_questions"])
  const dataContract = recordValue(payload["data_contract"])
  const rules = recordValue(payload["rules"])
  const mappings = recordArray(dataContract["field_mappings"])
  const ruleCount =
    recordArray(rules["calculations"]).length +
    recordArray(rules["decisions"]).length +
    recordArray(rules["validations"]).length
  const exceptions = recordArray(payload["exceptions"])
  const oversight = recordValue(payload["human_oversight"])
  const acceptanceCases = recordArray(parseRecord(requirementsText)["acceptance_cases"])
  const confirmedInputs = evidenceFiles.filter(
    (item) => item.confirmed && item.role === "INPUT",
  )
  const confirmedOutputs = evidenceFiles.filter(
    (item) => item.confirmed && item.role === "EXPECTED_OUTPUT",
  )

  useEffect(() => {
    void loadTemplate()
  }, [])

  useEffect(() => {
    if (!project) {
      setPackages([])
      setEvidenceFiles([])
      setAuditEvents([])
      return
    }
    void refresh(project.id)
  }, [project])

  async function run(action: () => Promise<void>) {
    setError("")
    setMessage("")
    setBusy(true)
    try {
      await action()
    } catch (caught) {
      setError(await errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  async function loadTemplate() {
    try {
      const template = await api
        .get("v1/implementation-requirements/template")
        .json<Record<string, unknown>>()
      setRequirementsText(JSON.stringify(template, null, 2))
    } catch (caught) {
      setError(await errorMessage(caught))
    }
  }

  async function refresh(projectId: string) {
    const [packageList, files, events] = await Promise.all([
      api
        .get(`v1/projects/${projectId}/implementation-packages`)
        .json<ImplementationPackage[]>(),
      api.get(`v1/projects/${projectId}/evidence-files`).json<EvidenceFile[]>(),
      api.get(`v1/projects/${projectId}/audit-events`).json<AuditEvent[]>(),
    ])
    setPackages(packageList)
    setEvidenceFiles(files)
    setAuditEvents(events.filter((event) => event.action.includes("IMPLEMENTATION") || event.action.includes("EVIDENCE_FILE") || event.action.includes("CODEGEN")))
  }

  async function uploadEvidence() {
    if (!project || !selectedFile) return
    await run(async () => {
      const contentBase64 = await fileToBase64(selectedFile)
      await api.post(`v1/projects/${project.id}/evidence-files`, {
        json: {
          role: fileRole,
          filename: selectedFile.name,
          content_type: evidenceContentType(selectedFile),
          content_base64: contentBase64,
        },
      })
      setSelectedFile(null)
      if (fileInput.current) {
        fileInput.current.value = ""
      }
      await refresh(project.id)
      setMessage("샘플 파일과 추출 schema를 append-only evidence로 저장했습니다.")
    })
  }

  async function confirmEvidence(evidenceFileId: string) {
    if (!project) return
    await run(async () => {
      await api.post(`v1/evidence-files/${evidenceFileId}/confirm`, {
        json: { confirmed: true, confirmed_by: "local-user" },
      })
      await refresh(project.id)
      setMessage("추출된 파일 schema를 확인했습니다.")
    })
  }

  async function saveRequirements() {
    if (!project) return
    await run(async () => {
      const parsed = JSON.parse(requirementsText) as Record<string, unknown>
      const recorded = await api
        .post(`v1/projects/${project.id}/implementation-requirements`, {
          json: { payload: parsed, confirmed: true },
        })
        .json<ImplementationRequirements>()
      await refresh(project.id)
      setMessage(`구현 계약 ${recorded.id.slice(0, 8)}을 확정했습니다.`)
    })
  }

  function bindAcceptanceFixture(
    index: number,
    field: "input_file_refs" | "expected_file_refs",
    evidenceFileId: string,
  ) {
    const parsed = parseRecord(requirementsText)
    const cases = recordArray(parsed["acceptance_cases"])
    const current = cases[index]
    if (!current) return
    cases[index] = {
      ...current,
      [field]: evidenceFileId ? [evidenceFileId] : ["REPLACED_BY_API"],
    }
    setRequirementsText(
      JSON.stringify({ ...parsed, acceptance_cases: cases }, null, 2),
    )
  }

  async function createPackage() {
    if (!project) return
    await run(async () => {
      const created = await api
        .post(`v1/projects/${project.id}/implementation-packages`)
        .json<ImplementationPackage>()
      setValidation(null)
      await refresh(project.id)
      setMessage(`Implementation package ${created.id.slice(0, 8)}을 생성했습니다.`)
    })
  }

  async function validatePackage() {
    if (!project || !latest) return
    await run(async () => {
      const result = await api
        .post(`v1/implementation-packages/${latest.id}/validate`)
        .json<ValidationResult>()
      setValidation(result)
      await refresh(project.id)
      setMessage(result.valid ? "Implementation package schema 검증을 통과했습니다." : "검증에 실패했습니다.")
    })
  }

  async function downloadArchive(mode: "draft" | "codegen") {
    if (!project || !latest) return
    await run(async () => {
      const response = await api.get(
        `v1/implementation-packages/${latest.id}/export.zip?mode=${mode}`,
      )
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = `implementation-package-${latest.id.slice(0, 8)}-${mode}.zip`
      link.click()
      URL.revokeObjectURL(url)
      await refresh(project.id)
      setMessage(`${mode === "draft" ? "DRAFT" : "CODEGEN_READY"} ZIP을 생성했습니다.`)
    })
  }

  return (
    <section className="panel stack wide" data-testid="m9-workbench">
      <h2>10. M9 Implementation package</h2>
      <div className="cluster">
        <button onClick={createPackage} disabled={!project || busy}>
          Readiness 평가·package 생성
        </button>
        <button className="secondary" onClick={validatePackage} disabled={!latest || busy}>
          Package 검증
        </button>
        <button className="secondary" onClick={() => downloadArchive("draft")} disabled={!latest || busy}>
          DRAFT ZIP
        </button>
        <button onClick={() => downloadArchive("codegen")} disabled={!latest || latest.readiness_status !== "CODEGEN_READY" || busy}>
          CODEGEN_READY ZIP
        </button>
      </div>

      {message ? <p className="success">{message}</p> : null}
      {error ? <p className="error">{error}</p> : null}

      <div className="metric-grid">
        <Metric label="Gate" value={latest?.readiness_status ?? "NOT_EVALUATED"} />
        <Metric label="Packages" value={String(packages.length)} />
        <Metric label="Blockers" value={String(blockers.length)} />
        <Metric label="Evidence" value={`${evidenceFiles.filter((item) => item.confirmed).length}/${evidenceFiles.length}`} />
      </div>

      {validation ? (
        <p className={validation.valid ? "success" : "error"}>
          {validation.valid ? `${validation.schema_name} 통과` : (validation.error ?? "검증 실패")}
        </p>
      ) : null}

      <div className="split equal">
        <ListSection title="Blockers" items={blockers} empty="현재 blocker가 없습니다." />
        <ListSection title="Follow-up questions" items={followUps} empty="추가 질문이 없습니다." />
      </div>

      <div className="split equal">
        <div className="stack">
          <strong>Sample evidence</strong>
          <div className="split equal compact-fields">
            <label>
              역할
              <select value={fileRole} onChange={(event) => setFileRole(event.target.value as EvidenceFileRole)}>
                <option value="INPUT">Input</option>
                <option value="EXPECTED_OUTPUT">Expected output</option>
              </select>
            </label>
            <label>
              CSV, JSON, XLSX
              <input
                ref={fileInput}
                type="file"
                accept=".csv,.json,.xlsx"
                onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              />
            </label>
          </div>
          <button onClick={uploadEvidence} disabled={!project || !selectedFile || busy}>
            파일 분석·저장
          </button>
          <div className="evidence-list">
            {evidenceFiles.map((item) => (
              <div className="evidence-row" key={item.id}>
                <div>
                  <strong>{item.filename}</strong>
                  <p className="muted">{item.role} · {item.size_bytes} bytes · {item.confirmed ? "confirmed" : "pending"}</p>
                  <code className="evidence-id">{item.id}</code>
                </div>
                <button className="secondary" onClick={() => confirmEvidence(item.id)} disabled={item.confirmed || busy}>
                  Schema 확인
                </button>
                <details>
                  <summary>추출 schema</summary>
                  <pre>{JSON.stringify(item.extracted_schema, null, 2)}</pre>
                </details>
              </div>
            ))}
            {evidenceFiles.length === 0 ? <p className="muted">저장된 sample evidence가 없습니다.</p> : null}
          </div>
        </div>

        <div className="stack">
          <label htmlFor="implementation-requirements"><strong>Implementation contract</strong></label>
          <strong>Acceptance fixture binding</strong>
          <div className="stack">
            {acceptanceCases.map((acceptanceCase, index) => (
              <div className="acceptance-binding" key={`${String(acceptanceCase["kind"])}-${index}`}>
                <p>
                  <strong>{String(acceptanceCase["kind"] ?? `CASE ${index + 1}`)}</strong>
                  <span className="muted"> {String(acceptanceCase["scenario"] ?? "")}</span>
                </p>
                <div className="split equal compact-fields">
                  <label>
                    Input fixture
                    <select
                      value={stringArray(acceptanceCase["input_file_refs"])[0] ?? ""}
                      onChange={(event) => bindAcceptanceFixture(index, "input_file_refs", event.target.value)}
                    >
                      <option value="">선택 필요</option>
                      {confirmedInputs.map((item) => (
                        <option value={item.id} key={item.id}>{item.filename}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Expected fixture
                    <select
                      value={stringArray(acceptanceCase["expected_file_refs"])[0] ?? ""}
                      onChange={(event) => bindAcceptanceFixture(index, "expected_file_refs", event.target.value)}
                    >
                      <option value="">선택 필요</option>
                      {confirmedOutputs.map((item) => (
                        <option value={item.id} key={item.id}>{item.filename}</option>
                      ))}
                    </select>
                  </label>
                </div>
              </div>
            ))}
            {acceptanceCases.length === 0 ? (
              <p className="muted">계약 template의 acceptance_cases가 필요합니다.</p>
            ) : null}
          </div>
          <textarea
            id="implementation-requirements"
            className="contract-editor"
            value={requirementsText}
            onChange={(event) => setRequirementsText(event.target.value)}
            spellCheck={false}
          />
          <button onClick={saveRequirements} disabled={!project || busy}>
            계약 확정
          </button>
        </div>
      </div>

      <div className="metric-grid">
        <Metric label="Mappings" value={String(mappings.length)} />
        <Metric label="Rules" value={String(ruleCount)} />
        <Metric label="Exceptions" value={String(exceptions.length)} />
        <Metric label="Approvals" value={String(stringArray(oversight["approval_points"]).length)} />
      </div>

      <details open={latest !== null}>
        <summary>Latest implementation package JSON</summary>
        <pre>{latest ? JSON.stringify(latest.payload, null, 2) : "생성된 package가 없습니다."}</pre>
      </details>

      <div className="stack">
        <strong>M9 audit events</strong>
        {auditEvents.map((event) => (
          <p className="list-row" key={event.id}>
            <span className="status">{event.action}</span>
            <span className="muted">{event.created_at}</span>
          </p>
        ))}
        {auditEvents.length === 0 ? <p className="muted">M9 감사 이벤트가 없습니다.</p> : null}
      </div>
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

function ListSection({
  title,
  items,
  empty,
}: {
  readonly title: string
  readonly items: readonly string[]
  readonly empty: string
}) {
  return (
    <div className="stack m9-list">
      <strong>{title}</strong>
      {items.map((item) => <p className="list-row" key={item}>{item}</p>)}
      {items.length === 0 ? <p className="muted">{empty}</p> : null}
    </div>
  )
}

function recordValue(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

function recordArray(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.map(recordValue) : []
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : []
}

function parseRecord(value: string): Record<string, unknown> {
  try {
    return recordValue(JSON.parse(value))
  } catch {
    return {}
  }
}

async function fileToBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer())
  let binary = ""
  const chunkSize = 32_768
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize))
  }
  return btoa(binary)
}

function evidenceContentType(file: File): string {
  if (file.type) return file.type
  if (file.name.toLowerCase().endsWith(".csv")) return "text/csv"
  if (file.name.toLowerCase().endsWith(".json")) return "application/json"
  return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
}
