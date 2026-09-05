from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any, Callable


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
DATA_DIR = BACKEND_DIR / "data"
OUTPUT_PATH = DATA_DIR / "cases.json"
SOURCE_CASES_PATH = DATA_DIR / "source_cases.json"
EXCLUSIONS_PATH = DATA_DIR / "source_exclusions.json"
STATUS_PATH = DATA_DIR / "update_status.json"
QUALITY_REPORT_PATH = DATA_DIR / "data_quality_report.json"

SOURCE_IDS = (
    "fbi",
    "opp",
    "rcmp-sk",
    "fq",
    "eps",
    "rcmp-bc",
    "vpd",
    "cfseu-bc",
    "rfj",
    "usms",
    "ns-reward",
    "uspis",
    "txdps",
    "cn-police",
)
SOURCE_BATCHES = {
    "us-core": ("fbi", "rfj"),
    "us-postal": ("uspis",),
    "us-justice": ("txdps", "usms"),
    "canada-east": ("opp", "fq", "eps", "ns-reward"),
    "canada-west": ("rcmp-sk", "rcmp-bc", "vpd", "cfseu-bc"),
    "china": ("cn-police",),
}
CATCH_UP_REDUNDANCY = ("rfj", "cfseu-bc")

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.case_quality import (  # noqa: E402
    build_data_quality_report,
    merge_cross_source_cases,
    normalize_reward_metadata,
    validate_data_quality,
)
from app.ingestion.fbi import fetch_fbi_cases  # noqa: E402
from app.ingestion.bc_rcmp import fetch_bc_rcmp_wanted_cases  # noqa: E402
from app.ingestion.cfseu import fetch_cfseu_bc_wanted_cases  # noqa: E402
from app.ingestion.china_police import fetch_china_police_reward_cases  # noqa: E402
from app.ingestion.edmonton import fetch_edmonton_most_wanted_cases  # noqa: E402
from app.ingestion.opp import fetch_opp_cases  # noqa: E402
from app.ingestion.quebec import fetch_quebec_fugitive_cases  # noqa: E402
from app.ingestion.rcmp import fetch_rcmp_saskatchewan_cases  # noqa: E402
from app.ingestion.rewards_for_justice import (  # noqa: E402
    fetch_rewards_for_justice_cases,
)
from app.ingestion.nova_scotia import fetch_nova_scotia_reward_cases  # noqa: E402
from app.ingestion.us_marshals import fetch_us_marshals_cases  # noqa: E402
from app.ingestion.uspis import fetch_uspis_cases  # noqa: E402
from app.ingestion.texas_dps import fetch_texas_dps_cases  # noqa: E402
from app.ingestion.vancouver import fetch_vancouver_wanted_cases  # noqa: E402
from app.database import get_database_url  # noqa: E402
from app.storage import sync_case_snapshot  # noqa: E402


def load_excluded_source_urls() -> set[str]:
    if not EXCLUSIONS_PATH.exists():
        return set()

    payload = json.loads(EXCLUSIONS_PATH.read_text(encoding="utf-8"))
    sources = payload.get("sources", []) if isinstance(payload, dict) else []
    return {
        source["url"]
        for source in sources
        if isinstance(source, dict) and isinstance(source.get("url"), str)
    }


def load_existing_cases(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    payload = json.loads(path.read_text(encoding="utf-8"))
    return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []


def load_existing_status(path: Path = STATUS_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}

    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def refresh_source(
    *,
    country: str,
    existing_cases: list[dict[str, Any]],
    fetcher: Callable[[], list[dict[str, Any]]],
    id_prefix: str,
    name: str,
    allow_empty: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started_at = monotonic()
    previous = [
        item
        for item in existing_cases
        if str(item.get("id", "")).startswith(id_prefix)
    ]

    try:
        cases = fetcher()
        if not cases and not allow_empty:
            raise ValueError("source returned no publishable records")
    except Exception as error:  # Network and upstream format failures share stale fallback handling.
        return previous, {
            "id": id_prefix.rstrip("-"),
            "name": name,
            "country": country,
            "success": False,
            "usedStaleData": bool(previous),
            "count": len(previous),
            "error": f"{type(error).__name__}: {error}",
            "durationSeconds": round(monotonic() - started_at, 3),
        }

    return cases, {
        "id": id_prefix.rstrip("-"),
        "name": name,
        "country": country,
        "success": True,
        "usedStaleData": False,
        "count": len(cases),
        "error": None,
        "durationSeconds": round(monotonic() - started_at, 3),
    }


def refresh_or_retain_source(
    *,
    country: str,
    existing_cases: list[dict[str, Any]],
    fetcher: Callable[[], list[dict[str, Any]]],
    id_prefix: str,
    name: str,
    selected_source_ids: set[str],
    previous_status: dict[str, Any] | None,
    allow_empty: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_id = id_prefix.rstrip("-")
    if source_id in selected_source_ids:
        return refresh_source(
            country=country,
            existing_cases=existing_cases,
            fetcher=fetcher,
            id_prefix=id_prefix,
            name=name,
            allow_empty=allow_empty,
        )

    previous = [
        item
        for item in existing_cases
        if str(item.get("id", "")).startswith(id_prefix)
    ]
    prior = previous_status or {}
    return previous, {
        "id": source_id,
        "name": name,
        "country": country,
        "success": bool(prior.get("success", False)),
        "usedStaleData": bool(prior.get("usedStaleData", not prior)),
        "count": len(previous),
        "error": prior.get("error"),
        "durationSeconds": None,
    }


def source_ids_for_batch(
    batch: str | None,
    previous_status: dict[str, Any],
    *,
    now: datetime,
) -> set[str]:
    if batch is None:
        return set(SOURCE_IDS)
    if batch != "catch-up":
        return set(SOURCE_BATCHES[batch])

    previous_updated_at = previous_status.get("updatedAt")
    previous_by_id = {
        str(status.get("id")): status
        for status in previous_status.get("sources", [])
        if isinstance(status, dict) and status.get("id")
    }
    selected = set(CATCH_UP_REDUNDANCY)
    for source_id in SOURCE_IDS:
        prior = previous_by_id.get(source_id, {})
        last_success_at = prior.get("lastSuccessAt")
        if not last_success_at and prior.get("success"):
            last_success_at = previous_updated_at
        if not _is_same_utc_date(last_success_at, now):
            selected.add(source_id)
    return selected


def attach_source_refresh_history(
    statuses: list[dict[str, Any]],
    previous_status: dict[str, Any],
    *,
    selected_source_ids: set[str],
    updated_at: str,
) -> None:
    previous_updated_at = previous_status.get("updatedAt")
    previous_by_id = {
        str(status.get("id")): status
        for status in previous_status.get("sources", [])
        if isinstance(status, dict) and status.get("id")
    }
    for status in statuses:
        source_id = str(status["id"])
        prior = previous_by_id.get(source_id, {})
        attempted = source_id in selected_source_ids
        prior_last_attempt = prior.get("lastAttemptAt") or previous_updated_at
        prior_last_success = prior.get("lastSuccessAt")
        if not prior_last_success and prior.get("success"):
            prior_last_success = previous_updated_at

        status["attemptedThisRun"] = attempted
        status["lastAttemptAt"] = updated_at if attempted else prior_last_attempt
        status["lastSuccessAt"] = (
            updated_at if attempted and status["success"] else prior_last_success
        )


def _is_same_utc_date(value: Any, now: datetime) -> bool:
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).date() == now.astimezone(UTC).date()


def main() -> int:
    parser = argparse.ArgumentParser(description="Update Reward Watch local case data.")
    parser.add_argument(
        "--fbi-limit",
        "--limit",
        dest="fbi_limit",
        type=int,
        default=0,
        help="Maximum FBI records to import, or 0 for every publishable record.",
    )
    parser.add_argument(
        "--opp-limit",
        type=int,
        default=0,
        help="Maximum Ontario Provincial Police records to import, or 0 for all.",
    )
    parser.add_argument(
        "--canada-limit",
        type=int,
        default=0,
        help="Maximum Saskatchewan RCMP records to import, or 0 for all.",
    )
    parser.add_argument(
        "--quebec-limit",
        type=int,
        default=0,
        help="Maximum Fugitifs Quebec records to import, or 0 for all.",
    )
    parser.add_argument(
        "--edmonton-limit",
        type=int,
        default=0,
        help="Maximum Edmonton Police records to import, or 0 for all.",
    )
    parser.add_argument(
        "--bc-rcmp-limit",
        type=int,
        default=0,
        help="Maximum British Columbia RCMP wanted records to import, or 0 for all.",
    )
    parser.add_argument(
        "--vancouver-limit",
        type=int,
        default=0,
        help="Maximum Vancouver Police wanted records to import, or 0 for all.",
    )
    parser.add_argument(
        "--cfseu-bc-limit",
        type=int,
        default=0,
        help="Maximum CFSEU-BC wanted records to import, or 0 for all.",
    )
    parser.add_argument(
        "--rewards-for-justice-limit",
        type=int,
        default=0,
        help="Maximum U.S. Rewards for Justice records to import, or 0 for all.",
    )
    parser.add_argument(
        "--us-marshals-limit",
        type=int,
        default=0,
        help="Maximum U.S. Marshals reward profiles to import, or 0 for all.",
    )
    parser.add_argument(
        "--nova-scotia-limit",
        type=int,
        default=0,
        help="Maximum Nova Scotia official reward records to import, or 0 for all.",
    )
    parser.add_argument(
        "--uspis-limit",
        type=int,
        default=0,
        help="Maximum U.S. Postal Inspection Service reward records to import, or 0 for all.",
    )
    parser.add_argument(
        "--texas-dps-limit",
        type=int,
        default=0,
        help="Maximum Texas DPS active reward records to import, or 0 for all.",
    )
    parser.add_argument(
        "--china-police-limit",
        type=int,
        default=0,
        help="Maximum mainland China public-security criminal reward records to import, or 0 for all.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return a failure code when any source uses stale fallback data.",
    )
    parser.add_argument(
        "--batch",
        choices=(*SOURCE_BATCHES, "catch-up"),
        help=(
            "Refresh one scheduled source batch. Omit this option for a manual "
            "full refresh; catch-up retries sources not yet refreshed successfully today."
        ),
    )
    parser.add_argument(
        "--skip-database",
        action="store_true",
        help="Write validated JSON snapshots without updating DATABASE_URL.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help="Output JSON path. Defaults to backend/data/cases.json.",
    )
    args = parser.parse_args()

    source_snapshot_path = (
        SOURCE_CASES_PATH
        if args.output.resolve() == OUTPUT_PATH.resolve() and SOURCE_CASES_PATH.exists()
        else args.output
    )
    existing_cases = load_existing_cases(source_snapshot_path)
    previous_update_status = load_existing_status()
    run_started_at = datetime.now(UTC)
    selected_source_ids = source_ids_for_batch(
        args.batch,
        previous_update_status,
        now=run_started_at,
    )
    previous_status_by_id = {
        str(status.get("id")): status
        for status in previous_update_status.get("sources", [])
        if isinstance(status, dict) and status.get("id")
    }
    excluded_source_urls = load_excluded_source_urls()
    fbi_cases, fbi_status = refresh_or_retain_source(
        country="US",
        existing_cases=existing_cases,
        fetcher=lambda: fetch_fbi_cases(
            limit=_optional_limit(args.fbi_limit),
            excluded_source_urls=excluded_source_urls,
        ),
        id_prefix="fbi-",
        name="FBI Wanted API",
        selected_source_ids=selected_source_ids,
        previous_status=previous_status_by_id.get("fbi"),
    )
    opp_cases, opp_status = refresh_or_retain_source(
        country="Canada",
        existing_cases=existing_cases,
        fetcher=lambda: fetch_opp_cases(limit=_optional_limit(args.opp_limit)),
        id_prefix="opp-",
        name="Ontario Provincial Police public investigations",
        selected_source_ids=selected_source_ids,
        previous_status=previous_status_by_id.get("opp"),
    )
    rcmp_cases, rcmp_status = refresh_or_retain_source(
        country="Canada",
        existing_cases=existing_cases,
        fetcher=lambda: fetch_rcmp_saskatchewan_cases(
            limit=_optional_limit(args.canada_limit)
        ),
        id_prefix="rcmp-sk-",
        name="Saskatchewan RCMP monthly wanted persons",
        selected_source_ids=selected_source_ids,
        previous_status=previous_status_by_id.get("rcmp-sk"),
    )
    quebec_cases, quebec_status = refresh_or_retain_source(
        country="Canada",
        existing_cases=existing_cases,
        fetcher=lambda: fetch_quebec_fugitive_cases(
            limit=_optional_limit(args.quebec_limit)
        ),
        id_prefix="fq-",
        name="Fugitifs Quebec provincial wanted list",
        selected_source_ids=selected_source_ids,
        previous_status=previous_status_by_id.get("fq"),
    )
    edmonton_cases, edmonton_status = refresh_or_retain_source(
        country="Canada",
        existing_cases=existing_cases,
        fetcher=lambda: fetch_edmonton_most_wanted_cases(
            limit=_optional_limit(args.edmonton_limit)
        ),
        id_prefix="eps-",
        name="Edmonton Police Service most wanted list",
        selected_source_ids=selected_source_ids,
        previous_status=previous_status_by_id.get("eps"),
    )
    bc_rcmp_cases, bc_rcmp_status = refresh_or_retain_source(
        country="Canada",
        existing_cases=existing_cases,
        fetcher=lambda: fetch_bc_rcmp_wanted_cases(
            limit=_optional_limit(args.bc_rcmp_limit)
        ),
        id_prefix="rcmp-bc-",
        name="British Columbia RCMP wanted news releases",
        selected_source_ids=selected_source_ids,
        previous_status=previous_status_by_id.get("rcmp-bc"),
    )
    vancouver_cases, vancouver_status = refresh_or_retain_source(
        country="Canada",
        existing_cases=existing_cases,
        fetcher=lambda: fetch_vancouver_wanted_cases(
            limit=_optional_limit(args.vancouver_limit)
        ),
        id_prefix="vpd-",
        name="Vancouver Police wanted news releases",
        selected_source_ids=selected_source_ids,
        previous_status=previous_status_by_id.get("vpd"),
    )
    cfseu_cases, cfseu_status = refresh_or_retain_source(
        country="Canada",
        existing_cases=existing_cases,
        fetcher=lambda: fetch_cfseu_bc_wanted_cases(
            limit=_optional_limit(args.cfseu_bc_limit)
        ),
        id_prefix="cfseu-bc-",
        name="CFSEU-BC wanted news releases",
        selected_source_ids=selected_source_ids,
        previous_status=previous_status_by_id.get("cfseu-bc"),
    )
    rewards_for_justice_cases, rewards_for_justice_status = refresh_or_retain_source(
        country="US",
        existing_cases=existing_cases,
        fetcher=lambda: fetch_rewards_for_justice_cases(
            limit=_optional_limit(args.rewards_for_justice_limit),
            excluded_source_urls=excluded_source_urls,
        ),
        id_prefix="rfj-",
        name="U.S. Department of State Rewards for Justice",
        selected_source_ids=selected_source_ids,
        previous_status=previous_status_by_id.get("rfj"),
    )
    us_marshals_cases, us_marshals_status = refresh_or_retain_source(
        country="US",
        existing_cases=existing_cases,
        fetcher=lambda: fetch_us_marshals_cases(
            limit=_optional_limit(args.us_marshals_limit)
        ),
        id_prefix="usms-",
        name="U.S. Marshals Service profiled fugitives with cash rewards",
        selected_source_ids=selected_source_ids,
        previous_status=previous_status_by_id.get("usms"),
    )
    nova_scotia_cases, nova_scotia_status = refresh_or_retain_source(
        country="Canada",
        existing_cases=existing_cases,
        fetcher=lambda: fetch_nova_scotia_reward_cases(
            limit=_optional_limit(args.nova_scotia_limit)
        ),
        id_prefix="ns-reward-",
        name="Nova Scotia Rewards for Major Unsolved Crimes",
        selected_source_ids=selected_source_ids,
        previous_status=previous_status_by_id.get("ns-reward"),
    )
    uspis_cases, uspis_status = refresh_or_retain_source(
        country="US",
        existing_cases=existing_cases,
        fetcher=lambda: fetch_uspis_cases(
            limit=_optional_limit(args.uspis_limit),
            excluded_source_urls=excluded_source_urls,
        ),
        id_prefix="uspis-",
        name="U.S. Postal Inspection Service wanted posters with cash rewards",
        selected_source_ids=selected_source_ids,
        previous_status=previous_status_by_id.get("uspis"),
    )
    texas_published_dates = {
        str(item.get("id")): str(item.get("publishedDate"))
        for item in existing_cases
        if str(item.get("id", "")).startswith("txdps-")
        and item.get("publishedDate")
    }
    texas_dps_cases, texas_dps_status = refresh_or_retain_source(
        country="US",
        existing_cases=existing_cases,
        fetcher=lambda: fetch_texas_dps_cases(
            limit=_optional_limit(args.texas_dps_limit),
            known_published_dates=texas_published_dates,
        ),
        id_prefix="txdps-",
        name="Texas DPS active Most Wanted reward directories",
        selected_source_ids=selected_source_ids,
        previous_status=previous_status_by_id.get("txdps"),
    )
    china_police_cases, china_police_status = refresh_or_retain_source(
        country="China",
        existing_cases=existing_cases,
        fetcher=lambda: fetch_china_police_reward_cases(
            limit=_optional_limit(args.china_police_limit),
        ),
        id_prefix="cn-police-",
        name="Mainland China official public-security criminal reward notices",
        selected_source_ids=selected_source_ids,
        previous_status=previous_status_by_id.get("cn-police"),
        allow_empty=True,
    )
    source_cases = normalize_reward_metadata(
        deduplicate_cases(
            [
                *fbi_cases,
                *opp_cases,
                *rcmp_cases,
                *quebec_cases,
                *edmonton_cases,
                *bc_rcmp_cases,
                *vancouver_cases,
                *cfseu_cases,
                *rewards_for_justice_cases,
                *us_marshals_cases,
                *nova_scotia_cases,
                *uspis_cases,
                *texas_dps_cases,
                *china_police_cases,
            ]
        )
    )
    cases = merge_cross_source_cases(source_cases)
    cases.sort(
        key=lambda item: str(item.get("publishedDate", "")),
        reverse=True,
    )
    if not cases:
        print("No cases were imported.")
        return 1

    source_statuses = [
        fbi_status,
        opp_status,
        rcmp_status,
        quebec_status,
        edmonton_status,
        bc_rcmp_status,
        vancouver_status,
        cfseu_status,
        rewards_for_justice_status,
        us_marshals_status,
        nova_scotia_status,
        uspis_status,
        texas_dps_status,
        china_police_status,
    ]
    updated_at_datetime = datetime.now(UTC)
    updated_at = updated_at_datetime.isoformat()
    attach_source_refresh_history(
        source_statuses,
        previous_update_status,
        selected_source_ids=selected_source_ids,
        updated_at=updated_at,
    )
    updated_today_count = sum(
        _is_same_utc_date(status.get("lastSuccessAt"), updated_at_datetime)
        for status in source_statuses
    )
    validate_data_quality(source_cases)
    validate_data_quality(cases)
    update_status = {
        "updatedAt": updated_at,
        "allSourcesFresh": all(status["success"] for status in source_statuses),
        "allSourcesUpdatedToday": updated_today_count == len(source_statuses),
        "totalCount": len(cases),
        "batch": {
            "name": args.batch or "full",
            "requestedSources": [
                source_id for source_id in SOURCE_IDS if source_id in selected_source_ids
            ],
            "updatedToday": updated_today_count,
            "totalSources": len(source_statuses),
        },
        "sources": source_statuses,
    }
    quality_report = build_data_quality_report(
        cases,
        generated_at=updated_at,
        source_statuses=source_statuses,
    )
    if args.output.resolve() == OUTPUT_PATH.resolve():
        write_json_atomic(SOURCE_CASES_PATH, source_cases)
    write_json_atomic(args.output, cases)
    write_json_atomic(STATUS_PATH, update_status)
    write_json_atomic(QUALITY_REPORT_PATH, quality_report)
    if get_database_url() and not args.skip_database:
        sync_case_snapshot(
            cases=cases,
            source_cases=source_cases,
            update_status=update_status,
            quality_report=quality_report,
        )

    print(f"Wrote {len(cases)} official records to {args.output}")
    print(
        f"Batch {args.batch or 'full'} attempted {len(selected_source_ids)} sources; "
        f"daily coverage is {updated_today_count}/{len(source_statuses)}"
    )
    for status in source_statuses:
        if not status["attemptedThisRun"]:
            state = "retained"
        else:
            state = "fresh" if status["success"] else "stale fallback"
        duration = status.get("durationSeconds")
        timing = f", {duration:.3f}s" if isinstance(duration, (int, float)) else ""
        print(
            f"- {status['country']}: {status['count']} records ({state}{timing})"
        )
        if status["error"]:
            print(f"  {status['error']}")
    if excluded_source_urls:
        print(f"Applied {len(excluded_source_urls)} reviewed source exclusions")
    print(
        f"Merged {quality_report['multiSourceCases']} cross-source cases; "
        f"{quality_report['rewards']['published']} records publish a cash amount"
    )

    attempted_statuses = [
        status for status in source_statuses if status["attemptedThisRun"]
    ]
    if args.strict and any(not status["success"] for status in attempted_statuses):
        return 1
    return 0


def _optional_limit(value: int) -> int | None:
    return value if value > 0 else None


def deduplicate_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique_cases: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for case in cases:
        case_id = str(case.get("id", ""))
        if not case_id or case_id in seen_ids:
            continue

        seen_ids.add(case_id)
        unique_cases.append(case)

    return unique_cases


if __name__ == "__main__":
    raise SystemExit(main())
