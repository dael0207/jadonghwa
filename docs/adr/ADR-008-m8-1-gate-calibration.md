# ADR-008: M8.1 Residual-Risk Gate Calibration

## Status

Accepted

## Context

The M4 score previously added every security constraint and every documented exception to risk. This made the product safety policy that forbids external execution count as workflow danger, and it penalized corroborated exception handling a second time. A normal Discovery Recovery therefore stopped at `ENABLE_FIRST` even after the user supplied complete evidence and confirmed playback.

## Decision

- Preserve safety policies in the Work Model, but classify `SAFETY_POLICY` separately from inherent workflow risk.
- Classify privacy, security, legal, financial, safety, and quality exposure as `INHERENT_RISK`.
- Treat a risk as controlled only when it has an explicit control, residual level at most 2, a `CORROBORATED` or `CONFIRMED` evidence state, and source references.
- Treat an exception as controlled only when condition, handling, corroborated evidence state, and source references are all present.
- Treat an authority boundary as confirmed only when the named human decision/approval boundary has a control, residual level, and corroborated source evidence.
- Use unresolved risk dimensions, unresolved exceptions, unresolved authority, open contradictions, and controlled residual levels to calculate `residual_risk` from 0 to 4.
- Keep the G1 thresholds unchanged: feasibility at least 70, evidence confidence at least 0.75, and residual risk at most 2.
- Require structured artifacts, clear systems, rules, controlled exceptions, confirmed authority, source references, no open contradiction, and no open material gap before `READY_FOR_DESIGN`.
- Add the structured `risk_profile` to Opportunity v1 so the UI and exported evidence explain safety policies, inherent/controlled/unresolved risks, controlled/unresolved exceptions, authority, contradictions, and residual risk.
- Keep M5 gating unchanged. `READY_FOR_DESIGN` creates `FULL_G1`; `ENABLE_FIRST` creates only `ENABLEMENT_PREP`; `DISCOVERY_NEEDED` and `BLOCKED` remain closed.

## Consequences

A corroborated Discovery Recovery can now proceed through `FULL_G1`, export-ready `FULL_G1_BLUEPRINT`, M7 blueprint completeness, and M8 export readiness. Missing controls, weak evidence, missing authority, and contradictions still prevent the full path. The implementation remains deterministic and does not add LLM, STT, credential collection, external execution, application code generation, or production deployment.
