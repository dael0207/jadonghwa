# Shared Contracts

M0 keeps the canonical contract files at the repository root:

- `schemas/work-model-v1.schema.json`
- `schemas/interview-state-v1.schema.json`
- `schemas/opportunity-v1.schema.json`
- `question-bank-v1.json`
- `openapi-mvp.yaml`
- `examples/*`

The API contract loader reads these files directly so tests validate the same artifacts used by the product documentation.

