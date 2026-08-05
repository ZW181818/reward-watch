from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
DATA_DIR = BACKEND_DIR / "data"
CASES_PATH = DATA_DIR / "cases.json"
STATUS_PATH = DATA_DIR / "update_status.json"
REPORT_PATH = DATA_DIR / "data_quality_report.json"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.case_quality import build_data_quality_report, validate_data_quality  # noqa: E402
from scripts.update_cases import write_json_atomic  # noqa: E402


def main() -> int:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    update_status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    validate_data_quality(cases)
    report = build_data_quality_report(
        cases,
        generated_at=str(update_status.get("updatedAt", "")),
        source_statuses=list(update_status.get("sources", [])),
    )
    write_json_atomic(REPORT_PATH, report)
    print(f"Wrote data quality report for {len(cases)} canonical cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
