# ADR-001 — M0 Foundation Boundaries

## Status

Accepted for M0.

## Context

The product discovers and structures work before recommending automation. The M0 implementation must prove the trust boundary before adding LLM, STT, adaptive interview, automation reasoning, or blueprint generation.

## Decision

- M0 implements project creation, interview creation, consent, fixed text intake, immutable turn events, state transitions, and JSON Schema validation.
- M0 does not connect to external operating systems, SaaS accounts, RPA tools, or customer credentials.
- M0 does not run LLM extraction, STT, audio recording, automation analysis, or G1 blueprint generation.
- M0 stores answers as immutable events. Corrections create revisions rather than overwriting originals.
- M0 treats JSON Schema files, OpenAPI, examples, and the question bank as shared contracts.
- M0 exposes PostgreSQL migration DDL for the target persistence shape, while local smoke tests use the in-memory repository to verify API behavior.

## Consequences

- Later LLM/STT services must attach to the same consent, evidence, turn, and state-machine boundaries.
- Any future feature that wants to execute external work must require a new ADR and a higher milestone than M0.
- Tests must prove that consent gates and invalid state transitions fail closed.

