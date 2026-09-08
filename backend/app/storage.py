from __future__ import annotations

from collections import Counter, OrderedDict
from datetime import UTC, datetime
from hashlib import sha256
import json
from math import ceil
from threading import RLock
from time import monotonic
from typing import Any, Iterable, Literal, Sequence

from sqlalchemy import (
    and_,
    delete,
    event,
    exists,
    func,
    literal,
    or_,
    select,
    union_all,
    update,
)
from sqlalchemy.orm import Session

from .database import (
    CaseMapLocationOverrideRow,
    CaseOverrideRow,
    CaseRow,
    PublicCaseAliasRow,
    PublicCaseMapRow,
    PublicCaseRegionRow,
    PublicCaseRow,
    PublicCaseSourceRow,
    PublicCatalogStateRow,
    SnapshotFingerprintRow,
    SourceCaseRow,
    SyncRunRow,
    create_database_engine,
    get_database_url,
    initialize_database,
    release_database_engine,
)
from .map_data import build_case_map_item, get_map_generated_at
from .models import (
    CaseFacetOption,
    CaseFacets,
    CaseListResponse,
    CaseMapItem,
    CaseMapResponse,
    RewardCase,
)


MANUAL_CASE_PREFIX = "manual-"
PUBLIC_CATALOG_KEY = "primary"
PUBLIC_PROJECTION_VERSION = 2
CASE_FINGERPRINT_VERSION = "case-index-v1"
DELETE_BATCH_SIZE = 400
SYNC_RUN_RETENTION = 500
PUBLIC_CACHE_TTL_SECONDS = 300.0
PUBLIC_PAGE_CACHE_SIZE = 256
PUBLIC_DETAIL_CACHE_SIZE = 4096
PUBLIC_FACET_CACHE_SIZE = 128
SortMode = Literal["published_desc", "reward_desc", "reward_asc", "title_asc"]

_PUBLIC_CACHE_LOCK = RLock()
_PUBLIC_PAGE_CACHE: OrderedDict[tuple[Any, ...], tuple[float, CaseListResponse]] = OrderedDict()
_PUBLIC_DETAIL_CACHE: OrderedDict[str, tuple[float, tuple[bool, RewardCase | None]]] = OrderedDict()
_PUBLIC_FACET_CACHE: OrderedDict[tuple[Any, ...], tuple[float, CaseFacets]] = OrderedDict()
_PUBLIC_MAP_CACHE: tuple[float, CaseMapResponse] | None = None
_PUBLIC_READY_DATABASES: set[str] = set()


def clear_public_query_cache() -> None:
    global _PUBLIC_MAP_CACHE
    with _PUBLIC_CACHE_LOCK:
        _PUBLIC_PAGE_CACHE.clear()
        _PUBLIC_DETAIL_CACHE.clear()
        _PUBLIC_FACET_CACHE.clear()
        _PUBLIC_MAP_CACHE = None


def _clear_public_cache_after_commit(session: Session) -> None:
    event.listen(session, "after_commit", lambda _session: clear_public_query_cache(), once=True)


def _cache_get(cache: OrderedDict, key):
    with _PUBLIC_CACHE_LOCK:
        cached = cache.get(key)
        if cached is None:
            return None
        expires_at, value = cached
        if expires_at <= monotonic():
            del cache[key]
            return None
        cache.move_to_end(key)
        if isinstance(value, (CaseListResponse, CaseFacets)):
            return value.model_copy(deep=True)
        ready, reward_case = value
        return ready, reward_case.model_copy(deep=True) if reward_case else None


def _cache_put(cache: OrderedDict, key, value, *, max_size: int) -> None:
    with _PUBLIC_CACHE_LOCK:
        if isinstance(value, (CaseListResponse, CaseFacets)):
            stored_value = value.model_copy(deep=True)
        else:
            ready, reward_case = value
            stored_value = (
                ready,
                reward_case.model_copy(deep=True) if reward_case else None,
            )
        cache[key] = (monotonic() + PUBLIC_CACHE_TTL_SECONDS, stored_value)
        cache.move_to_end(key)
        while len(cache) > max_size:
            cache.popitem(last=False)


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


def _canonical_hash(payload: dict[str, Any], *, version: str) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return sha256(f"{version}\n{serialized}".encode("utf-8")).hexdigest()


def _case_row_values(payload: dict[str, Any], *, timestamp: datetime) -> dict[str, Any]:
    source_names = _source_names(payload)
    return {
        "id": str(payload["id"]),
        "country": str(payload["country"]),
        "status": str(payload["status"]),
        "reward": payload.get("reward"),
        "published_date": str(payload["publishedDate"]),
        "source_name": source_names[0] if source_names else str(payload.get("agency", "")),
        "search_text": _search_text(payload),
        "regions_text": "|" + "|".join(
            str(value).casefold() for value in payload.get("regions", [])
        ) + "|",
        "sources_text": "|" + "|".join(value.casefold() for value in source_names) + "|",
        "payload": payload,
        "updated_at": timestamp,
    }


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
    values = _case_row_values(payload, timestamp=timestamp)
    if row is None:
        row = CaseRow(**values, created_at=timestamp)
        session.add(row)
        return row

    for key, value in values.items():
        if key != "id":
            setattr(row, key, value)
    return row


def _effective_payload(row: CaseRow, override: CaseOverrideRow | None) -> dict[str, Any]:
    payload = dict(row.payload)
    if override:
        payload.update(override.fields)
    return payload


def _is_public_override(override: CaseOverrideRow | None) -> bool:
    return override is None or (
        override.is_visible and override.review_status == "published"
    )


def _projection_parts(
    payload: dict[str, Any],
    *,
    timestamp: datetime,
    map_locations: list[dict[str, Any]] | None = None,
):
    normalized = RewardCase.model_validate(payload).model_dump(mode="json")
    case_id = normalized["id"]
    public_case = PublicCaseRow(
        id=case_id,
        country=normalized["country"],
        status=normalized["status"],
        reward=normalized.get("reward"),
        published_date=normalized["publishedDate"],
        title_sort=normalized["title"].casefold(),
        search_text=_search_text(normalized),
        payload=normalized,
        updated_at=timestamp,
    )

    regions_by_key = {
        str(value).strip().casefold(): str(value).strip()
        for value in normalized.get("regions", [])
        if str(value).strip()
    }
    sources_by_key = {
        value.casefold(): value
        for value in _source_names(normalized)
        if value
    }
    aliases = {
        str(source.get("caseId", "")).strip()
        for source in normalized.get("sourceRecords", [])
        if isinstance(source, dict) and str(source.get("caseId", "")).strip()
    }
    aliases.discard(case_id)
    map_item = build_case_map_item(normalized, map_locations)
    map_row = (
        PublicCaseMapRow(
            case_id=case_id,
            payload=map_item.model_dump(mode="json"),
            updated_at=timestamp,
        )
        if map_item is not None
        else None
    )

    return (
        public_case,
        [
            PublicCaseRegionRow(case_id=case_id, value_folded=key, value=value)
            for key, value in sorted(regions_by_key.items())
        ],
        [
            PublicCaseSourceRow(case_id=case_id, value_folded=key, value=value)
            for key, value in sorted(sources_by_key.items())
        ],
        [PublicCaseAliasRow(alias_id=alias, case_id=case_id) for alias in sorted(aliases)],
        map_row,
    )


def _chunks(values: Iterable[str]) -> Iterable[list[str]]:
    items = sorted(set(values))
    for index in range(0, len(items), DELETE_BATCH_SIZE):
        yield items[index : index + DELETE_BATCH_SIZE]


def _delete_public_projection(session: Session, case_ids: Iterable[str]) -> None:
    for batch in _chunks(case_ids):
        session.execute(delete(PublicCaseAliasRow).where(PublicCaseAliasRow.case_id.in_(batch)))
        session.execute(delete(PublicCaseMapRow).where(PublicCaseMapRow.case_id.in_(batch)))
        session.execute(delete(PublicCaseRegionRow).where(PublicCaseRegionRow.case_id.in_(batch)))
        session.execute(delete(PublicCaseSourceRow).where(PublicCaseSourceRow.case_id.in_(batch)))
        session.execute(delete(PublicCaseRow).where(PublicCaseRow.id.in_(batch)))


def _replace_public_projection(
    session: Session,
    rows: Sequence[tuple[CaseRow, CaseOverrideRow | None]],
    *,
    removed_ids: Iterable[str] = (),
    timestamp: datetime,
) -> None:
    affected_ids = {row.id for row, _ in rows} | set(removed_ids)
    _delete_public_projection(session, affected_ids)
    session.flush()

    public_rows: list[PublicCaseRow] = []
    region_rows: list[PublicCaseRegionRow] = []
    source_rows: list[PublicCaseSourceRow] = []
    alias_rows: list[PublicCaseAliasRow] = []
    map_rows: list[PublicCaseMapRow] = []
    row_ids = [row.id for row, _ in rows]
    map_overrides = {
        override.case_id: override.locations
        for override in session.scalars(
            select(CaseMapLocationOverrideRow).where(
                CaseMapLocationOverrideRow.case_id.in_(row_ids)
            )
        ).all()
    } if row_ids else {}
    for row, override in rows:
        if not _is_public_override(override):
            continue
        public_case, regions, sources, aliases, map_row = _projection_parts(
            _effective_payload(row, override),
            timestamp=timestamp,
            map_locations=map_overrides.get(row.id),
        )
        public_rows.append(public_case)
        region_rows.extend(regions)
        source_rows.extend(sources)
        alias_rows.extend(aliases)
        if map_row is not None:
            map_rows.append(map_row)

    session.add_all(public_rows)
    session.add_all(region_rows)
    session.add_all(source_rows)
    session.add_all(alias_rows)
    session.add_all(map_rows)


def _catalog_state(session: Session) -> PublicCatalogStateRow | None:
    state = session.scalar(
        select(PublicCatalogStateRow)
        .where(PublicCatalogStateRow.key == PUBLIC_CATALOG_KEY)
        .limit(1)
    )
    if (
        state is None
        or not state.ready
        or state.projection_version != PUBLIC_PROJECTION_VERSION
    ):
        return None
    return state


def _catalog_is_ready(
    session: Session,
    *,
    cache_key: str | None = None,
) -> bool:
    if cache_key:
        with _PUBLIC_CACHE_LOCK:
            if cache_key in _PUBLIC_READY_DATABASES:
                return True

    ready = _catalog_state(session) is not None
    if ready and cache_key:
        with _PUBLIC_CACHE_LOCK:
            _PUBLIC_READY_DATABASES.add(cache_key)
    return ready


def _set_catalog_ready(
    session: Session,
    *,
    timestamp: datetime,
    increment_revision: bool,
) -> PublicCatalogStateRow:
    session.flush()
    case_count = session.scalar(select(func.count()).select_from(PublicCaseRow)) or 0
    state = session.scalar(
        select(PublicCatalogStateRow)
        .where(PublicCatalogStateRow.key == PUBLIC_CATALOG_KEY)
        .limit(1)
    )
    if state is None:
        state = PublicCatalogStateRow(
            key=PUBLIC_CATALOG_KEY,
            projection_version=PUBLIC_PROJECTION_VERSION,
            revision=1,
            ready=True,
            case_count=case_count,
            updated_at=timestamp,
        )
        session.add(state)
        return state

    state.projection_version = PUBLIC_PROJECTION_VERSION
    state.revision = state.revision + 1 if increment_revision else max(state.revision, 1)
    state.ready = True
    state.case_count = case_count
    state.updated_at = timestamp
    return state


def _rebuild_public_catalog(
    session: Session,
    official_payloads: Sequence[dict[str, Any]],
    *,
    timestamp: datetime,
) -> None:
    # The complete official snapshot is already in memory in the sync worker.
    # Reuse it instead of downloading the same multi-megabyte payloads from
    # Neon during a first deployment or projection-version migration. Only
    # manual notices, which are not present in the generated snapshot, need to
    # be read from the database.
    manual_rows = session.scalars(
        select(CaseRow).where(CaseRow.id.startswith(MANUAL_CASE_PREFIX))
    ).all()
    official_rows = [
        CaseRow(**_case_row_values(payload, timestamp=timestamp), created_at=timestamp)
        for payload in official_payloads
    ]
    rows = [*official_rows, *manual_rows]
    overrides = {
        override.case_id: override
        for override in session.scalars(select(CaseOverrideRow)).all()
    }
    session.execute(delete(PublicCaseAliasRow))
    session.execute(delete(PublicCaseMapRow))
    session.execute(delete(PublicCaseRegionRow))
    session.execute(delete(PublicCaseSourceRow))
    session.execute(delete(PublicCaseRow))
    session.flush()
    _replace_public_projection(
        session,
        [(row, overrides.get(row.id)) for row in rows],
        timestamp=timestamp,
    )
    _set_catalog_ready(session, timestamp=timestamp, increment_revision=True)


def refresh_public_case(
    session: Session,
    row: CaseRow,
    override: CaseOverrideRow | None,
    *,
    now: datetime | None = None,
) -> None:
    """Refresh one effective public row inside the caller's admin transaction."""

    if _catalog_state(session) is None:
        return
    timestamp = now or datetime.now(UTC)
    _replace_public_projection(session, [(row, override)], timestamp=timestamp)
    _set_catalog_ready(session, timestamp=timestamp, increment_revision=True)
    _clear_public_cache_after_commit(session)


def remove_public_case(
    session: Session,
    case_id: str,
    *,
    now: datetime | None = None,
) -> None:
    if _catalog_state(session) is None:
        return
    timestamp = now or datetime.now(UTC)
    _delete_public_projection(session, [case_id])
    _set_catalog_ready(session, timestamp=timestamp, increment_revision=True)
    _clear_public_cache_after_commit(session)


def _validate_snapshot(
    cases: Sequence[dict[str, Any]],
    source_cases: Sequence[dict[str, Any]],
    update_status: dict[str, Any],
) -> datetime:
    case_ids = [str(payload["id"]) for payload in cases]
    source_ids = [str(payload["id"]) for payload in source_cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("The case snapshot contains duplicate IDs")
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("The source case snapshot contains duplicate IDs")
    if any(case_id.startswith(MANUAL_CASE_PREFIX) for case_id in case_ids):
        raise ValueError("Official snapshots cannot contain manual case IDs")
    if int(update_status["totalCount"]) != len(cases):
        raise ValueError("The update status count does not match the case snapshot")

    value = str(update_status["updatedAt"]).replace("Z", "+00:00")
    timestamp = datetime.fromisoformat(value)
    return timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=UTC)


def _replace_fingerprints(
    session: Session,
    collection: str,
    values: dict[str, str],
    removed_ids: Iterable[str],
) -> None:
    affected = set(values) | set(removed_ids)
    for batch in _chunks(affected):
        session.execute(
            delete(SnapshotFingerprintRow).where(
                SnapshotFingerprintRow.collection == collection,
                SnapshotFingerprintRow.item_id.in_(batch),
            )
        )
    session.add_all(
        SnapshotFingerprintRow(
            collection=collection,
            item_id=item_id,
            payload_hash=payload_hash,
        )
        for item_id, payload_hash in values.items()
    )


def _delete_rows_by_id(session: Session, model, column, ids: Iterable[str]) -> None:
    for batch in _chunks(ids):
        session.execute(delete(model).where(column.in_(batch)))


def _acquire_snapshot_lock(session: Session) -> None:
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        session.execute(select(func.pg_advisory_xact_lock(7_466_927_747_243_101)))


def _normalize_db_datetime(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _trim_sync_history(session: Session) -> None:
    retained_ids = (
        select(SyncRunRow.id)
        .order_by(SyncRunRow.id.desc())
        .limit(SYNC_RUN_RETENTION)
        .subquery()
    )
    session.execute(
        delete(SyncRunRow).where(
            ~SyncRunRow.id.in_(select(retained_ids.c.id))
        )
    )


def sync_case_snapshot(
    *,
    cases: list[dict[str, Any]],
    source_cases: list[dict[str, Any]],
    update_status: dict[str, Any],
    quality_report: dict[str, Any],
    database_url: str | None = None,
) -> None:
    snapshot_started_at = _validate_snapshot(cases, source_cases, update_status)
    engine = initialize_database(database_url)
    now = datetime.now(UTC)

    try:
        with Session(engine) as session, session.begin():
            _acquire_snapshot_lock(session)
            latest_started_at = session.scalar(
                select(SyncRunRow.started_at)
                .order_by(SyncRunRow.started_at.desc())
                .limit(1)
            )
            if latest_started_at and snapshot_started_at < _normalize_db_datetime(latest_started_at):
                raise ValueError("Refusing to replace a newer database snapshot")

            existing_case_fingerprint_rows = session.execute(
                select(CaseRow.id, SnapshotFingerprintRow.payload_hash)
                .outerjoin(
                    SnapshotFingerprintRow,
                    and_(
                        SnapshotFingerprintRow.collection == "cases",
                        SnapshotFingerprintRow.item_id == CaseRow.id,
                    ),
                )
                .where(~CaseRow.id.startswith(MANUAL_CASE_PREFIX))
            ).all()
            existing_case_ids = {
                case_id for case_id, _payload_hash in existing_case_fingerprint_rows
            }
            case_fingerprints = {
                case_id: payload_hash
                for case_id, payload_hash in existing_case_fingerprint_rows
                if payload_hash is not None
            }
            next_case_ids = {str(payload["id"]) for payload in cases}
            removed_case_ids = existing_case_ids - next_case_ids
            case_hashes = {
                str(payload["id"]): _canonical_hash(
                    payload,
                    version=CASE_FINGERPRINT_VERSION,
                )
                for payload in cases
            }
            changed_case_payloads = [
                payload
                for payload in cases
                if str(payload["id"]) not in existing_case_ids
                or case_fingerprints.get(str(payload["id"])) != case_hashes[str(payload["id"])]
            ]

            case_updates = [
                _case_row_values(payload, timestamp=now)
                for payload in changed_case_payloads
                if str(payload["id"]) in existing_case_ids
            ]
            if case_updates:
                session.execute(update(CaseRow), case_updates)
            session.add_all(
                CaseRow(**_case_row_values(payload, timestamp=now), created_at=now)
                for payload in changed_case_payloads
                if str(payload["id"]) not in existing_case_ids
            )
            _delete_rows_by_id(session, CaseRow, CaseRow.id, removed_case_ids)
            _replace_fingerprints(
                session,
                "cases",
                {str(payload["id"]): case_hashes[str(payload["id"])] for payload in changed_case_payloads},
                removed_case_ids,
            )

            session.flush()
            if _catalog_state(session) is None:
                # Per-source normalized records already live in the versioned
                # source_cases.json artifact and are not read by the API or
                # admin application. Remove the legacy Neon duplicate during
                # this one-time catalog migration instead of spending storage,
                # reads, hashes, and writes on it at every refresh.
                session.execute(delete(SourceCaseRow))
                session.execute(
                    delete(SnapshotFingerprintRow).where(
                        SnapshotFingerprintRow.collection == "source_cases"
                    )
                )
                _rebuild_public_catalog(session, cases, timestamp=now)
            elif changed_case_payloads or removed_case_ids:
                changed_ids = [str(payload["id"]) for payload in changed_case_payloads]
                changed_rows = {
                    str(payload["id"]): CaseRow(
                        **_case_row_values(payload, timestamp=now),
                        created_at=now,
                    )
                    for payload in changed_case_payloads
                }
                overrides = {
                    override.case_id: override
                    for override in session.scalars(
                        select(CaseOverrideRow).where(CaseOverrideRow.case_id.in_(changed_ids))
                    ).all()
                } if changed_ids else {}
                _replace_public_projection(
                    session,
                    [(row, overrides.get(case_id)) for case_id, row in changed_rows.items()],
                    removed_ids=removed_case_ids,
                    timestamp=now,
                )
                _set_catalog_ready(session, timestamp=now, increment_revision=True)

            session.add(
                SyncRunRow(
                    started_at=snapshot_started_at,
                    completed_at=now,
                    all_sources_fresh=bool(update_status["allSourcesFresh"]),
                    total_count=int(update_status["totalCount"]),
                    status_payload=update_status,
                    quality_payload=quality_report,
                )
            )
            session.flush()
            _trim_sync_history(session)
        clear_public_query_cache()
    finally:
        release_database_engine(engine)


def _facet_options(values: Counter[str]) -> list[CaseFacetOption]:
    return [
        CaseFacetOption(value=value, count=count)
        for value, count in sorted(values.items(), key=lambda item: item[0].lower())
    ]


def query_database_case_page(
    *,
    q: str | None = None,
    country: str | None = None,
    region: str | None = None,
    status: str | None = None,
    source: str | None = None,
    reward_min: int | None = None,
    reward_max: int | None = None,
    sort: SortMode = "published_desc",
    page: int = 1,
    page_size: int = 12,
    database_url: str | None = None,
) -> CaseListResponse | None:
    cache_key = (
        q,
        country,
        region,
        status,
        source,
        reward_min,
        reward_max,
        sort,
        page,
        page_size,
    )
    if database_url is None:
        cached = _cache_get(_PUBLIC_PAGE_CACHE, cache_key)
        if cached is not None:
            return cached

    production_database_key = get_database_url() if database_url is None else None
    engine = create_database_engine(database_url)
    try:
        with Session(engine) as session:
            if not _catalog_is_ready(session, cache_key=production_database_key):
                return None

            base_conditions = []
            if q:
                base_conditions.append(PublicCaseRow.search_text.contains(q.casefold(), autoescape=True))
            if country:
                base_conditions.append(PublicCaseRow.country == country)

            facet_cache_key = (q, country)
            facets = (
                _cache_get(_PUBLIC_FACET_CACHE, facet_cache_key)
                if database_url is None
                else None
            )
            if facets is None:
                status_facets = (
                    select(
                        literal("status").label("kind"),
                        PublicCaseRow.status.label("value"),
                        func.count(PublicCaseRow.id).label("count"),
                    )
                    .where(*base_conditions)
                    .group_by(PublicCaseRow.status)
                )
                region_facets = (
                    select(
                        literal("region").label("kind"),
                        func.min(PublicCaseRegionRow.value).label("value"),
                        func.count(PublicCaseRegionRow.case_id).label("count"),
                    )
                    .join(PublicCaseRow, PublicCaseRow.id == PublicCaseRegionRow.case_id)
                    .where(*base_conditions)
                    .group_by(PublicCaseRegionRow.value_folded)
                )
                source_facets = (
                    select(
                        literal("source").label("kind"),
                        func.min(PublicCaseSourceRow.value).label("value"),
                        func.count(PublicCaseSourceRow.case_id).label("count"),
                    )
                    .join(PublicCaseRow, PublicCaseRow.id == PublicCaseSourceRow.case_id)
                    .where(*base_conditions)
                    .group_by(PublicCaseSourceRow.value_folded)
                )
                facet_counts: dict[str, Counter[str]] = {
                    "status": Counter(),
                    "region": Counter(),
                    "source": Counter(),
                }
                for kind, value, count in session.execute(
                    union_all(status_facets, region_facets, source_facets)
                ):
                    facet_counts[kind][value] = count
                facets = CaseFacets(
                    statuses=_facet_options(facet_counts["status"]),
                    regions=_facet_options(facet_counts["region"]),
                    sources=_facet_options(facet_counts["source"]),
                )
                if database_url is None:
                    _cache_put(
                        _PUBLIC_FACET_CACHE,
                        facet_cache_key,
                        facets,
                        max_size=PUBLIC_FACET_CACHE_SIZE,
                    )

            conditions = list(base_conditions)
            if region:
                conditions.append(
                    exists(
                        select(PublicCaseRegionRow.case_id).where(
                            PublicCaseRegionRow.case_id == PublicCaseRow.id,
                            PublicCaseRegionRow.value_folded == region.casefold(),
                        )
                    )
                )
            if status:
                conditions.append(PublicCaseRow.status == status)
            if source:
                conditions.append(
                    exists(
                        select(PublicCaseSourceRow.case_id).where(
                            PublicCaseSourceRow.case_id == PublicCaseRow.id,
                            PublicCaseSourceRow.value_folded == source.casefold(),
                        )
                    )
                )
            if reward_min is not None:
                conditions.append(PublicCaseRow.reward >= reward_min)
            if reward_max is not None:
                conditions.append(PublicCaseRow.reward <= reward_max)

            if sort == "reward_desc":
                ordering = (PublicCaseRow.reward.is_(None), PublicCaseRow.reward.desc())
            elif sort == "reward_asc":
                ordering = (PublicCaseRow.reward.is_(None), PublicCaseRow.reward.asc())
            elif sort == "title_asc":
                ordering = (PublicCaseRow.title_sort.asc(),)
            else:
                ordering = (PublicCaseRow.published_date.desc(),)

            page_rows = session.execute(
                select(
                    PublicCaseRow.payload,
                    func.count().over().label("total_count"),
                )
                .where(*conditions)
                .order_by(*ordering, PublicCaseRow.id.asc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            if page_rows:
                total = int(page_rows[0].total_count)
                payloads = [row.payload for row in page_rows]
            else:
                # A page beyond the end has no window row carrying the total.
                # Only that uncommon request needs a separate count query.
                total = session.scalar(
                    select(func.count()).select_from(PublicCaseRow).where(*conditions)
                ) or 0
                payloads = []
            total_pages = ceil(total / page_size) if total else 0
            result = CaseListResponse(
                items=[RewardCase.model_validate(payload) for payload in payloads],
                total=total,
                page=page,
                pageSize=page_size,
                totalPages=total_pages,
                facets=facets,
            )
            if database_url is None:
                _cache_put(
                    _PUBLIC_PAGE_CACHE,
                    cache_key,
                    result,
                    max_size=PUBLIC_PAGE_CACHE_SIZE,
                )
            return result
    finally:
        release_database_engine(engine)


def load_database_case(
    case_id: str,
    database_url: str | None = None,
) -> tuple[bool, RewardCase | None]:
    if database_url is None:
        cached = _cache_get(_PUBLIC_DETAIL_CACHE, case_id)
        if cached is not None:
            return cached

    production_database_key = get_database_url() if database_url is None else None
    engine = create_database_engine(database_url)
    try:
        with Session(engine) as session:
            if not _catalog_is_ready(session, cache_key=production_database_key):
                return False, None
            alias_case_id = (
                select(PublicCaseAliasRow.case_id)
                .where(PublicCaseAliasRow.alias_id == case_id)
                .limit(1)
                .scalar_subquery()
            )
            payload = session.scalar(
                select(PublicCaseRow.payload)
                .where(
                    or_(
                        PublicCaseRow.id == case_id,
                        PublicCaseRow.id == alias_case_id,
                    )
                )
                .order_by((PublicCaseRow.id == case_id).desc())
                .limit(1)
            )
            result = (
                True,
                RewardCase.model_validate(payload) if payload is not None else None,
            )
            if database_url is None:
                _cache_put(
                    _PUBLIC_DETAIL_CACHE,
                    case_id,
                    result,
                    max_size=PUBLIC_DETAIL_CACHE_SIZE,
                )
            return result
    finally:
        release_database_engine(engine)


def query_database_case_map(
    database_url: str | None = None,
) -> CaseMapResponse | None:
    global _PUBLIC_MAP_CACHE

    if database_url is None:
        with _PUBLIC_CACHE_LOCK:
            if _PUBLIC_MAP_CACHE is not None:
                expires_at, cached = _PUBLIC_MAP_CACHE
                if expires_at > monotonic():
                    return cached.model_copy(deep=True)
                _PUBLIC_MAP_CACHE = None

    production_database_key = get_database_url() if database_url is None else None
    engine = create_database_engine(database_url)
    try:
        with Session(engine) as session:
            if not _catalog_is_ready(session, cache_key=production_database_key):
                return None
            payloads = session.scalars(
                select(PublicCaseMapRow.payload).order_by(PublicCaseMapRow.case_id.asc())
            ).all()
            items = [CaseMapItem.model_validate(payload) for payload in payloads]
            result = CaseMapResponse(
                items=items,
                total=len(items),
                generatedAt=get_map_generated_at(),
            )
            if database_url is None:
                with _PUBLIC_CACHE_LOCK:
                    _PUBLIC_MAP_CACHE = (
                        monotonic() + PUBLIC_CACHE_TTL_SECONDS,
                        result.model_copy(deep=True),
                    )
            return result
    finally:
        release_database_engine(engine)


def load_database_cases(database_url: str | None = None) -> list[RewardCase] | None:
    """Compatibility loader for maintenance/tests; public endpoints use bounded queries."""

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
                if not _is_public_override(override):
                    continue
                cases.append(RewardCase.model_validate(_effective_payload(row, override)))
            return cases
    finally:
        release_database_engine(engine)
