# ADR-009: M9 Implementation Package and CODEGEN_READY Gate

## Status

Accepted

## Context

M8.1 proves that a FULL_G1 blueprint is design-ready, but that result does not prove that an independent implementer can build the automation without inventing runtime, data, integration, error, approval, or test behavior. Packaging existing JSON and Markdown would preserve the ambiguity.

M9 must produce an implementation contract that can be checked without connecting credentials, executing external business systems, generating production application code, or deploying to production.

## Decision

- Keep `DESIGN_READY`, `IMPLEMENTATION_READY`, and `CODEGEN_READY` as separate gates.
- Reject CODEGEN_READY when a critical value contains an unresolved marker, a workflow reference is missing, the DAG is cyclic, or an open blocker remains.
- Store evidence files, confirmations, implementation requirements, and implementation packages append-only in both repository implementations.
- Accept only CSV, JSON, and XLSX evidence within bounded size limits. Reject unsafe filenames, archive paths, absolute paths, secret-like fields, and secret-like assignments.
- Require distinct confirmed input and expected-output files for NORMAL, ERROR, EXCEPTION, and APPROVAL_REQUIRED acceptance cases.
- Revalidate schemas, references, checksums, workflow connectivity, fixture coverage, and archive safety when a CODEGEN_READY ZIP is exported.
- Run artifact-only blind-build QA in a temporary directory. The reference implementation may read only the exported contracts and fixtures and must semantically match all four expected outputs.
- Record evidence upload/confirmation, requirements, package creation/validation/export, and readiness evaluation as audit events.

## Consequences

DESIGN_READY no longer implies that code generation is safe. A DRAFT ZIP remains available for resolving blockers, while the CODEGEN_READY ZIP is only available after the implementation contract and executable evidence are complete.

The ZIP is sufficient for a bounded reference implementation of the documented monthly-report workflow, but it is not production code and does not prove behavior against live vendor APIs, real credentials, production data volume, or production deployment controls.

`defusedxml` is added because XLSX files are ZIP containers containing untrusted XML. It prevents unsafe XML entity behavior while retaining a dependency-light parser.
