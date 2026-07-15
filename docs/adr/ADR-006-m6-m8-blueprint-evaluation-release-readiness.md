# ADR-006: M6~M8 Blueprint, Evaluation, Release Readiness Boundary

## Status

Accepted

## Context

M5 creates a readiness-gated G1 design package draft. M6~M8 must make the remaining G1 MVP path testable without crossing into real automation execution, generated app code, live credentials, LLM/STT calls, or production deployment.

## Decision

- M6 creates an append-only G1 Solution Blueprint preview from a schema-valid design package.
- `READY_FOR_DESIGN` + `FULL_G1` can produce an export-ready full blueprint.
- `ENABLE_FIRST` + `ENABLEMENT_PREP` can produce only a limited follow-up blueprint and must remain non-export-ready for full G1.
- M7 creates deterministic evaluation runs from repository artifacts and a versioned fixture corpus.
- M8 creates deterministic limited release readiness reports from blueprint, evaluation, audit, consent, deletion, and schema evidence.
- Blueprints, evaluation runs, and release readiness reports are stored append-only in both in-memory and PostgreSQL repository implementations.
- All create, validate, and export operations emit audit events.

## Non-Goals

- No real LLM calls.
- No STT or voice recording.
- No external business system execution.
- No real credential collection.
- No generated application code.
- No production release or deployment.

## Consequences

- G1 output is reviewable design and QA evidence, not runnable software.
- Schema validation remains the boundary between deterministic builders and API responses.
- G2 can add controlled scaffold templates or revision loops later without weakening M0~M8 traceability.
