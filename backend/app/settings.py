from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .database import AppSettingRow, get_database_url, initialize_database


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


def load_published_home_settings() -> HomeSettings:
    if not get_database_url():
        return DEFAULT_HOME_SETTINGS

    engine = initialize_database()
    try:
        with Session(engine) as session:
            row = session.get(AppSettingRow, "home.published")
            return HomeSettings.model_validate(row.value) if row else DEFAULT_HOME_SETTINGS
    except Exception:
        return DEFAULT_HOME_SETTINGS
    finally:
        engine.dispose()


@router.get("/home", response_model=HomeSettings)
def get_home_settings() -> HomeSettings:
    return load_published_home_settings()
