from __future__ import annotations

import subprocess
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .admin_security import create_access_token, require_admin, verify_password
from .database import (
    AdminUserRow,
    AppSettingRow,
    AuditLogRow,
    CaseOverrideRow,
    CaseRow,
    SyncRunRow,
    initialize_database,
)
from .models import RewardCase, RewardCurrency
from .settings import DEFAULT_HOME_SETTINGS, HomeSettings


router = APIRouter(prefix="/admin", tags=["admin"])
SYNC_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "update_cases.py"
SYNC_LOCK = threading.Lock()


class LoginRequest(BaseModel):
    email: str
    password: str


class CaseUpdateRequest(BaseModel):
    title: str | None = None
    summary: str | None = None
    status: str | None = None
    reward: int | None = Field(default=None, ge=0)
    rewardCurrency: RewardCurrency | None = None
    imageUrl: str | None = None
    imageUrls: list[str] | None = None
    regions: list[str] | None = None
    warningMessage: str | None = None
    isVisible: bool | None = None
    reviewStatus: Literal["draft", "published"] | None = None
    note: str | None = None


EDITABLE_FIELDS = {
    "title",
    "summary",
    "status",
    "reward",
    "rewardCurrency",
    "imageUrl",
    "imageUrls",
    "regions",
    "warningMessage",
}


def _effective_payload(row: CaseRow, override: CaseOverrideRow | None) -> dict:
    payload = dict(row.payload)
    if override:
        payload.update(override.fields)
    return payload


def _audit(
    session: Session,
    *,
    admin_email: str,
    action: str,
    entity_id: str,
    before: dict | None,
    after: dict | None,
) -> None:
    session.add(
        AuditLogRow(
            admin_email=admin_email,
            action=action,
            entity_type="case",
            entity_id=entity_id,
            before_payload=before,
            after_payload=after,
        )
    )


@router.post("/auth/login")
def login(body: LoginRequest):
    engine = initialize_database()
    try:
        with Session(engine) as session:
            user = session.query(AdminUserRow).filter(
                func.lower(AdminUserRow.email) == body.email.strip().lower()
            ).one_or_none()
            if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Email or password is incorrect",
                )
            return {
                "accessToken": create_access_token(user),
                "expiresIn": 8 * 60 * 60,
                "admin": {"email": user.email, "role": user.role},
            }
    finally:
        engine.dispose()


@router.get("/dashboard")
def dashboard(admin_email: str = Depends(require_admin)):
    engine = initialize_database()
    try:
        with Session(engine) as session:
            latest = session.scalar(select(SyncRunRow).order_by(SyncRunRow.completed_at.desc()).limit(1))
            visible_count = session.scalar(select(func.count()).select_from(CaseRow)) or 0
            hidden_count = session.scalar(
                select(func.count()).select_from(CaseOverrideRow).where(CaseOverrideRow.is_visible.is_(False))
            ) or 0
            draft_count = session.scalar(
                select(func.count()).select_from(CaseOverrideRow).where(CaseOverrideRow.review_status == "draft")
            ) or 0
            return {
                "adminEmail": admin_email,
                "counts": {
                    "cases": visible_count,
                    "hidden": hidden_count,
                    "drafts": draft_count,
                },
                "sync": latest.status_payload if latest else None,
                "quality": latest.quality_payload if latest else None,
                "syncRunning": SYNC_LOCK.locked(),
            }
    finally:
        engine.dispose()


@router.get("/cases")
def list_admin_cases(
    q: Annotated[str | None, Query(min_length=1)] = None,
    visibility: Literal["all", "visible", "hidden"] = "all",
    review_status: Literal["all", "draft", "published"] = "all",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    _admin_email: str = Depends(require_admin),
):
    engine = initialize_database()
    try:
        with Session(engine) as session:
            statement = select(CaseRow, CaseOverrideRow).outerjoin(
                CaseOverrideRow, CaseOverrideRow.case_id == CaseRow.id
            )
            if q:
                needle = f"%{q.strip().casefold()}%"
                statement = statement.where(
                    or_(CaseRow.search_text.like(needle), func.lower(CaseRow.id).like(needle))
                )
            if visibility == "hidden":
                statement = statement.where(CaseOverrideRow.is_visible.is_(False))
            elif visibility == "visible":
                statement = statement.where(
                    or_(CaseOverrideRow.case_id.is_(None), CaseOverrideRow.is_visible.is_(True))
                )
            if review_status != "all":
                if review_status == "published":
                    statement = statement.where(
                        or_(CaseOverrideRow.case_id.is_(None), CaseOverrideRow.review_status == "published")
                    )
                else:
                    statement = statement.where(CaseOverrideRow.review_status == review_status)

            count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
            total = session.scalar(count_statement) or 0
            rows = session.execute(
                statement.order_by(CaseRow.published_date.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            items = []
            for row, override in rows:
                effective = _effective_payload(row, override)
                items.append(
                    {
                        "id": row.id,
                        "title": effective["title"],
                        "country": effective["country"],
                        "status": effective["status"],
                        "reward": effective.get("reward"),
                        "rewardCurrency": effective.get("rewardCurrency"),
                        "sourceName": effective.get("sourceAuthor") or effective.get("agency"),
                        "imageUrl": effective.get("imageUrl"),
                        "publishedDate": effective["publishedDate"],
                        "isVisible": override.is_visible if override else True,
                        "reviewStatus": override.review_status if override else "published",
                        "hasOverride": override is not None,
                    }
                )
            return {"items": items, "total": total, "page": page, "pageSize": page_size}
    finally:
        engine.dispose()


@router.get("/cases/{case_id}")
def get_admin_case(case_id: str, _admin_email: str = Depends(require_admin)):
    engine = initialize_database()
    try:
        with Session(engine) as session:
            row = session.get(CaseRow, case_id)
            if row is None:
                raise HTTPException(status_code=404, detail="Case not found")
            override = session.get(CaseOverrideRow, case_id)
            return {
                "raw": row.payload,
                "effective": _effective_payload(row, override),
                "override": {
                    "fields": override.fields,
                    "isVisible": override.is_visible,
                    "reviewStatus": override.review_status,
                    "note": override.note,
                    "updatedBy": override.updated_by,
                    "updatedAt": override.updated_at.isoformat(),
                } if override else None,
            }
    finally:
        engine.dispose()


@router.patch("/cases/{case_id}")
def update_admin_case(
    case_id: str,
    body: CaseUpdateRequest,
    admin_email: str = Depends(require_admin),
):
    engine = initialize_database()
    try:
        with Session(engine) as session, session.begin():
            row = session.get(CaseRow, case_id)
            if row is None:
                raise HTTPException(status_code=404, detail="Case not found")
            override = session.get(CaseOverrideRow, case_id)
            before = {
                "fields": dict(override.fields),
                "isVisible": override.is_visible,
                "reviewStatus": override.review_status,
                "note": override.note,
            } if override else None
            if override is None:
                override = CaseOverrideRow(case_id=case_id, fields={})
                session.add(override)

            supplied = body.model_fields_set
            next_fields = dict(override.fields)
            for field_name in EDITABLE_FIELDS & supplied:
                next_fields[field_name] = getattr(body, field_name)

            effective = dict(row.payload)
            effective.update(next_fields)
            RewardCase.model_validate(effective)

            override.fields = next_fields
            if "isVisible" in supplied:
                override.is_visible = bool(body.isVisible)
            if "reviewStatus" in supplied and body.reviewStatus:
                override.review_status = body.reviewStatus
            if "note" in supplied:
                override.note = body.note
            override.updated_by = admin_email
            override.updated_at = datetime.now(UTC)

            after = {
                "fields": next_fields,
                "isVisible": override.is_visible,
                "reviewStatus": override.review_status,
                "note": override.note,
            }
            _audit(
                session,
                admin_email=admin_email,
                action="case.override.updated",
                entity_id=case_id,
                before=before,
                after=after,
            )
            return {"case": effective, "override": after}
    finally:
        engine.dispose()


@router.delete("/cases/{case_id}/override")
def reset_admin_case(case_id: str, admin_email: str = Depends(require_admin)):
    engine = initialize_database()
    try:
        with Session(engine) as session, session.begin():
            override = session.get(CaseOverrideRow, case_id)
            if override is None:
                return {"reset": False}
            before = {
                "fields": override.fields,
                "isVisible": override.is_visible,
                "reviewStatus": override.review_status,
                "note": override.note,
            }
            session.delete(override)
            _audit(
                session,
                admin_email=admin_email,
                action="case.override.reset",
                entity_id=case_id,
                before=before,
                after=None,
            )
            return {"reset": True}
    finally:
        engine.dispose()


@router.get("/audit")
def audit_log(
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    _admin_email: str = Depends(require_admin),
):
    engine = initialize_database()
    try:
        with Session(engine) as session:
            rows = session.scalars(
                select(AuditLogRow).order_by(AuditLogRow.created_at.desc()).limit(limit)
            ).all()
            return [
                {
                    "id": row.id,
                    "adminEmail": row.admin_email,
                    "action": row.action,
                    "entityType": row.entity_type,
                    "entityId": row.entity_id,
                    "createdAt": row.created_at.isoformat(),
                }
                for row in rows
            ]
    finally:
        engine.dispose()


@router.get("/settings/home")
def get_admin_home_settings(_admin_email: str = Depends(require_admin)):
    engine = initialize_database()
    try:
        with Session(engine) as session:
            published = session.get(AppSettingRow, "home.published")
            draft = session.get(AppSettingRow, "home.draft")
            return {
                "published": HomeSettings.model_validate(published.value).model_dump()
                if published else DEFAULT_HOME_SETTINGS.model_dump(),
                "draft": HomeSettings.model_validate(draft.value).model_dump()
                if draft else None,
                "draftUpdatedAt": draft.updated_at.isoformat() if draft else None,
                "draftUpdatedBy": draft.updated_by if draft else None,
            }
    finally:
        engine.dispose()


@router.patch("/settings/home")
def save_admin_home_settings(
    body: HomeSettings,
    admin_email: str = Depends(require_admin),
):
    engine = initialize_database()
    try:
        with Session(engine) as session, session.begin():
            existing_ids = set(
                session.scalars(select(CaseRow.id).where(CaseRow.id.in_(body.featuredCaseIds)))
            ) if body.featuredCaseIds else set()
            missing_ids = set(body.featuredCaseIds) - existing_ids
            if missing_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown featured case IDs: {', '.join(sorted(missing_ids))}",
                )

            row = session.get(AppSettingRow, "home.draft")
            before = dict(row.value) if row else None
            if row is None:
                row = AppSettingRow(key="home.draft", value=body.model_dump(), is_published=False)
                session.add(row)
            else:
                row.value = body.model_dump()
            row.updated_by = admin_email
            row.updated_at = datetime.now(UTC)
            session.add(
                AuditLogRow(
                    admin_email=admin_email,
                    action="home.settings.draft.saved",
                    entity_type="setting",
                    entity_id="home",
                    before_payload=before,
                    after_payload=body.model_dump(),
                )
            )
            return {"saved": True, "draft": body.model_dump()}
    finally:
        engine.dispose()


@router.post("/settings/home/publish")
def publish_admin_home_settings(admin_email: str = Depends(require_admin)):
    engine = initialize_database()
    try:
        with Session(engine) as session, session.begin():
            draft = session.get(AppSettingRow, "home.draft")
            if draft is None:
                raise HTTPException(status_code=409, detail="Save a home settings draft before publishing")
            settings_payload = dict(draft.value)
            published = session.get(AppSettingRow, "home.published")
            before = dict(published.value) if published else DEFAULT_HOME_SETTINGS.model_dump()
            if published is None:
                published = AppSettingRow(
                    key="home.published",
                    value=settings_payload,
                    is_published=True,
                )
                session.add(published)
            else:
                published.value = settings_payload
            published.updated_by = admin_email
            published.updated_at = datetime.now(UTC)
            session.add(
                AuditLogRow(
                    admin_email=admin_email,
                    action="home.settings.published",
                    entity_type="setting",
                    entity_id="home",
                    before_payload=before,
                    after_payload=settings_payload,
                )
            )
            session.delete(draft)
            return {"published": True, "settings": settings_payload}
    finally:
        engine.dispose()


def _run_manual_sync() -> None:
    if not SYNC_LOCK.acquire(blocking=False):
        return
    try:
        subprocess.run([sys.executable, str(SYNC_SCRIPT), "--strict"], check=False)
    finally:
        SYNC_LOCK.release()


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
def trigger_sync(
    background_tasks: BackgroundTasks,
    _admin_email: str = Depends(require_admin),
):
    if SYNC_LOCK.locked():
        raise HTTPException(status_code=409, detail="A data sync is already running")
    background_tasks.add_task(_run_manual_sync)
    return {"accepted": True}
