from __future__ import annotations

from threading import RLock
from time import monotonic

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import event
from sqlalchemy.orm import Session

from .database import (
    AppSettingRow,
    create_database_engine,
    get_database_url,
    release_database_engine,
)


router = APIRouter(prefix="/settings", tags=["settings"])


class HomeSettings(BaseModel):
    brandSubtitle: str = Field(
        default="Official and reviewed public reward notices from supported jurisdictions",
        min_length=10,
        max_length=120,
    )
    safetyMessage: str = Field(
        default="Do not approach or attempt to detain any person. Submit information through the listed publisher's source page.",
        min_length=20,
        max_length=240,
    )
    featuredCaseIds: list[str] = Field(default_factory=list, max_length=6)
    recentCaseLimit: int = Field(default=4, ge=4, le=6)


DEFAULT_HOME_SETTINGS = HomeSettings()
HOME_SETTINGS_CACHE_TTL_SECONDS = 300.0
_HOME_SETTINGS_CACHE_LOCK = RLock()
_HOME_SETTINGS_CACHE: tuple[str, float, HomeSettings] | None = None


def clear_home_settings_cache() -> None:
    global _HOME_SETTINGS_CACHE
    with _HOME_SETTINGS_CACHE_LOCK:
        _HOME_SETTINGS_CACHE = None


def clear_home_settings_cache_after_commit(session: Session) -> None:
    event.listen(session, "after_commit", lambda _session: clear_home_settings_cache(), once=True)


def load_published_home_settings() -> HomeSettings:
    global _HOME_SETTINGS_CACHE
    database_url = get_database_url()
    if not database_url:
        return DEFAULT_HOME_SETTINGS

    with _HOME_SETTINGS_CACHE_LOCK:
        if (
            _HOME_SETTINGS_CACHE
            and _HOME_SETTINGS_CACHE[0] == database_url
            and _HOME_SETTINGS_CACHE[1] > monotonic()
        ):
            return _HOME_SETTINGS_CACHE[2].model_copy(deep=True)

    # Public reads should not run schema introspection after every Render cold
    # start. Schema creation belongs to the sync/admin paths.
    engine = create_database_engine()
    try:
        with Session(engine) as session:
            row = session.get(AppSettingRow, "home.published")
            settings = HomeSettings.model_validate(row.value) if row else DEFAULT_HOME_SETTINGS
            with _HOME_SETTINGS_CACHE_LOCK:
                _HOME_SETTINGS_CACHE = (
                    database_url,
                    monotonic() + HOME_SETTINGS_CACHE_TTL_SECONDS,
                    settings.model_copy(deep=True),
                )
            return settings
    except Exception:
        return DEFAULT_HOME_SETTINGS
    finally:
        release_database_engine(engine)


@router.get("/home", response_model=HomeSettings)
def get_home_settings() -> HomeSettings:
    return load_published_home_settings()
