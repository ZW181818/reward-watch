from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parent / "update_cases.py"
SYNC_MINUTE = int(os.getenv("SYNC_MINUTE", "20"))


def next_run(now: datetime) -> datetime:
    candidate = now.replace(minute=SYNC_MINUTE, second=0, microsecond=0)
    return candidate if candidate > now else candidate + timedelta(hours=1)


def run_sync() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--strict"],
        check=False,
    )
    if completed.returncode:
        print(f"Hourly sync completed with status {completed.returncode}", flush=True)


def main() -> int:
    if os.getenv("SYNC_RUN_ON_STARTUP", "true").lower() in {"1", "true", "yes"}:
        run_sync()

    while True:
        now = datetime.now(UTC)
        scheduled = next_run(now)
        wait_seconds = max(1, (scheduled - now).total_seconds())
        print(f"Next official-data sync: {scheduled.isoformat()}", flush=True)
        time.sleep(wait_seconds)
        run_sync()


if __name__ == "__main__":
    raise SystemExit(main())
