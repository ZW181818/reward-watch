from __future__ import annotations

import json
import sys
from pathlib import Path
from time import monotonic


BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "data"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.storage import sync_case_snapshot  # noqa: E402


def _load(name: str):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def main() -> int:
    started_at = monotonic()
    sync_case_snapshot(
        cases=_load("cases.json"),
        source_cases=_load("source_cases.json"),
        update_status=_load("update_status.json"),
        quality_report=_load("data_quality_report.json"),
    )
    print(
        "Synchronized the validated case snapshot to DATABASE_URL in "
        f"{monotonic() - started_at:.3f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
