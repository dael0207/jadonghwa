# Work Discovery AI Blueprint

이 저장소는 사용자가 자신의 업무를 텍스트 또는 음성으로 설명하면, AI가 반복 질문을 통해 업무 흐름·판단·예외·도구·데이터를 구조화하고 자동화 또는 업무 지원 프로그램의 설계 명세까지 생성하는 프로젝트의 연구·MVP 설계를 담고 있습니다.

## 핵심 흐름

```text
사용자의 업무 설명
→ 텍스트·음성 입력 및 전사 확인
→ 적응형 딥인터뷰
→ 근거가 연결된 업무 모델
→ 제거·단순화·표준화·자동화 후보 분석
→ 사람과 AI의 역할 분배
→ PRD·화면·데이터·API·테스트 명세
```

## 문서

- `R003-automation-discovery-framework.md`: 자동화 발견·판단 프레임워크
- `R004-work-ontology.md`: 업무 온톨로지 및 사실 상태 모델
- `R005-interview-methodology.md`: 초기 질문지와 딥인터뷰 방법론
- `R006-interview-engine.md`: 인터뷰 상태 머신과 AI 역할 분리
- `R007-automation-reasoning-engine.md`: 자동화 후보 추론 엔진
- `R008-program-generation.md`: 프로그램 설계 산출물 생성 규격
- `R009-evaluation-framework.md`: 평가 지표와 파일럿 계획
- `R010-mvp-spec.md`: MVP 범위와 기술 구조
- `DECISIONS-AND-NEXT.md`: 확정 사항, 남은 결정, M0 작업 목록

## 구조화 자산

- `question-bank-v1.json`: 한국어 인터뷰 질문 뱅크
- `schemas/`: Work Model, Interview State, Automation Opportunity JSON Schema
- `examples/`: 월간 보고서 업무 기반 검증 예시
- `openapi-mvp.yaml`: MVP API 초안

## 현재 범위

첫 MVP는 한국어 지식노동자의 반복적인 디지털 업무 하나를 분석해 1~3개의 개선·자동화 후보와 개발 가능한 G1 수준 솔루션 명세를 생성하는 데 집중합니다. 실제 외부 시스템 로그인, 자동 실행, 운영 코드 배포는 후속 단계입니다.
