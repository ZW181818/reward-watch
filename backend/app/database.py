from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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


def create_database_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    return create_engine(url, pool_pre_ping=True)


def initialize_database(database_url: str | None = None) -> Engine:
    engine = create_database_engine(database_url)
    Base.metadata.create_all(engine)
    return engine
