# Shared Contracts

M0~M8 keep the canonical contract files at the repository root:

- `schemas/work-model-v1.schema.json`
- `schemas/interview-state-v1.schema.json`
- `schemas/opportunity-v1.schema.json`
- `schemas/design-package-v1.schema.json`
- `schemas/blueprint-v1.schema.json`
- `schemas/evaluation-run-v1.schema.json`
- `schemas/release-readiness-v1.schema.json`
- `question-bank-v1.json`
- `openapi-mvp.yaml`
- `examples/*`

The API contract loader reads these files directly so tests validate the same artifacts used by the product documentation. Runtime output is wrapped by API response models, while `payload` fields remain the schema-validated contract objects.
