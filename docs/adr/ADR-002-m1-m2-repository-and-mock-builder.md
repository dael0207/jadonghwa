# ADR-002: M1/M2 Repository Boundary and Mock Work Model Builder

날짜: 2026-07-15

## 상태

Accepted

## 맥락

M1/M2는 M0의 동의, 질문, 답변, 상태 전이, 감사 로그 기준을 유지하면서 실제 DB 저장소로 갈 수 있는 경계와 사람이 클릭 가능한 웹 흐름을 제공해야 한다. 동시에 실제 LLM, STT, 음성 녹음, 외부 자동화 실행, G1 명세 생성은 아직 연결하지 않는다.

## 결정

- API는 `WorkDiscoveryRepository` 프로토콜을 통해 저장소 구현에 접근한다.
- `DATABASE_URL`이 없으면 `MemoryStore`를 사용한다.
- `DATABASE_URL`이 있으면 `PostgresRepository`를 사용한다.
- PostgreSQL 저장소는 `infra/db/migrations/001_m0_foundation.sql` 적용을 전제로 한다.
- 질문지는 인터뷰 생성 시 `question-bank-v1.json`의 초기 10문항을 seed/upsert한다.
- Work Model 생성은 `DeterministicWorkModelBuilder`가 수행한다.
- builder는 외부 LLM 호출 없이 답변 텍스트와 질문 metadata만 사용한다.
- 생성된 Work Model은 API에서 schema validation을 통과한 뒤 저장한다.
- build, playback confirm, playback reject는 모두 `audit_events`에 기록한다.

## 결과

M1/M2에서는 PostgreSQL 전환 경계와 deterministic playback 흐름을 검증할 수 있다. 생성된 Work Model은 실제 자동화 분석 결과가 아니라 다음 단계 LLM builder와 reasoning engine을 붙이기 전의 계약 검증용 초안이다.

## 비범위

- 실제 LLM/STT/음성 녹음 연결
- 외부 시스템 실행
- 실제 자격증명 수집
- 자동화 후보 분석
- G1 명세 생성
