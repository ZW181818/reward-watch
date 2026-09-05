from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import CaseOverrideRow, CaseRow, SourceCaseRow, SyncRunRow, initialize_database
from .models import RewardCase


MANUAL_CASE_PREFIX = "manual-"


def _source_names(reward_case: dict[str, Any]) -> list[str]:
    names = {
        str(name).strip()
        for name in [
            reward_case.get("sourceAuthor") or reward_case.get("agency"),
            *[
                source.get("author")
                for source in reward_case.get("sourceRecords", [])
                if isinstance(source, dict)
            ],
        ]
        if name and str(name).strip()
    }
    return sorted(names)


def _source_id(case_id: str) -> str:
    prefixes = (
        "cfseu-bc",
        "cn-police",
        "ns-reward",
        "rcmp-bc",
        "rcmp-sk",
        "txdps",
        "usms",
        "uspis",
        "fbi",
        "opp",
        "fq",
        "eps",
        "vpd",
        "rfj",
    )
    return next((prefix for prefix in prefixes if case_id.startswith(f"{prefix}-")), case_id.split("-", 1)[0])


def _search_text(reward_case: dict[str, Any]) -> str:
    values = [
        reward_case.get("title"),
        reward_case.get("summary"),
        reward_case.get("sourceTitle"),
        reward_case.get("agency"),
        *_source_names(reward_case),
        *reward_case.get("regions", []),
    ]
    return " ".join(str(value).strip() for value in values if value).casefold()


def upsert_case_payload(
    session: Session,
    payload: dict[str, Any],
    *,
    now: datetime | None = None,
) -> CaseRow:
    timestamp = now or datetime.now(UTC)
    case_id = str(payload["id"])
    row = session.get(CaseRow, case_id)
    return _apply_case_payload(session, row, payload, timestamp=timestamp)


def _apply_case_payload(
    session: Session,
    row: CaseRow | None,
    payload: dict[str, Any],
    *,
    timestamp: datetime,
) -> CaseRow:
    case_id = str(payload["id"])
    source_names = _source_names(payload)
    if row is None:
        row = CaseRow(
            id=case_id,
            country=str(payload["country"]),
            status=str(payload["status"]),
            reward=payload.get("reward"),
            published_date=str(payload["publishedDate"]),
            source_name=source_names[0] if source_names else str(payload.get("agency", "")),
            search_text=_search_text(payload),
            regions_text="",
            sources_text="",
            payload=payload,
            created_at=timestamp,
            updated_at=timestamp,
        )
        session.add(row)

    row.country = str(payload["country"])
    row.status = str(payload["status"])
    row.reward = payload.get("reward")
    row.published_date = str(payload["publishedDate"])
    row.source_name = source_names[0] if source_names else str(payload.get("agency", ""))
    row.search_text = _search_text(payload)
    row.regions_text = "|" + "|".join(
        str(value).casefold() for value in payload.get("regions", [])
    ) + "|"
    row.sources_text = "|" + "|".join(value.casefold() for value in source_names) + "|"
    row.payload = payload
    row.updated_at = timestamp
    return row


def sync_case_snapshot(
    *,
    cases: list[dict[str, Any]],
    source_cases: list[dict[str, Any]],
    update_status: dict[str, Any],
    quality_report: dict[str, Any],
    database_url: str | None = None,
) -> None:
    engine = initialize_database(database_url)
    now = datetime.now(UTC)

    with Session(engine) as session, session.begin():
        current_case_rows = {
            row.id: row for row in session.scalars(select(CaseRow)).all()
        }
        current_case_ids = set(current_case_rows)
        next_case_ids: set[str] = set()

        for payload in cases:
            case_id = str(payload["id"])
            next_case_ids.add(case_id)
            existing_row = current_case_rows.get(case_id)
            if existing_row is not None and existing_row.payload == payload:
                continue
            _apply_case_payload(
                session,
                existing_row,
                payload,
                timestamp=now,
            )

        for removed_id in current_case_ids - next_case_ids:
            if removed_id.startswith(MANUAL_CASE_PREFIX):
                continue
            session.delete(current_case_rows[removed_id])

        current_source_rows = {
            row.id: row for row in session.scalars(select(SourceCaseRow)).all()
        }
        current_source_ids = set(current_source_rows)
        next_source_ids: set[str] = set()
        for payload in source_cases:
            case_id = str(payload["id"])
            next_source_ids.add(case_id)
            row = current_source_rows.get(case_id)
            source_id = _source_id(case_id)
            if (
                row is not None
                and row.source_id == source_id
                and row.payload == payload
            ):
                continue
            if row is None:
                session.add(
                    SourceCaseRow(
                        id=case_id,
                        source_id=source_id,
                        payload=payload,
                        updated_at=now,
                    )
                )
            else:
                row.source_id = source_id
                row.payload = payload
                row.updated_at = now

        for removed_id in current_source_ids - next_source_ids:
            session.delete(current_source_rows[removed_id])

        session.add(
            SyncRunRow(
                started_at=datetime.fromisoformat(str(update_status["updatedAt"])),
                completed_at=now,
                all_sources_fresh=bool(update_status["allSourcesFresh"]),
                total_count=int(update_status["totalCount"]),
                status_payload=update_status,
                quality_payload=quality_report,
            )
        )

    engine.dispose()


def load_database_cases(database_url: str | None = None) -> list[RewardCase] | None:
    engine = initialize_database(database_url)
    try:
        with Session(engine) as session:
            if session.scalar(select(SyncRunRow.id).limit(1)) is None:
                return None

            rows = session.scalars(select(CaseRow).order_by(CaseRow.published_date.desc())).all()
            overrides = {
                item.case_id: item
                for item in session.scalars(select(CaseOverrideRow)).all()
            }
            cases: list[RewardCase] = []
            for row in rows:
                override = overrides.get(row.id)
                if override and (not override.is_visible or override.review_status != "published"):
                    continue

                payload = dict(row.payload)
                if override:
                    payload.update(override.fields)
                cases.append(RewardCase.model_validate(payload))
            return cases
    finally:
        engine.dispose()
