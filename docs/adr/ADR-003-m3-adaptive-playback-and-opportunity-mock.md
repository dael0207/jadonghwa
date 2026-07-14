# ADR-003: M3 Adaptive Playback Loop and Opportunity Mock

날짜: 2026-07-15

## 상태

Accepted

## 맥락

M3는 M1/M2의 저장소 경계와 deterministic Work Model builder를 유지하면서 playback 거절 후 추가 증거를 수집하고 모델을 다시 만들 수 있어야 한다. 또한 Deep Interview로 확장하기 전에 질문 뱅크를 고정 질문지가 아니라 coverage rubric과 후보 pool로도 사용할 수 있어야 한다.

## 결정

- 고정 10문항 intake는 M0-M2 기준선으로 유지한다.
- `PLAYBACK_CONFIRMATION`에서 reject하면 `NEEDS_EVIDENCE`로 전이한다.
- `NEEDS_EVIDENCE`에서만 추가 evidence와 answer revision을 허용한다.
- evidence와 revision은 기존 답변을 덮어쓰지 않고 새 turn/answer 이벤트로 저장한다.
- `resume-model-building`은 `NEEDS_EVIDENCE`에서만 `MODEL_BUILDING`으로 전이한다.
- 재빌드된 Work Model은 새 버전으로 누적 저장한다.
- deterministic adaptive selector는 coverage 항목과 다음 후보 질문을 계산하지만 LLM follow-up을 생성하지 않는다.
- deterministic opportunity analyzer는 schema-valid draft를 만들지만 실제 자동화 후보 분석으로 간주하지 않는다.
- LLM, STT, 음성 녹음, 외부 자동화 실행, 실제 G1 명세 생성은 계속 비범위다.

## 결과

사용자는 로컬 UI에서 reject, evidence, revision, rebuild, opportunity draft까지 한 사이클을 클릭으로 확인할 수 있다. 모든 build/reject/evidence/revision/rebuild/opportunity 이벤트는 audit log에 남으며, 나중에 LLM/STT/실제 analyzer를 붙일 수 있도록 provider protocol 경계를 둔다.
