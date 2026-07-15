# ADR-005: M5 G1 Design Package Draft

## Status

Accepted

## Context

M4 can score opportunities and produce readiness results, but it still stops before any G1 design artifact. M5 needs a deterministic draft package that can be previewed, validated, exported as JSON, and traced back to the source Work Model, opportunity, readiness result, and evidence refs.

M5 must not call an LLM, record audio, collect credentials, execute external systems, or generate real application code.

## Decision

M5 introduces `schemas/design-package-v1.schema.json`, a deterministic design package builder, repository methods, PostgreSQL migration, API routes, and a web workbench panel.

Readiness gates are enforced:

- `READY_FOR_DESIGN` creates a `FULL_G1` package.
- `ENABLE_FIRST` creates an `ENABLEMENT_PREP` package.
- `BLOCKED` and `DISCOVERY_NEEDED` are rejected.

Design packages are append-only records. Creating a new package never overwrites a previous one. Create and validate operations emit audit events.

## Consequences

- G1 handoff shape is testable before real LLM generation.
- ENABLE_FIRST work can still produce a limited pre-design package without pretending it is ready for full implementation design.
- PostgreSQL and in-memory repositories keep the same contract.
- M6 can focus on export, review, and richer G1 package quality gates.

## Non-Goals

- Real LLM calls
- STT or voice recording
- External automation execution
- Credential collection
- Actual application code generation
- Real G1 implementation package generation
