# Work Discovery AI Blueprint

버전: v0.9
상태: M9 Implementation Package 구현 완료
목표 사용자: 자동화 지식이 부족하지만 디지털 업무를 개선하고 싶은 개인, 직원, 팀, 중소기업

## 제품 정의

> 사용자가 자신의 업무를 텍스트 또는 음성으로 설명하면, AI가 최근의 실제 사례를 중심으로 후속 질문을 반복하고, 업무 흐름·판단·예외·데이터·도구를 검증 가능한 구조로 정리한 뒤, 개선 및 자동화 후보를 비교하고 선택된 후보의 PRD와 개발 명세를 생성한다.

이 제품은 단순한 챗봇이나 워크플로 빌더가 아니다. 핵심은 사용자가 아직 자동화 대상을 모르는 상태에서 시작해 **업무 발견 → 업무 모델링 → 개선·자동화 판단 → 프로그램 명세 생성**까지 연결하는 것이다.

## 성공 레벨

- Level 1 — 업무 이해: 사용자가 “내 업무를 정확히 이해했다”고 확인할 수 있는 검증된 업무 모델 생성
- Level 2 — 자동화 발견: 개선·자동화 후보와 예상 효과, 위험, 전제조건을 비교
- Level 3 — 프로그램 설계: PRD, 사용자 흐름, 데이터 모델, 연동, 수용 기준 생성
- Level 4 — 개발 전달: 개발자가 구현을 시작할 수 있는 API·스키마·백로그·테스트 명세 생성

## 연구 문서

1. `R001-project-definition.md` — 프로젝트 정의, 미션, 사용자, 범위
2. `R002-market-competitor-research.md` — 시장, 경쟁 제품, 실제 업무 자동화 사례
3. `R003-automation-discovery-framework.md` — 무엇을 왜 개선·자동화할지 판단하는 기준
4. `R004-work-ontology.md` — 사용자 업무를 저장하는 표준 구조
5. `R005-interview-methodology.md` — 어떤 순서와 원칙으로 인터뷰할지
6. `R006-interview-engine.md` — 인터뷰 상태 머신과 AI 파이프라인
7. `R007-automation-reasoning-engine.md` — 자동화 후보 생성·평가·설명 엔진
8. `R008-program-generation.md` — 선택된 후보를 프로그램 명세로 변환
9. `R009-evaluation-framework.md` — 정확도·안전성·효용 평가
10. `R010-mvp-spec.md` — 첫 번째 제품 범위와 구현 계획

## 구현 보조 산출물

- `schemas/work-model-v1.schema.json`
- `schemas/interview-state-v1.schema.json`
- `schemas/opportunity-v1.schema.json`
- `schemas/design-package-v1.schema.json`
- `schemas/automation-workflow-v1.schema.json`
- `schemas/integration-contract-v1.schema.json`
- `schemas/implementation-package-v1.schema.json`
- `schemas/codegen-readiness-v1.schema.json`
- `schemas/export-manifest-v1.schema.json`
- `schemas/acceptance-fixture-v1.schema.json`
- `question-bank-v1.json`
- `openapi-mvp.yaml`

## 로컬 실행

API 서버:
```bash
cd apps/api
python -m pip install -e .
python -m uvicorn work_discovery_api.main:app --reload --port 8000
```

웹 UI:
```bash
cd apps/web
npm install
npm run dev -- -H 127.0.0.1 -p 3000
```

브라우저에서 `http://127.0.0.1:3000`을 열면 프로젝트 생성, 인터뷰 생성, 동의, 10문항 답변, Work Model 생성, Playback 승인/거절, 추가 증거, 답변 수정, 재빌드, coverage/next-question, opportunity draft, M4 opportunity scoring, residual-risk gate, Discovery Recovery, diff, M5 design package, M6 blueprint, M7 evaluation run, M8 release readiness report, M9 implementation package와 CODEGEN_READY ZIP 생성/검증/preview, 감사 이벤트 조회까지 클릭으로 확인할 수 있다.

## 저장소와 데이터베이스

- 기본 실행은 `DATABASE_URL`이 없을 때 in-memory 저장소를 사용한다.
- `DATABASE_URL=postgresql://...`을 설정하면 API가 `PostgresRepository`를 선택한다.
- PostgreSQL을 사용할 때는 먼저 `infra/db/migrations/*.sql`을 파일명 순서대로 대상 DB에 적용해야 한다.
- 로컬 개발자가 PostgreSQL 없이 검증할 수 있도록 PGlite 기반 마이그레이션 스모크가 유지된다.

마이그레이션 스모크:
```bash
cd infra/db
npm install
npm run migration:smoke
```

## M1~M9 검증

```bash
cd apps/api
python -m pytest
python -m ruff check .
python -m basedpyright
python -m work_discovery_api.scripts.schema_smoke
python -m work_discovery_api.scripts.api_smoke
python -m work_discovery_api.scripts.server_smoke
python -m pytest tests/test_m9_acceptance.py -q

cd ../../infra/db
npm install
npm run migration:smoke
npm audit --audit-level=moderate

cd ../../apps/web
npm install
npm run typecheck
npm run build
npm audit --audit-level=moderate
```

## M2 Mock Builder

M2의 Work Model Builder는 LLM을 호출하지 않는다. 10문항의 최신 답변을 deterministic 규칙으로 요약해 `schemas/work-model-v1.schema.json`을 통과하는 Work Model 초안을 생성한다. 이 결과는 인터뷰 답변 기반 playback 확인용 초안이며, 자동화 후보 분석이나 G1 명세 생성 결과가 아니다.

## M3 deterministic foundation

M3는 고정 10문항 흐름을 유지하면서 reject 이후 `NEEDS_EVIDENCE` 상태에서 추가 증거와 답변 revision을 받을 수 있게 한다. `resume-model-building` 후 다시 Work Model을 생성하면 새 버전이 누적되고, 이전 답변과 수정 답변은 모두 immutable turn으로 남는다.

적응형 인터뷰는 아직 LLM이 아니다. `question-bank-v1.json`을 coverage rubric과 후보 pool로 사용해 deterministic selector가 부족한 축과 다음 후보 질문을 계산한다. Opportunity draft도 실제 자동화 분석이 아니라 `schemas/opportunity-v1.schema.json`을 통과하는 deterministic mock analyzer 결과다.

M3까지 의도적으로 구현하지 않는 것:

- 실제 LLM 호출
- STT 및 음성 녹음
- 외부 업무 시스템 실행
- 실제 자격증명 수집
- 실제 자동화 후보 분석
- 실제 G1 명세 생성

## M4 deterministic opportunity scoring

M4는 M3의 단순 opportunity draft를 근거 기반 scoring engine으로 교체한다. 엔진은 LLM을 호출하지 않고 schema-valid Work Model의 `steps`, `artifacts`, `systems`, `rules`, `decisions`, `exceptions`, `pain_points`, `constraints`, `evidence_summary`, `understanding_gate`만 읽어 아래 차원을 분리해 계산한다.

- `value`: 반복 단계, manual touch, pain point, metric 존재 여부
- `feasibility`: 구조화된 입력·출력, 시스템 접근 방식, 규칙·결정 명확성
- `risk`: 제품 안전 정책을 제외하고 통제 후 남은 실제 업무의 residual risk
- `evidence_confidence`: source ref, confirmed claim rate, open gap, contradiction
- `oversight`: 사람이 유지해야 하는 승인·예외 처리 수준

M4는 단일 총점을 만들지 않는다. 결과는 `portfolio_class`와 `gate.result`로 나뉘며, gate는 `BLOCKED`, `DISCOVERY_NEEDED`, `ENABLE_FIRST`, `READY_FOR_DESIGN` 중 하나다. `READY_FOR_DESIGN`은 G1 설계로 넘어갈 준비 여부만 뜻하며 G1 명세를 생성하지 않는다.

추가 API:

- `POST /v1/projects/{project_id}/opportunities/analyze`
- `GET /v1/projects/{project_id}/opportunities`
- `GET /v1/opportunities/{opportunity_id}`
- `POST /v1/opportunities/{opportunity_id}/validate`
- `GET /v1/interviews/{interview_id}/readiness`
- `GET /v1/projects/{project_id}/readiness`
- `GET /v1/projects/{project_id}/opportunities/diff`

M4에서도 의도적으로 구현하지 않는 것:

- 실제 LLM 판단
- STT 및 음성 녹음
- 외부 시스템 실행
- 실제 자격증명 수집
- 실제 G1 명세 생성

### Discovery Recovery Loop

`DISCOVERY_NEEDED`는 자동화 후보가 거절되었다는 뜻이 아니라, Work Model에 설계 판단에 필요한 근거가 부족하다는 뜻이다. `BLOCKED`도 현재 근거와 위험 경계로는 다음 단계가 닫혀 있음을 뜻한다. 두 결과에서는 웹의 **Discovery recovery** 패널이 시스템/도구, 입출력, 규칙, 예외, 승인, 지표, 비범위, source ref의 부족한 축과 `question-bank-v1.json` 기반 추가 질문을 표시한다.

사용자 확인 순서는 다음과 같다.

1. `복구 시작`으로 `FINALIZED` 인터뷰를 recovery 전용 경로에서 `NEEDS_EVIDENCE`로 연다.
2. 실제 최근 사례를 기준으로 구조화된 추가 증거를 저장한다. 답변은 기존 turn을 덮어쓰지 않는다.
3. `Work Model 재생성 준비` 후 기존 Work Model 생성 버튼으로 새 버전을 만든다.
4. 생성된 모델을 Playback에서 사용자가 직접 승인한다.
5. `Opportunity 재분석`으로 새 opportunity를 append-only로 저장하고 readiness를 다시 확인한다.

`READY_FOR_DESIGN` 또는 `ENABLE_FIRST`일 때만 Design Package 생성이 가능하다. `DISCOVERY_NEEDED`와 `BLOCKED`에서는 API와 웹 버튼이 모두 생성을 막고 이유를 표시한다. 이 흐름은 deterministic label parser와 고정 질문 규칙이며 실제 LLM adaptive interview는 아니다.

### M8.1 Gate Calibration

M8.1은 `constraint-no-external-execution` 같은 제품 안전 정책을 Work Model과 근거 추적에는 유지하되 실제 업무 위험 점수에는 더하지 않는다. 위험과 예외는 존재 여부가 아니라 통제 상태로 분류한다.

- 통제된 위험: 명시된 control, residual level 2 이하, `CORROBORATED`/`CONFIRMED` 상태, source ref가 모두 존재
- 통제된 예외: condition, handling, 강한 evidence state, source ref가 모두 존재
- 통제된 권한 경계: 사람의 최종 판단·승인 경계, control, residual level, source ref가 모두 존재
- 미해결 위험: 위 통제 정보가 없거나 근거가 약한 실제 privacy/security/legal/financial/safety/quality 위험
- `residual_risk`: 미해결 위험·예외·권한·모순과 통제 후 잔여 수준만 반영

`READY_FOR_DESIGN` 임계값은 낮추지 않았다. feasibility `>= 70`, evidence confidence `>= 0.75`, residual risk `<= 2`를 모두 만족하고, 구조화 입출력·시스템·규칙·통제된 예외·승인 경계·source ref가 있으며 open gap/contradiction이 없어야 한다. 웹 M4 패널은 현재 gate, 세 점수, 확인된 통제, 미해결 위험, blocker, FULL_G1 경로 상태를 함께 표시한다.

정상 복구 검증 경로는 다음과 같다.

`DISCOVERY_NEEDED → 추가 증거 → Work Model 새 버전 → Playback 승인 → READY_FOR_DESIGN → FULL_G1 → FULL_G1_BLUEPRINT → export_ready → M7 PASS → M8 READY`

추가 API:

- `GET /v1/projects/{project_id}/discovery-guidance`
- `POST /v1/projects/{project_id}/discovery/reopen`
- `POST /v1/projects/{project_id}/discovery/reanalyze`

별도 DB migration은 추가하지 않았다. 기존 `interview_sessions.status`, append-only Work Model/opportunity, `answers`/`turns`, `audit_events`가 복구 상태와 `DISCOVERY_REOPENED`/`DISCOVERY_REANALYZED` 추적에 필요한 데이터를 모두 보존한다. 다음 M9/G2 후보는 실제 LLM 기반 단일 질문 후속 인터뷰, reviewer feedback/revision loop, 제한된 starter scaffold 경계다.

## M5 G1 Design Package Draft

M5는 M4의 schema-valid opportunity와 readiness 결과를 입력으로 받아 `schemas/design-package-v1.schema.json`을 통과하는 G1 design package 초안을 생성한다. `READY_FOR_DESIGN`은 `FULL_G1`, `ENABLE_FIRST`는 `ENABLEMENT_PREP` 패키지로 제한된다. `BLOCKED`와 `DISCOVERY_NEEDED`는 패키지 생성을 거부한다.

M5 패키지는 아래 내용을 포함한다.

- problem, target users, scope, non-goals
- user flow, data contract, system assumptions
- human oversight, risks and controls
- acceptance tests, implementation backlog, open questions
- source Work Model/opportunity/evidence refs

추가 API:

- `POST /v1/opportunities/{opportunity_id}/design-package`
- `GET /v1/opportunities/{opportunity_id}/design-packages`
- `GET /v1/projects/{project_id}/design-packages`
- `GET /v1/design-packages/{package_id}`
- `POST /v1/design-packages/{package_id}/validate`

M5에서 생성하는 것은 G1 설계 패키지 초안이다. 실제 코드 생성, 외부 업무 시스템 실행, 자격증명 수집, 실제 G1 구현은 포함하지 않는다.

## M6 G1 Solution Blueprint

M6는 M5 design package를 입력으로 받아 `schemas/blueprint-v1.schema.json`을 통과하는 G1 Solution Blueprint preview를 생성한다. `READY_FOR_DESIGN` + `FULL_G1`은 export-ready full blueprint가 되고, `ENABLE_FIRST` + `ENABLEMENT_PREP`은 blocker/follow-up 중심의 limited blueprint로 남는다.

추가 API:

- `POST /v1/design-packages/{package_id}/blueprint`
- `GET /v1/design-packages/{package_id}/blueprints`
- `GET /v1/projects/{project_id}/blueprints`
- `GET /v1/blueprints/{blueprint_id}`
- `POST /v1/blueprints/{blueprint_id}/validate`
- `GET /v1/blueprints/{blueprint_id}/export/json`
- `GET /v1/blueprints/{blueprint_id}/export/markdown`

## M7 Evaluation & Pilot Prep

M7는 실제 파일럿을 실행하지 않는다. R009 기준을 deterministic evaluation run으로 옮겨 24개 fixture corpus, work model completeness, evidence traceability, opportunity scoring consistency, design package completeness, blueprint completeness, safety/non-goal compliance, interview burden을 평가한다.

추가 API:

- `POST /v1/projects/{project_id}/evaluation-runs`
- `GET /v1/projects/{project_id}/evaluation-runs`
- `GET /v1/evaluation-runs/{run_id}`
- `POST /v1/evaluation-runs/{run_id}/validate`

## M8 Limited Release Readiness

M8는 실제 배포가 아니다. consent/audit/deletion readiness, schema validation coverage, export readiness, safety non-goal enforcement, monitoring placeholder, support/deletion runbook, pilot metrics definition을 계산해 `schemas/release-readiness-v1.schema.json` 리포트로 저장한다.

추가 API:

- `POST /v1/projects/{project_id}/release-readiness`
- `GET /v1/projects/{project_id}/release-readiness`
- `GET /v1/release-readiness/{report_id}`
- `POST /v1/release-readiness/{report_id}/validate`

M6~M8.1에서 생성하는 것은 G1 설계 preview와 QA/release-prep 문서다. 실제 LLM 호출, STT/음성 녹음, 외부 업무 시스템 실행, 실제 자격증명 수집, 실제 앱 코드 생성, 운영 배포는 포함하지 않는다.

## M9 Implementation Package와 CODEGEN_READY

M9는 `DESIGN_READY`, `IMPLEMENTATION_READY`, `CODEGEN_READY`를 구분한다.

- `DESIGN_READY`: M8의 FULL_G1 blueprint는 있으나 구현 계약의 핵심 필드가 없거나 미확정이다.
- `IMPLEMENTATION_READY`: runtime, workflow, schema, mapping, rule, exception, approval, adapter 계약은 있지만 fixture나 검증 근거가 부족하다.
- `CODEGEN_READY`: critical field의 `UNKNOWN`/미해결 참조가 없고, 정상·오류·예외·승인 필요 fixture가 각각 확인되었으며, DAG·schema·traceability·보안 검사를 모두 통과했다.

웹의 **M9 Implementation package** 패널에서 CSV/JSON/XLSX sample을 업로드하면 컬럼, 자료형, 필수값과 예제값을 추출한다. 사용자가 schema를 확인한 뒤 acceptance 사례별 input/expected fixture 선택기로 계약에 연결한다. 원본, 추출 결과, 사용자 확인, 요구사항, package는 append-only로 저장된다.

추가 API:

- `GET /v1/implementation-requirements/template`
- `POST|GET /v1/projects/{project_id}/evidence-files`
- `POST /v1/evidence-files/{evidence_file_id}/confirm`
- `POST /v1/projects/{project_id}/implementation-requirements`
- `POST|GET /v1/projects/{project_id}/implementation-packages`
- `GET /v1/implementation-packages/{package_id}`
- `POST /v1/implementation-packages/{package_id}/validate`
- `GET /v1/implementation-packages/{package_id}/codegen-readiness`
- `GET /v1/implementation-packages/{package_id}/export.zip?mode=draft|codegen`

CODEGEN_READY ZIP 구조:

```text
manifest.json
README.md
source/{work-model,opportunity,design-package,blueprint}.json
contracts/{workflow,integrations,input.schema,output.schema,mappings,decisions,exceptions,approvals}.json
implementation/{stack.json,architecture.md,modules.json,env.example,deployment.md}
tests/acceptance-tests.json
tests/fixtures/input/*
tests/fixtures/expected/*
traceability/evidence-map.json
```

`manifest.json`은 파일별 SHA-256과 크기를 기록한다. codegen export는 모든 참조 대상, fixture output schema, DAG 연결, 4종 acceptance case, 절대 경로, secret 유사 값까지 재검증한다. DRAFT ZIP은 blocker 확인용이며 구현 전달 승인을 뜻하지 않는다.

Artifact-only blind-build는 export ZIP을 별도 임시 디렉터리에 풀고 저장소 코드, 실행 중 API, DB 없이 ZIP의 mapping과 fixture만 사용해 reference automation을 생성한다. 네 acceptance case를 실행해 기대 JSON과 의미적으로 동일한지 검사한다.

```bash
cd apps/api
python -m work_discovery_api.scripts.blind_build_smoke /path/to/codegen-ready.zip
```

M9는 구현 가능한 계약과 fixture를 생성하지만 실제 자동화 앱 코드를 ZIP에 생성하지 않는다. 실제 외부 시스템 실행, 자격증명 값 수집, production 배포도 계속 금지한다.

새 의존성:

- `defusedxml`: 신뢰할 수 없는 XLSX 내부 XML을 외부 엔터티 확장 없이 분석
- `psycopg[binary]`: `DATABASE_URL` 기반 PostgreSQL 저장소 연결
- `ky`: 웹 UI의 API 호출 클라이언트
- `playwright`: 로컬 웹 스모크 검증

## 핵심 설계 원칙

1. **자동화 전에 가치와 프로세스를 본다.** 없애거나 단순화할 수 있는 일을 먼저 자동화하지 않는다.
2. **한 개의 총점으로 결정하지 않는다.** 가치, 실행 가능성, 위험, 증거 신뢰도, 필요한 인간 감독 수준을 분리한다.
3. **설명과 실제 사례를 구분한다.** 일반론보다 최근 실제 사례, 예외 사례, 실패 사례를 우선 수집한다.
4. **사실·추론·검증 상태를 분리한다.** 사용자 발언, AI 추론, 문서 증거, 사용자 확인을 같은 사실처럼 취급하지 않는다.
5. **중요 정보는 묵시적으로 채우지 않는다.** 권한, 책임, 개인정보, 예외, 완료 조건은 사용자 확인 없이는 확정하지 않는다.
6. **사람의 역할을 없애는 것이 목적이 아니다.** 정보 제공, 초안, 추천, 승인 후 실행, 제한적 자율 실행을 구분한다.
7. **모든 명세는 근거로 추적 가능해야 한다.** 요구사항과 추천은 인터뷰 답변 또는 증거에 연결된다.
8. **MVP는 실제 시스템을 조작하지 않는다.** 업무를 이해하고 설계 문서를 만드는 데 집중한다.

## MVP 한 문장

> 한국어 지식노동자가 하나의 반복적인 디지털 업무를 텍스트·음성으로 설명하면, AI가 확인 가능한 업무 지도와 1~3개의 개선·자동화 후보를 만들고, 선택된 후보의 개발 가능한 솔루션 패키지를 내보낸다.

## 근거로 사용한 방법론·표준

- Lean의 가치·가치흐름·흐름·당김·완전성 원칙과 Value Stream Mapping
- Six Sigma DMAIC의 정의·측정·분석·개선·관리 구조
- BPMN, DMN, CMMN의 프로세스·의사결정·비정형 사례 모델
- O*NET의 직무·업무·활동·맥락 구조
- W3C PROV의 근거 및 출처 추적 개념
- Applied Cognitive Task Analysis와 Critical Decision Method의 실제 사례 기반 인지 인터뷰
- OMX deep-interview의 단일 질문, 취약 차원 우선, 압박 질문, 종료 게이트
- NIST AI RMF·Privacy Framework·SSDF 및 OWASP LLM 위험 분류

이 문서는 제품의 초기 가설이다. 점수 가중치와 평가 임계값은 파일럿 데이터와 전문가 검토로 보정해야 한다.
