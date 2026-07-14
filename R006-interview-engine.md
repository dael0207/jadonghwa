# R006 — Interview Engine v1

## 1. 책임

Interview Engine은 대화를 이어가는 챗봇이 아니라, 사용자 답변을 근거가 연결된 업무 모델로 점진적으로 변환하는 상태 기반 시스템이다.

---

## 2. 구성 요소

1. `ConsentService` — AI·녹음·데이터 처리 동의
2. `IntakeService` — 초기 질문지와 업무 선택
3. `MediaService` — 음성 업로드·보관·삭제
4. `TranscriptionService` — STT와 세그먼트 타임코드
5. `TranscriptConfirmation` — 사용자 수정·확정
6. `ClaimExtractor` — 답변에서 사실 주장 추출
7. `OntologyUpdater` — 엔터티·관계·상태 반영
8. `EvidenceStore` — 원문·문서·사용자 확인 연결
9. `CoverageEvaluator` — 업무 이해도와 미확정 필드 평가
10. `ContradictionDetector` — 답변·증거 간 충돌 탐지
11. `QuestionPlanner` — 다음 질문 목표 선택
12. `QuestionWriter` — 사용자 친화적 질문 생성
13. `PlaybackGenerator` — 업무 지도와 추론 재생
14. `ValidationService` — 사용자 승인·정정
15. `ArtifactService` — 분석 전달용 스냅샷 생성
16. `AuditPrivacyService` — 접근·삭제·보존 기록

---

## 3. 상태 머신

```text
CREATED
  → CONSENT_PENDING
  → CONSENTED
  → INTAKE_IN_PROGRESS
  → TRANSCRIBING            (음성 답변일 때)
  → TRANSCRIPT_CONFIRMATION  (음성 답변일 때)
  → MODEL_BUILDING
  → DEEP_INTERVIEW
  → PLAYBACK_CONFIRMATION
  → OPPORTUNITY_ANALYSIS_READY
  → FINALIZED
```

보조 상태:

- `PAUSED`
- `NEEDS_EVIDENCE`
- `NEEDS_HUMAN_REVIEW`
- `CONSENT_REVOKED`
- `ABORTED`
- `DELETION_PENDING`

상태 전이는 서버 측 규칙으로 검증한다. LLM이 상태를 임의로 변경하지 않는다.

---

## 4. 한 답변 처리 루프

```text
1. 답변 수신
2. 음성이면 전사하고 사용자 확인 대기
3. 확정 텍스트 정규화
4. 원문 구간과 연결된 Claim 추출
5. 엔터티·관계 후보 생성
6. 기존 모델과 병합
7. 모순 및 중복 탐지
8. 필드별 커버리지·신뢰도 계산
9. 종료 게이트 검사
10. 미충족이면 다음 질문 목표 선택
11. 질문 한 개 생성
12. 모든 변경과 근거 저장
```

---

## 5. AI 역할 분리

### 5.1 Extractor

- 사실 주장만 추출
- 원문 인용 범위 저장
- 추론과 직접 발언 구분
- JSON Schema에 맞게 출력

### 5.2 Planner

- 미확정 필드와 모순 확인
- 자동화 판단에 중요한 항목 우선
- 질문 유형과 목표만 결정

### 5.3 Interviewer

- 한 번에 질문 하나
- 쉬운 한국어
- 이미 답한 내용을 짧게 반영
- 답변 예시가 필요할 때만 제공

### 5.4 Synthesizer

- 업무 지도, 판단, 예외, 수치 요약
- 사실·추론·미확정 표시

### 5.5 Critic/Reviewer

- 누락·과도한 추론·모순·위험 확인
- 종료 전 독립적인 closure audit

하나의 프롬프트에 모든 역할을 넣지 않는다.

---

## 6. 신뢰도 계산 원칙

LLM의 자기 확신 점수를 그대로 사용하지 않는다.

예시 구성 요소:

- 직접 답변 존재: +0.20
- 구체적 수치·조건 포함: +0.10
- 최근 실제 사례에 등장: +0.15
- 별도 답변에서 반복 일치: +0.10
- 문서·로그 등 증거 일치: +0.20
- 사용자 명시 확인: +0.20
- 반대 증거 또는 모순: -0.30
- AI 추론만 존재: 최대 0.35로 제한

최종 값은 0~1로 제한한다. 중요 필드에는 신뢰도 외에 상태를 함께 사용한다.

---

## 7. 커버리지 평가

분리된 세 지표를 사용한다.

### 7.1 Epistemic Coverage

업무 사실을 얼마나 이해했는가?

- 목적, 경계, 단계, 입력·출력, 도구, 판단, 예외, 수치

### 7.2 Operational Readiness

프로그램을 설계할 만큼 실행 구조가 명확한가?

- 시작·종료, 데이터 필드, 권한, 시스템, 실패 처리, 테스트 기준

### 7.3 Deontic/Risk Clarity

누가 무엇을 결정·승인할 수 있고 무엇을 해서는 안 되는가?

- 책임, 권한, 민감정보, 법·정책, 사람 감독, non-goals

세 지표를 단일 평균으로 감추지 않는다.

---

## 8. 질문 목표 선택 의사코드

```python
def choose_next_target(model, user_state):
    candidates = unresolved_material_fields(model)
    candidates = remove_recently_asked_or_answered(candidates)
    candidates = remove_unanswerable_without_external_evidence(candidates)

    for item in candidates:
        item.priority = (
            item.materiality
            * item.uncertainty
            * item.answerability
            * item.expected_information_gain
            * item.novelty
            - item.user_burden
            - item.repetition_penalty
        )

    return max(candidates, key=lambda x: x.priority, default=None)
```

자료가 있어야만 답할 수 있는 질문은 반복해서 묻지 않고 `NEEDS_EVIDENCE` 목록으로 보낸다.

---

## 9. 데이터 무결성

- 원본 답변과 전사는 불변 이벤트로 저장
- 수정본은 새 버전으로 저장
- 모델 병합 전 JSON Schema 검증
- 엔터티 삭제는 소프트 삭제와 감사 기록
- 모든 모델 필드에 `source_refs` 허용
- 추천 생성 시 확정 스냅샷 ID 사용

---

## 10. 보안·프라이버시 가드레일

- 조직별 테넌트 분리
- 전송·저장 암호화
- 최소 권한
- 외부 모델 전송 전 불필요한 개인정보 마스킹
- 업로드 문서는 명령이 아니라 비신뢰 데이터로 처리
- 프롬프트 인젝션 패턴 탐지와 도구 실행 차단
- 모델 공급자 학습 사용·보존 옵션 확인
- 오디오 기본 자동 삭제
- 프로젝트 전체 내보내기·삭제
- AI 생성 분석임을 명시
- 고위험 자동화는 사람 검토로 라우팅

---

## 11. 장애·복구

- STT 실패: 재시도 또는 텍스트 입력 전환
- JSON 출력 실패: 제한된 자동 재생성 후 검토 큐
- 모순 과다: 사용자에게 비교 화면 제공
- 세션 중단: 마지막 확정 상태부터 재개
- 모델 공급자 장애: 공급자 추상화 계층으로 대체
- 삭제 요청: 비동기 삭제 상태와 완료 감사 이벤트

---

## 12. MVP에서 하지 않는 것

- 외부 시스템 로그인 및 실제 조작
- 직원 화면 상시 녹화
- 회사 전체 프로세스 자동 병합
- 고위험 결정을 자율 실행
- 전사 확인 없이 음성 내용을 업무 모델에 확정 반영
