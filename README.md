# Work Discovery AI Blueprint

버전: v0.1  
상태: 연구·MVP 설계 기준선  
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

브라우저에서 `http://127.0.0.1:3000`을 열면 프로젝트 생성, 인터뷰 생성, 동의, 10문항 답변, Work Model 생성, Playback 승인/거절, 추가 증거, 답변 수정, 재빌드, coverage/next-question, opportunity draft, 감사 이벤트 조회까지 클릭으로 확인할 수 있다.

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

## M1/M2/M3 검증

```bash
cd apps/api
python -m pytest
python -m ruff check .
python -m basedpyright
python -m work_discovery_api.scripts.schema_smoke
python -m work_discovery_api.scripts.api_smoke
python -m work_discovery_api.scripts.server_smoke

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

새 의존성:

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
