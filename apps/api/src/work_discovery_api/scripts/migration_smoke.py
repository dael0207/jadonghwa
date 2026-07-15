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
        "opportunity_drafts",
        "design_packages",
        "audit_events",
        "deletion_jobs",
    },
)


def main() -> None:
    migration_dir = default_contract_paths().root / "infra" / "db" / "migrations"
    sql = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(migration_dir.glob("*.sql"))
    )
    created = frozenset(re.findall(r"CREATE TABLE IF NOT EXISTS ([a-z_]+)", sql))
    missing = REQUIRED_TABLES - created
    if missing:
        message = f"migration missing tables: {sorted(missing)}"
        raise RuntimeError(message)
    print("migration smoke OK")


if __name__ == "__main__":
    main()
