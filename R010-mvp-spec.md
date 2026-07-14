# R010 — MVP Product & Technical Specification

## 1. 제품명

작업명: **Work Discovery AI**  
한국어 가칭: **업무발견 AI**

---

## 2. 문제

자동화 도구를 사용할 수 있는 사람도 “내 업무 중 무엇을 자동화해야 하는지”, “어떤 정보를 준비해야 하는지”, “효과가 어느 정도인지”를 모르면 시작하기 어렵다. 기존 워크플로 빌더는 대체로 사용자가 자동화 대상을 이미 알고 있다는 전제에서 시작한다.

MVP는 사용자가 업무를 설명하는 것만으로 **자동화 전 단계의 발견·구조화·검증·설계**를 지원한다.

---

## 3. MVP 목표

> 한국어 지식노동자가 하나의 반복적인 디지털 업무를 텍스트 또는 음성으로 설명하면, AI가 적응형 질문을 통해 업무를 검증 가능한 구조로 만들고, 1~3개의 개선·자동화 후보를 비교한 뒤, 선택된 후보의 PRD와 기술 설계를 생성한다.

---

## 4. 초기 대상

### 포함

- 개인 또는 중소기업의 지식노동자
- 이메일, 파일, 스프레드시트, 브라우저, 사내 시스템을 사용하는 업무
- 반복되는 보고, 정리, 조회, 입력, 검토, 추적, 문서 처리
- 업무 수행자가 직접 설명하고 확인할 수 있는 경우

### 제외

- 물리 설비·로봇 제어가 중심인 업무
- 의료·법률·재무의 고위험 결정을 자율화하는 용도
- 직원 감시를 위한 상시 화면·행동 수집
- 회사 전체 ERP 로그 기반 프로세스 마이닝
- 운영 시스템에 직접 로그인하여 실행

---

## 5. 핵심 사용자 여정

```text
1. 회원가입/워크스페이스 생성
2. AI·녹음·데이터 처리 고지 및 동의
3. 새 업무 분석 프로젝트 생성
4. 초기 질문지에 텍스트 또는 음성으로 답변
5. 음성 전사를 편집하고 확정
6. AI가 첫 업무 지도 생성
7. 사용자가 지도·추론·미확정 항목 검토
8. AI가 한 번에 한 질문씩 딥인터뷰
9. 사용자 확인을 거쳐 업무 모델 확정
10. AI가 개선·자동화 후보 1~3개 생성
11. 가치·실행 가능성·위험·효과·사람 역할 비교
12. 사용자가 후보 하나 선택
13. PRD·업무 흐름·데이터·API·테스트 명세 생성
14. Markdown/JSON으로 내보내기 또는 프로젝트 삭제
```

---

## 6. 화면

### 6.1 Dashboard

- 프로젝트 목록
- 상태, 최근 활동, 미확정 질문
- 새 프로젝트
- 내보내기·삭제

### 6.2 Setup & Consent

- 사용 목적
- AI 생성 고지
- 녹음·전사·보존 정책
- 민감정보 주의
- 회사 자료 입력 권한 확인

### 6.3 Initial Intake

- 10개 질문지
- 질문별 텍스트/음성 전환
- 임시 저장
- 모름/건너뛰기

### 6.4 Voice & Transcript Editor

- 녹음 시작/일시정지/종료
- 전사 상태
- 타임스탬프 기반 텍스트
- 편집·다시 녹음·확정
- 오디오 삭제 예정 표시

### 6.5 Deep Interview

- 이전 답변 반영 요약
- 질문 한 개
- 질문 이유를 짧게 보기
- 텍스트/음성 답변
- 진행 상태: 목적/흐름/판단/예외/수치/권한
- 일시정지

### 6.6 Work Map Review

- 업무 목적·범위
- 단계별 흐름
- 판단·예외
- 입력·출력·도구
- 수치·불편·위험
- 사실/AI 추론/미확정 표시
- 직접 수정·확인

### 6.7 Opportunity Comparison

- 후보 1~3개
- 해결 방식
- 예상 효과 범위
- 가치·실행 가능성·위험·신뢰도
- 사람 역할과 자동화 수준
- 전제조건과 검증 실험
- 선택/보류

### 6.8 Solution Blueprint

- Executive brief
- AS-IS/TO-BE
- PRD
- 화면 흐름
- 데이터 모델
- API 초안
- 수용 기준
- 백로그
- 위험·보안·운영
- Markdown/JSON 내보내기

### 6.9 Privacy & Audit

- 동의 기록
- 보관 중인 오디오·파일
- 다운로드·삭제
- AI 처리 기록

---

## 7. P0 기능

1. 이메일 또는 소셜 로그인과 워크스페이스
2. 프로젝트·인터뷰 세션 생성/재개
3. 동의·고지·데이터 보존 설정
4. 초기 10문항 질문지
5. 브라우저 음성 녹음
6. STT 및 전사 편집·확정
7. Claim 추출과 source span 연결
8. Work Ontology v1 저장·버전 관리
9. 필드 커버리지·모순 평가
10. 적응형 한 질문 생성
11. 업무 지도 표시·수정·확정
12. ADF 기반 후보 1~3개 생성
13. 후보 비교·선택
14. G1 솔루션 패키지 생성
15. Markdown/JSON 내보내기
16. 오디오 자동 삭제·프로젝트 삭제
17. 감사 로그와 사용자 피드백

---

## 8. P1 기능

- PDF·스프레드시트·스크린샷 등 증거 업로드
- 팀원 초대와 공동 검증
- 여러 직원의 같은 프로세스 병합
- 기존 자동화 도구·API 인벤토리
- 템플릿 기반 Starter Scaffold
- 산업별 질문 팩
- 다국어
- 정량 효과 추적 대시보드

---

## 9. 명시적 비범위

- 운영 시스템 연결과 실제 작업 실행
- 생산 코드 자동 배포
- 무제한 범용 소프트웨어 생성
- ROI 보장
- 법률·규정 준수 최종 판단
- 화면 상시 녹화와 태스크 마이닝
- 네이티브 모바일 앱
- 회사 전체 조직·프로세스 분석
- 채용·평가·감시 목적 직원 프로파일링

---

## 10. 권장 아키텍처

### Frontend

- Next.js + TypeScript
- 반응형 웹
- 브라우저 MediaRecorder
- Work Map 시각화: 초기에는 Mermaid/커스텀 플로 차트

### Backend

- FastAPI + Python
- REST API
- 비동기 작업 큐
- LLM/STT 공급자 추상화
- Pydantic/JSON Schema 검증

### Data

- PostgreSQL
- JSONB 업무 모델 스냅샷
- S3 호환 오브젝트 스토리지
- 선택적 pgvector는 검색 요구가 생긴 뒤 도입

### Operations

- 관리형 인증
- 컨테이너 배포
- 구조화 로그, 추적 ID, 감사 이벤트
- 비밀 관리
- 환경별 분리

---

## 11. 서비스 경계

- `Identity/Workspace Service`
- `Project Service`
- `Interview Orchestrator`
- `Media & Transcription Service`
- `Ontology & Evidence Service`
- `Question Planning Service`
- `Automation Analysis Service`
- `Blueprint Generation Service`
- `Privacy & Audit Service`

MVP에서는 물리적 마이크로서비스보다 모듈형 모놀리스로 시작하되 경계를 코드 모듈과 인터페이스로 유지한다.

---

## 12. 핵심 데이터 테이블

- `workspaces`
- `users`
- `workspace_members`
- `projects`
- `interview_sessions`
- `turns`
- `questions`
- `answers`
- `audio_assets`
- `transcripts`
- `transcript_segments`
- `claims`
- `work_models`
- `work_entities`
- `work_relations`
- `evidence_items`
- `validations`
- `contradictions`
- `opportunities`
- `solution_specs`
- `artifacts`
- `consent_records`
- `audit_events`
- `deletion_jobs`

---

## 13. 핵심 API

- `POST /v1/projects`
- `GET /v1/projects/{project_id}`
- `DELETE /v1/projects/{project_id}`
- `POST /v1/projects/{project_id}/interviews`
- `POST /v1/interviews/{interview_id}/answers`
- `POST /v1/interviews/{interview_id}/audio`
- `POST /v1/transcripts/{transcript_id}/confirm`
- `POST /v1/interviews/{interview_id}/next-question`
- `GET /v1/projects/{project_id}/work-model`
- `PATCH /v1/projects/{project_id}/work-model`
- `POST /v1/projects/{project_id}/work-model/validate`
- `POST /v1/projects/{project_id}/opportunities/analyze`
- `GET /v1/projects/{project_id}/opportunities`
- `POST /v1/opportunities/{opportunity_id}/select`
- `POST /v1/opportunities/{opportunity_id}/blueprint`
- `GET /v1/artifacts/{artifact_id}`
- `POST /v1/projects/{project_id}/export`

---

## 14. AI 파이프라인

```text
확정 답변
  → Claim Extractor
  → Schema Validator
  → Ontology Merge
  → Contradiction/Coverage Evaluator
  → Question Planner
  → Interviewer
  → User Validation
  → ADF Analyzer
  → Opportunity Reviewer
  → Blueprint Generator
  → Traceability Validator
```

Extractor, Planner, Analyzer, Generator의 프롬프트와 출력 스키마를 분리한다.

---

## 15. 프라이버시·보안 요구

- AI 사용과 AI 생성 산출물 표시
- 녹음 전 명시적 동의
- 전사 확인 후 원본 오디오 기본 삭제
- 보존 기간 설정과 삭제 상태 표시
- 프로젝트 전체 다운로드·삭제
- 테넌트 격리
- 전송·저장 암호화
- 최소 권한과 관리자 접근 감사
- 외부 AI 공급자 학습 사용 방지 설정 확인
- 불필요한 개인정보 마스킹
- 업로드 자료의 프롬프트 인젝션 방어
- 생성 결과에 근거·가정·위험 표시
- 실제 작업 실행과 자격증명 수집 금지

법적 적용은 배포 국가와 고객 환경에 따라 별도 검토한다.

---

## 16. 품질·관찰 가능성

- 요청·세션·모델 버전 추적 ID
- 프롬프트·모델 버전 기록
- JSON 검증 실패율
- 질문 중복률
- 사용자 수정률
- 필드 커버리지
- 추천 confidence
- 삭제 작업 상태
- 오류·지연·비용 메트릭

사용자 원문을 운영 로그에 무분별하게 남기지 않는다.

---

## 17. 구현 마일스톤

### M0 — Foundation

- 저장소, CI, 환경, 인증, DB 마이그레이션
- 핵심 JSON Schema와 API 계약
- 개인정보·동의 정책 초안

### M1 — Clickable UX

- 전체 사용자 여정 프로토타입
- 질문지, 전사 편집, 업무 지도, 후보 비교, 명세 화면
- 5명 이상 사용성 검토

### M2 — Deterministic Interview Core

- 프로젝트·세션 상태 머신
- 텍스트 답변
- Claim·Ontology 저장
- 고정 질문지와 업무 지도 수정

### M3 — Voice

- 녹음·업로드·STT
- 전사 편집·확정
- 오디오 자동 삭제

### M4 — Adaptive Deep Interview

- 커버리지·모순 계산
- Question Planner
- 한 질문 루프
- 재생·사용자 확인

### M5 — Automation Discovery

- ADF 벡터 평가
- 하드 게이트
- 후보 1~3개와 검증 실험

### M6 — Blueprint Generation

- PRD·TO-BE·데이터·API·테스트·백로그
- 추적성 검증
- Markdown/JSON 내보내기

### M7 — Evaluation & Pilot

- 24개 업무 코퍼스
- 전문가 기준 정답
- 안전·정확도·인터뷰 부담 평가
- 임계값 보정

### M8 — Limited Release

- 소수 워크스페이스 배포
- 모니터링·지원·삭제 검증
- 실제 프로그램 제작으로 이어진 비율 측정

---

## 18. MVP 완료 정의

MVP는 다음이 한 흐름에서 작동할 때 완료다.

1. 사용자가 동의 후 프로젝트를 생성한다.
2. 텍스트와 음성으로 초기 질문에 답한다.
3. 모든 음성 답변은 전사 확인을 거친다.
4. AI가 근거가 연결된 업무 지도를 만든다.
5. 사용자가 추론과 미확정 항목을 수정·확인한다.
6. AI가 필요한 후속 질문을 중복 없이 한다.
7. 종료 게이트 후 1~3개의 개선·자동화 후보를 제시한다.
8. 각 후보에 가치·실행 가능성·위험·인간 역할·효과 범위가 있다.
9. 선택 후보에서 추적 가능한 G1 솔루션 패키지가 생성된다.
10. 사용자가 데이터를 내보내고 프로젝트와 오디오를 삭제할 수 있다.
11. 시스템은 어떤 외부 업무도 실제로 실행하지 않는다.

---

## 19. 첫 파일럿 시나리오

`월간 보고서 작성`을 기준 시나리오로 권장한다.

이유:

- 디지털 입력과 출력이 명확함
- 단계·도구·반복·오류를 설명하기 쉬움
- 규칙 자동화, 데이터 연동, AI 요약 등 복수 해결안을 비교 가능
- 고위험 자율 실행을 피하면서도 제품 가치를 보여주기 좋음

보조 시나리오:

- 이메일 문의 분류·답변 초안
- 송장/증빙 확인과 입력
- 규제·품질 문서 체크리스트 검토

---

## 20. 가장 큰 제품 위험

1. 사용자의 설명이 실제 업무와 다름
2. 인터뷰가 길어져 이탈
3. AI가 확신 있게 잘못된 업무 모델 생성
4. 효과를 과장해 신뢰 상실
5. 기존 도구로 충분한데 전용 앱을 과잉 추천
6. 개인정보·회사 기밀 입력
7. 좋은 명세가 실제 도입·변화관리로 이어지지 않음

대응은 실제 사례 중심 질문, 근거 추적, 사용자 확인, 다차원 판단, 명시적 비범위, 파일럿 측정으로 한다.
