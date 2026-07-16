# ADR-007: M4/M5 Discovery Recovery Loop

## Status

Accepted

## Context

M4 can return `DISCOVERY_NEEDED` or `BLOCKED`, while M5 correctly rejects those gates. A finalized interview previously had no explicit path back to evidence collection, so the user could not act on the readiness result without weakening the general state machine.

## Decision

- Add deterministic guidance for eight evidence dimensions: systems/tools, input/output, rules, exceptions, authority, metrics, scope/non-goals, and source refs.
- Reuse `question-bank-v1.json` for follow-up questions.
- Add a recovery-only transition from `PLAYBACK_CONFIRMATION`, `OPPORTUNITY_ANALYSIS_READY`, or `FINALIZED` to `NEEDS_EVIDENCE`.
- Keep the normal `transition()` graph unchanged. Only `discovery/reopen` can invoke the recovery transition.
- Reject recovery from `CONSENT_REVOKED`, `DELETION_PENDING`, and `ABORTED`.
- Require evidence, `MODEL_BUILDING`, Work Model build, `PLAYBACK_CONFIRMATION`, and explicit user confirmation before reanalysis.
- Append a new opportunity on reanalysis and audit `DISCOVERY_REOPENED` and `DISCOVERY_REANALYZED`.
- Allow M5 package creation only for `READY_FOR_DESIGN` and `ENABLE_FIRST`.

No database migration is required. Existing interview status, immutable answer/turn events, append-only Work Model and opportunity records, and audit event metadata contain the complete recovery history for both in-memory and PostgreSQL repositories.

## Consequences

The M4 result is now actionable without bypassing playback or weakening consent. The recovery evidence parser is intentionally deterministic and only recognizes labelled evidence lines; it is not an LLM adaptive interview. M9/G2 may replace question selection and evidence interpretation behind the same API and repository boundaries.
