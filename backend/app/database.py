from __future__ import annotations

from datetime import UTC, datetime
import os
from threading import RLock
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, JSON, String, Text, text
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import NullPool


class Base(DeclarativeBase):
    pass


class CaseRow(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(180), primary_key=True)
    country: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(80), index=True)
    reward: Mapped[int | None] = mapped_column(BigInteger, index=True)
    published_date: Mapped[str] = mapped_column(String(32), index=True)
    source_name: Mapped[str] = mapped_column(String(300), index=True)
    search_text: Mapped[str] = mapped_column(Text)
    regions_text: Mapped[str] = mapped_column(Text)
    sources_text: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class SourceCaseRow(Base):
    __tablename__ = "source_cases"

    id: Mapped[str] = mapped_column(String(180), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(80), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class CaseOverrideRow(Base):
    __tablename__ = "case_overrides"

    case_id: Mapped[str] = mapped_column(String(180), primary_key=True)
    fields: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    review_status: Mapped[str] = mapped_column(String(32), default="published", index=True)
    note: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[str | None] = mapped_column(String(180))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class CaseMapLocationOverrideRow(Base):
    """Durable administrator-reviewed map locations for one case."""

    __tablename__ = "case_map_location_overrides"

    case_id: Mapped[str] = mapped_column(String(180), primary_key=True)
    locations: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    note: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[str | None] = mapped_column(String(180))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class PublicCaseRow(Base):
    """Materialized, reviewed case data used by every public read."""

    __tablename__ = "public_cases"

    id: Mapped[str] = mapped_column(String(180), primary_key=True)
    country: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(80), index=True)
    reward: Mapped[int | None] = mapped_column(BigInteger, index=True)
    published_date: Mapped[str] = mapped_column(String(32), index=True)
    title_sort: Mapped[str] = mapped_column(String(500), index=True)
    search_text: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PublicCaseRegionRow(Base):
    __tablename__ = "public_case_regions"

    case_id: Mapped[str] = mapped_column(String(180), primary_key=True)
    value_folded: Mapped[str] = mapped_column(String(300), primary_key=True, index=True)
    value: Mapped[str] = mapped_column(String(300))


class PublicCaseSourceRow(Base):
    __tablename__ = "public_case_sources"

    case_id: Mapped[str] = mapped_column(String(180), primary_key=True)
    value_folded: Mapped[str] = mapped_column(String(500), primary_key=True, index=True)
    value: Mapped[str] = mapped_column(String(500))


class PublicCaseAliasRow(Base):
    __tablename__ = "public_case_aliases"

    alias_id: Mapped[str] = mapped_column(String(180), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(180), index=True)


class PublicCaseMapRow(Base):
    """Compact public map item, separate from the full case payload."""

    __tablename__ = "public_case_map"

    case_id: Mapped[str] = mapped_column(String(180), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PublicCatalogStateRow(Base):
    __tablename__ = "public_catalog_state"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    projection_version: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    ready: Mapped[bool] = mapped_column(Boolean, default=False)
    case_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SnapshotFingerprintRow(Base):
    __tablename__ = "snapshot_fingerprints"

    collection: Mapped[str] = mapped_column(String(40), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(180), primary_key=True)
    payload_hash: Mapped[str] = mapped_column(String(64))


class SyncRunRow(Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    all_sources_fresh: Mapped[bool] = mapped_column(Boolean, index=True)
    total_count: Mapped[int] = mapped_column(Integer)
    status_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    quality_payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class AdminUserRow(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(32), default="admin")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class AuditLogRow(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_email: Mapped[str] = mapped_column(String(320), index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str] = mapped_column(String(180), index=True)
    before_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )


class AppSettingRow(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    updated_by: Mapped[str | None] = mapped_column(String(320))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


def get_database_url() -> str | None:
    return os.getenv("DATABASE_URL") or None


_ENGINE_LOCK = RLock()
_POSTGRES_ENGINES: dict[str, Engine] = {}
_INITIALIZED_SCHEMAS: set[str] = set()
_SCHEMA_SENTINEL_TABLE = "case_map_location_overrides"


def _normalized_database_url(database_url: str | None = None) -> str:
    url = database_url or get_database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    return url


def create_database_engine(database_url: str | None = None) -> Engine:
    url = _normalized_database_url(database_url)

    # Tests and local tools need isolated SQLite handles that can be disposed
    # before their temporary directory is removed. The deployed PostgreSQL app
    # reuses one deliberately small pool instead of reconnecting on every API call.
    if url.startswith("sqlite"):
        return create_engine(url, pool_pre_ping=True, poolclass=NullPool)

    with _ENGINE_LOCK:
        engine = _POSTGRES_ENGINES.get(url)
        if engine is None:
            engine = create_engine(
                url,
                pool_pre_ping=True,
                pool_size=1,
                max_overflow=2,
                pool_timeout=15,
                pool_recycle=300,
            )
            _POSTGRES_ENGINES[url] = engine
        return engine



def initialize_database(database_url: str | None = None) -> Engine:
    url = _normalized_database_url(database_url)
    engine = create_database_engine(database_url)
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(engine)
        return engine

    with _ENGINE_LOCK:
        if url not in _INITIALIZED_SCHEMAS:
            # GitHub Actions starts a new process for every scheduled sync. A
            # single PostgreSQL catalog lookup is enough after the migration,
            # instead of asking PostgreSQL to check every table on every run.
            # Point the sentinel at the newest required table when a future
            # schema migration adds another model.
            with engine.connect() as connection:
                schema_is_current = connection.scalar(
                    text("SELECT to_regclass(:table_name)"),
                    {"table_name": _SCHEMA_SENTINEL_TABLE},
                ) is not None
            if not schema_is_current:
                Base.metadata.create_all(engine)
            _INITIALIZED_SCHEMAS.add(url)
    return engine


def release_database_engine(engine: Engine) -> None:
    """Release disposable local engines while retaining the production pool."""

    if engine.dialect.name == "sqlite":
        engine.dispose()
