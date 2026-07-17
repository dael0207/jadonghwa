# 확정 사항, 남은 결정, 바로 다음 작업

## 0. 구현 진행 상태

- M0: 프로젝트/인터뷰, 동의 게이트, 고정 10문항, immutable answer turn, schema validation 완료
- M1/M2: repository 경계, PostgreSQL 선택 경로, 웹 클릭 흐름, deterministic Work Model builder, playback confirm/reject 완료
- M3: reject 후 evidence/revision/rebuild 루프, coverage/next-question API, deterministic opportunity draft, provider interface 경계 완료
- M4: Work Model 근거 기반 deterministic opportunity scoring, readiness gate, opportunity diff, audit 추적, 웹 scoring 패널 완료
- M5: readiness-gated G1 design package draft, append-only package 저장/조회, schema validation, 웹 preview/validate 패널 완료
- M6: design package 기반 G1 Solution Blueprint preview, 품질 gate, JSON/Markdown export 완료
- M7: deterministic evaluation run, 24개 fixture corpus, schema/audit 검증 완료
- M8: limited release readiness report, readiness checklist, 웹 preview/validate 패널 완료
- M4/M5 Recovery: `DISCOVERY_NEEDED`/`BLOCKED` guidance, recovery 전용 reopen, 추가 증거 기반 Work Model 재생성, Playback 재승인, append-only reanalysis, M5 웹 gate 완료
- M8.1: 제품 안전 정책과 실제 업무 위험 분리, 통제/미해결 위험·예외·권한 분류, residual-risk gate, 정상 Recovery의 FULL_G1~M8 READY 경로 완료
- M9: Implementation Package, 3단계 readiness gate, sample evidence 확인, CODEGEN_READY ZIP, 4종 fixture blind-build QA 완료
- 다음 G2 후보: CODEGEN_READY package 기반 제한된 starter scaffold, reviewer feedback/revision loop, 실제 파일럿 QA 운영 기준을 검토한다. 실제 외부 실행과 자격증명 수집은 계속 비범위로 둔다.

## 1. 이번 설계에서 확정한 사항

### 제품 정체성

- 업무 자동화 빌더가 아니라 **업무 발견·모델링·자동화 설계 시스템**이다.
- 사용자가 자동화 대상을 모르는 상태에서 시작한다.
- 텍스트와 음성을 모두 받되, 음성은 전사 확인 후에만 분석한다.
- 인터뷰의 결과는 요약문이 아니라 근거가 연결된 업무 모델이다.
- 자동화 전에 삭제·통합·단순화·표준화를 검토한다.
- 자동화 추천은 단일 점수가 아니라 가치·실행 가능성·위험·신뢰도·감독 수준으로 나눈다.
- 첫 MVP는 실제 업무를 실행하지 않고 G1 개발 명세까지 만든다.

### MVP 사용자

- 한국어를 사용하는 개인·직원·중소기업 지식노동자
- 이메일, 파일, 스프레드시트, 브라우저, 사내 시스템을 사용하는 디지털 사무 업무

### 첫 기준 업무

- 월간 보고서 작성
- 보조 검증 업무: 이메일 문의 분류, 송장/증빙 처리, 규제·품질 문서 검토

### 개인정보 기본값

- 녹음 전 명시적 동의
- 전사 확인 후 원본 오디오 삭제
- 사용자 원문과 AI 추론 표시 분리
- 실제 시스템 자격증명 수집 금지
- 프로젝트 내보내기·삭제 지원

---

## 2. 개발 시작 전에 제품 소유자가 결정할 사항

### D1 — 첫 판매 대상

선택지:

1. 개인 사용자 셀프서비스
2. 중소기업 팀 단위
3. 자동화 컨설턴트·개발사 도구

**권장:** 2번을 주 대상으로 하되, 3번 사용 시나리오를 함께 검증한다. 회사 내부 자료와 실제 도입 승인 때문에 개인 단독보다 팀 단위가 최종 가치 실현에 유리하다.

### D2 — 첫 파일럿 산업

선택지:

- 범용 사무직
- 제조·품질·규제 문서
- 회계·재무 운영
- 영업 운영
- 고객 지원

**권장:** 범용 월간 보고 업무로 제품 흐름을 만들고, 사용자가 잘 아는 제조·품질·규제 문서 업무를 두 번째 세로형 파일럿으로 사용한다.

### D3 — AI·STT 공급 방식

결정할 내용:

- 외부 API 사용 가능 여부
- 데이터 저장 지역
- 모델 학습 사용 방지 계약·설정
- 보존 기간
- 공급자 장애 시 대체 전략

**권장:** MVP는 공급자 추상화 계층을 두고 관리형 API로 시작하되, 민감 고객용 별도 배포 경로를 열어둔다.

### D4 — 인터뷰 모드

권장 기본값:

- Quick: 업무 개요와 후보 탐색, 최대 6개 적응형 질문
- Standard: 업무 1개 설계, 최대 15개 적응형 질문
- Deep: 복잡한 판단·예외 업무, 최대 30개 적응형 질문

질문 수는 절대 종료 조건이 아니라 피로 방지 상한이다.

### D5 — G2 코드 생성 포함 여부

**권장:** 첫 MVP에서는 제외한다. G1 명세의 품질을 평가한 뒤, 반복되는 솔루션 템플릿에만 제한적으로 추가한다.

### D6 — 수익 모델

지금 확정할 필요는 없지만 파일럿 전에 아래 중 하나를 정한다.

- 프로젝트당 결제
- 사용자/워크스페이스 구독
- 컨설턴트 좌석 + 고객 프로젝트
- 분석 무료, 설계·개발 연결 유료

**초기 검증 권장:** 프로젝트 단위 유료 의향과 컨설턴트 좌석 가치를 함께 조사한다.

---

## 3. 이전 M0 구현 작업 기록

1. 저장소 생성과 모듈 구조 확정
2. ADR-001: MVP 비범위와 실제 실행 금지 기록
3. PostgreSQL 마이그레이션 초안
4. 제공된 3개 JSON Schema를 공용 패키지로 등록
5. OpenAPI에서 서버 스텁 생성
6. 프로젝트·인터뷰 상태 머신 구현
7. ConsentRecord와 AuditEvent 구현
8. 텍스트 답변 저장과 불변 Turn 이벤트 구현
9. Claim Extractor의 구조화 출력 계약 작성
10. Work Model 버전 생성·검증 API 구현
11. 질문 뱅크 로더와 고정 질문지 구현
12. 테스트용 월간 보고 예시 데이터로 통합 테스트
13. 삭제 작업과 오디오 보존 정책 테스트
14. 클릭 가능한 전체 UX 프로토타입 제작
15. 파일럿 참여자 모집 및 동의서 초안

---

## 4. M0 완료 조건

- 로컬에서 프로젝트와 인터뷰를 생성할 수 있다.
- 동의 없이는 답변·녹음을 받을 수 없다.
- 텍스트 답변이 불변 이벤트로 저장된다.
- Work Model JSON이 스키마 검증을 통과한다.
- 상태 머신이 잘못된 전이를 거부한다.
- 예시 업무 모델·기회 카드가 자동 테스트를 통과한다.
- 프로젝트 삭제 요청이 모든 파생 데이터 삭제 목록을 만든다.
- 아직 LLM을 붙이지 않아도 고정 질문지 전체 흐름이 동작한다.

---

## 5. 완료된 구현 작업 — M5~M8

1. `schemas/design-package-v1.schema.json` 추가
2. deterministic Design Package Builder 구현
3. `READY_FOR_DESIGN`은 `FULL_G1`, `ENABLE_FIRST`는 `ENABLEMENT_PREP`로 제한
4. `BLOCKED`와 `DISCOVERY_NEEDED` opportunity의 package 생성을 거부
5. in-memory/PostgreSQL 저장소와 migration에 append-only `design_packages` 추가
6. package 생성/목록/조회/검증 API와 audit event 추가
7. 웹 workbench에 M5 package 생성, 목록, JSON preview, acceptance tests 요약, validate 패널 추가
8. 실제 LLM, STT, 외부 시스템 실행, 자격증명 수집, 실제 앱 코드 생성은 비범위로 유지
9. `schemas/blueprint-v1.schema.json`과 deterministic Blueprint Builder 추가
10. M6 blueprint 생성/조회/검증/JSON export/Markdown export API와 audit event 추가
11. `schemas/evaluation-run-v1.schema.json`, `examples/evaluation-corpus-v1.json` 기반 M7 deterministic evaluation runner 추가
12. `schemas/release-readiness-v1.schema.json` 기반 M8 release readiness evaluator 추가
13. in-memory/PostgreSQL 저장소와 migration에 append-only `blueprints`, `evaluation_runs`, `release_readiness_reports` 추가
14. 웹 workbench에 M6/M7/M8 생성, 목록, JSON preview, validate, release status 패널 추가

---

## 6. 완료된 구현 작업 — M9

1. workflow, integration, implementation package, codegen readiness, manifest, acceptance fixture schema 추가
2. `DESIGN_READY`, `IMPLEMENTATION_READY`, `CODEGEN_READY` gate 분리
3. CSV/JSON/XLSX evidence 안전 분석과 append-only 원본·추출·확인 추적
4. in-memory/PostgreSQL 저장소와 migration에 evidence와 implementation package 추가
5. runtime, DAG, schema, mapping, rule, exception, approval, adapter, module, 운영 요구사항 계약 생성
6. DRAFT/CODEGEN_READY ZIP 분리와 파일별 checksum·traceability 검증
7. 정상·오류·예외·승인 필요 fixture를 ZIP만으로 실행하는 artifact-only blind-build QA 추가
8. 웹 workbench에 blocker, 추가 질문, schema 확인, fixture binding, gate, ZIP 다운로드 패널 추가

---

## 7. 바로 다음 구현 작업 — G2 후보

1. 제한된 starter scaffold template 범위 결정: 실제 실행 없는 파일 구조 preview인지, 다운로드 가능한 skeleton인지 구분
2. Reviewer feedback/revision API와 append-only revision history 추가
3. Blueprint revision diff와 acceptance-test coverage drift 표시
4. 실제 파일럿 전에 QA runbook, deletion drill, support escalation checklist를 운영 문서로 분리
5. LLM/STT 연결 전 provider boundary, prompt/input policy, redaction policy 테스트 강화
6. 외부 시스템 실행과 실제 자격증명 수집은 별도 G2 이후 결정으로 유지
7. deterministic recovery 질문을 실제 LLM 기반 한 질문씩 이어가는 adaptive interview로 교체하되 consent, immutable turn, playback, audit 경계를 유지
