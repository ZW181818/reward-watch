import json
import logging
from pathlib import Path

from .database import get_database_url
from .models import RewardCase
from .storage import load_database_cases


DATA_PATH = Path(__file__).resolve().parents[2] / "sample_cases.json"
REAL_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "cases.json"
logger = logging.getLogger(__name__)


def load_cases() -> list[RewardCase]:
    if get_database_url():
        try:
            database_cases = load_database_cases()
            if database_cases is not None:
                return database_cases
        except Exception:
            logger.exception("Database read failed; using the last valid JSON snapshot")

    data_path = REAL_DATA_PATH if REAL_DATA_PATH.exists() else DATA_PATH

    if not data_path.exists():
        return []

    raw_cases = json.loads(data_path.read_text(encoding="utf-8"))
    return [RewardCase.model_validate(item) for item in raw_cases]
