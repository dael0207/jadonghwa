# ADR-004: M4 Opportunity Scoring and Readiness Gate

## Status

Accepted

## Context

M3 produced a schema-valid opportunity draft, but it used fixed mock scores. M4 needs a deterministic scoring layer that reads Work Model evidence and tells whether an opportunity is ready for G1 design. It must not call an LLM, record audio, collect credentials, execute external systems, or generate the actual G1 package.

## Decision

M4 introduces an evidence-based deterministic opportunity analyzer. It reads the latest schema-valid Work Model and computes separate dimensions:

- value
- feasibility
- risk
- evidence_confidence
- oversight

The system does not compute one total score. It stores every analysis in `opportunity_drafts`, exposes version history, and provides a latest-vs-previous diff. Readiness is a separate API response that reports whether the latest opportunity is ready for G1 design, including blockers, missing evidence, required follow-ups, and a dimension score summary.

Audit events are recorded for analyze, validate, readiness, and diff operations.

## Consequences

- M4 is explainable and repeatable in tests.
- PostgreSQL and in-memory repositories expose the same opportunity methods.
- G1 generation remains blocked until a later milestone.
- The scoring thresholds are product assumptions and must be calibrated with pilot data.

## Non-Goals

- Real LLM scoring
- STT or voice recording
- External automation execution
- Credential collection
- Actual G1 design package generation
