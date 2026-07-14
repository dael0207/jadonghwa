from __future__ import annotations

from work_discovery_api.config import load_settings
from work_discovery_api.postgres_repository import PostgresRepository
from work_discovery_api.repository import WorkDiscoveryRepository
from work_discovery_api.store import MemoryStore


def create_repository() -> WorkDiscoveryRepository:
    settings = load_settings()
    if settings.database_url is not None and settings.database_url.strip():
        return PostgresRepository(database_url=settings.database_url)
    return MemoryStore()
