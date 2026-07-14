# R004 — Work Ontology v1

## 1. 설계 목적

온톨로지는 인터뷰 답변을 단순 요약문이 아니라 **검증 가능한 업무 모델**로 변환하기 위한 공통 언어다. 초기 버전은 완전한 시맨틱 웹보다 제품 구현에 적합한 JSON 기반 애플리케이션 온톨로지를 사용한다.

프로세스는 BPMN 계열 개념, 판단은 DMN 계열 개념, 비정형·사례 중심 업무는 CMMN 계열 개념, 직무와 업무 맥락은 O*NET 계열 개념, 근거 추적은 W3C PROV 계열 개념을 참고한다.

---

## 2. 모델의 네 층

### 2.1 조직·역할 층

- `Organization`
- `OrgUnit`
- `Role`
- `PersonAlias`
- `Stakeholder`
- `Responsibility`

### 2.2 업무·프로세스 층

- `Goal`
- `Outcome`
- `Metric`
- `Process`
- `CaseType`
- `Task`
- `Step`
- `Action`
- `TriggerEvent`
- `EndEvent`
- `Flow`
- `Variant`
- `Dependency`

### 2.3 정보·판단·통제 층

- `InputArtifact`
- `OutputArtifact`
- `DataField`
- `Document`
- `ToolSystem`
- `Channel`
- `Decision`
- `Rule`
- `Exception`
- `Risk`
- `Control`
- `Permission`

### 2.4 개선·설계 층

- `PainPoint`
- `WasteObservation`
- `AutomationCandidate`
- `SolutionOption`
- `Requirement`
- `NonGoal`
- `AcceptanceCriterion`
- `BenefitEstimate`
- `Constraint`
- `Assumption`

### 2.5 인터뷰·근거 층

- `InterviewSession`
- `Turn`
- `Question`
- `Answer`
- `TranscriptSegment`
- `Claim`
- `Evidence`
- `Validation`
- `ConsentRecord`
- `AuditEvent`

---

## 3. 핵심 관계

| 관계 | 의미 |
|---|---|
| `contains` | 프로세스가 작업·단계를 포함 |
| `performed_by` | 역할이 업무를 수행 |
| `responsible_for` | 결과 또는 승인에 책임 |
| `achieves` | 업무가 목표·결과에 기여 |
| `triggered_by` | 이벤트가 업무를 시작 |
| `consumes` | 입력·데이터를 사용 |
| `produces` | 출력·결과물을 생성 |
| `uses_tool` | 시스템·앱·채널을 사용 |
| `followed_by` | 단계 순서 |
| `branches_on` | 판단에 따라 흐름 분기 |
| `governed_by` | 규칙·정책·통제를 따름 |
| `handles_exception` | 예외 상황을 처리 |
| `depends_on` | 다른 업무·사람·시스템에 의존 |
| `causes_pain` | 단계가 불편·지연·오류를 야기 |
| `targets` | 후보가 개선할 대상을 가리킴 |
| `requires` | 구현 전제·권한·데이터를 요구 |
| `supported_by` | 주장·추천이 근거로 뒷받침됨 |
| `validated_by` | 사용자 또는 전문가가 확인 |
| `derived_from` | AI 추론이 원본 답변·증거에서 파생 |

---

## 4. 모든 업무 모델에 필요한 핵심 필드

### 4.1 업무 식별

- 업무명
- 업무 소유자와 수행자
- 목적과 결과 수신자
- 시작 조건과 종료 조건
- 정상 흐름과 주요 변형

### 4.2 실행 구조

- 단계와 순서
- 각 단계의 행동
- 입력과 출력
- 사용 도구·시스템·채널
- 역할과 권한
- 선행·후행 의존성

### 4.3 판단 구조

- 판단 지점
- 판단 기준과 필요한 데이터
- 규칙·임계값·우선순위
- 승인 또는 에스컬레이션 조건
- 예외와 예외 처리
- 사람의 암묵적 단서

### 4.4 성과·문제 구조

- 빈도와 처리량
- 평균·최소·최대 처리 시간
- 대기 시간
- 오류율과 재작업
- 불편·병목·중복
- 품질·규정·고객 영향

### 4.5 증거·검증 구조

- 출처: 텍스트/음성/문서/로그/사용자 수정
- 원문 위치 또는 세그먼트
- 사실 상태
- 신뢰도
- 확인자와 확인 시점
- 모순 여부

---

## 5. 주장 상태 모델

모든 사실성 필드는 다음 상태 중 하나를 가진다.

- `UNKNOWN`: 아직 정보 없음
- `CLAIMED`: 사용자가 말했지만 구체적 검증 없음
- `INFERRED`: AI가 문맥에서 추론
- `CORROBORATED`: 별도 사례·문서·로그와 일치
- `CONFIRMED`: 사용자가 명시적으로 확인
- `DISPUTED`: 서로 다른 답변·증거가 충돌
- `NOT_APPLICABLE`: 해당 업무에는 적용되지 않음

AI 추론은 화면에서 명확히 표시하고, 중요한 필드를 `INFERRED` 상태로 종료하지 않는다.

---

## 6. 시간축과 버전

업무는 현재 상태와 목표 상태를 분리한다.

- `AS_IS`: 지금 실제로 수행되는 방식
- `TO_BE`: 개선 후 제안 방식
- `PILOT`: 제한된 시험 운영 방식
- `RETIRED`: 더 이상 사용하지 않는 방식

각 모델은 `version`, `valid_from`, `valid_to`, `change_reason`, `approved_by`를 가진다.

---

## 7. 업무 이해 완료 게이트

다음 항목은 `CONFIRMED`, `CORROBORATED` 또는 명시적 `UNKNOWN`이어야 한다.

1. 소유자·수행자·수신자
2. 목적과 성공 결과
3. 시작·종료 조건
4. 주요 단계와 순서
5. 핵심 입력·출력
6. 사용 도구·시스템
7. 주요 판단과 규칙
8. 대표 예외와 처리 방식
9. 빈도·처리량·시간 범위
10. 불편·오류·위험
11. 최근 실제 사례 한 건 이상
12. 사용자 업무 지도 확인

`UNKNOWN`이 허용되더라도 자동화 결정을 바꿀 수 있는 중요한 미지 정보라면 인터뷰 종료가 아니라 `NEEDS_EVIDENCE`로 이동한다.

---

## 8. 자동화 후보 완료 게이트

- 명확한 대상 단계
- 해결할 문제
- 추천 방식과 대안
- 자동화 범위와 인간 역할
- 기대 효과 범위
- 실행 가능성
- 위험과 통제
- 전제조건
- 근거와 신뢰도
- 하지 않을 것
- 검증 실험
- 수용 기준

---

## 9. 예시

```json
{
  "process": {
    "name": "월간 매출 보고서 작성",
    "goal": "경영진이 전월 실적과 이상 징후를 확인한다",
    "trigger": "매월 첫 영업일",
    "owner_role": "영업기획 담당자"
  },
  "steps": [
    {
      "id": "step-1",
      "action": "ERP에서 매출 데이터를 다운로드한다",
      "uses_tool": ["ERP"],
      "produces": ["sales.csv"],
      "status": "CONFIRMED"
    },
    {
      "id": "step-2",
      "action": "전월 파일에 데이터를 붙여넣는다",
      "uses_tool": ["Excel"],
      "pain_points": ["열 순서가 바뀌면 수식 오류가 발생한다"]
    }
  ],
  "decisions": [
    {
      "question": "이상 매출로 표시할 것인가?",
      "rule": "전월 대비 30% 이상 증감",
      "exception": "신규 거래처는 담당자 검토"
    }
  ]
}
```

---

## 10. 초기 구현 원칙

- PostgreSQL의 정규화 테이블과 JSONB 스냅샷을 함께 사용한다.
- 관계형 그래프가 필요해질 때 별도 그래프 데이터베이스를 검토한다.
- 원문 답변은 불변 기록으로 보존하고, 모델은 버전 관리한다.
- 모든 추출 엔터티에 `source_refs`를 저장한다.
- 출력은 JSON Schema로 검증한다.
