from __future__ import annotations

import re

from work_discovery_api.contracts import default_contract_paths

REQUIRED_TABLES: frozenset[str] = frozenset(
    {
        "workspaces",
        "local_users",
        "projects",
        "interview_sessions",
        "consent_records",
        "turns",
        "questions",
        "answers",
        "work_models",
        "audit_events",
        "deletion_jobs",
    },
)


def main() -> None:
    migration = (
        default_contract_paths().root
        / "infra"
        / "db"
        / "migrations"
        / "001_m0_foundation.sql"
    )
    sql = migration.read_text(encoding="utf-8")
    created = frozenset(re.findall(r"CREATE TABLE IF NOT EXISTS ([a-z_]+)", sql))
    missing = REQUIRED_TABLES - created
    if missing:
        message = f"migration missing tables: {sorted(missing)}"
        raise RuntimeError(message)
    print("migration smoke OK")


if __name__ == "__main__":
    main()
