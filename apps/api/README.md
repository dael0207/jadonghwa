# Work Discovery API

M0 Foundation API for local development.

## Run

```bash
cd apps/api
python -m pip install -e .
python -m uvicorn work_discovery_api.main:app --reload --port 8000
```

## Test

```bash
cd apps/api
python -m pytest
python -m work_discovery_api.scripts.schema_smoke
python -m work_discovery_api.scripts.migration_smoke
python -m work_discovery_api.scripts.api_smoke
python -m work_discovery_api.scripts.server_smoke
```

PostgreSQL DDL 실행 스모크는 루트 기준 `infra/db`에서 실행한다.

```bash
cd infra/db
npm install
npm run migration:smoke
```
