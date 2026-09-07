from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import re
import tempfile
import unittest
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event, func, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.database import (
    CaseOverrideRow,
    CaseRow,
    SnapshotFingerprintRow,
    SourceCaseRow,
    SyncRunRow,
    initialize_database,
    release_database_engine,
)
from app.storage import sync_case_snapshot, upsert_case_payload


def make_payload(case_id: str, title: str) -> dict[str, Any]:
    return {
        "id": case_id,
        "title": title,
        "agency": "Federal Bureau of Investigation",
        "country": "US",
        "regions": ["Federal"],
        "reward": 1_000,
        "rewardCurrency": "USD",
        "status": "Open",
        "summary": "A source-backed reward notice used by the sync efficiency tests.",
        "publishedDate": "2026-08-01",
        "lastVerified": "2026-08-05",
        "sourceUrl": f"https://example.test/{case_id}",
        "sourceAuthor": "Federal Bureau of Investigation",
        "sourceRecords": [],
        "imageUrl": f"https://example.test/{case_id}.jpg",
        "imageUrls": [f"https://example.test/{case_id}.jpg"],
    }


def update_status(timestamp: str, total_count: int) -> dict[str, Any]:
    return {
        "updatedAt": timestamp,
        "allSourcesFresh": True,
        "totalCount": total_count,
        "sources": [],
    }


def _normalized_sql(statement: str) -> str:
    return re.sub(r"\s+", " ", statement.replace('"', "").lower()).strip()


def _parameter_text(parameters: Any) -> str:
    if isinstance(parameters, dict):
        return " ".join(str(value) for value in parameters.values())
    if isinstance(parameters, (list, tuple)):
        return " ".join(_parameter_text(value) for value in parameters)
    return str(parameters)


class SyncEfficiencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.directory.cleanup()

    def database_url(self, name: str = "sync.db") -> str:
        return f"sqlite:///{Path(self.directory.name, name).as_posix()}"

    def sync(
        self,
        cases: list[dict[str, Any]],
        *,
        timestamp: str,
        database_url: str | None = None,
        source_cases: list[dict[str, Any]] | None = None,
        total_count: int | None = None,
    ) -> None:
        sync_case_snapshot(
            cases=deepcopy(cases),
            source_cases=deepcopy(source_cases if source_cases is not None else cases),
            update_status=update_status(
                timestamp,
                len(cases) if total_count is None else total_count,
            ),
            quality_report={"checks": {"uniqueCaseIds": True}},
            database_url=database_url or self.database_url(),
        )

    def capture_sync_sql(self, *args: Any, **kwargs: Any) -> list[tuple[str, Any]]:
        statements: list[tuple[str, Any]] = []

        def capture(
            _connection: Any,
            _cursor: Any,
            statement: str,
            parameters: Any,
            _context: Any,
            _executemany: bool,
        ) -> None:
            statements.append((statement, parameters))

        event.listen(Engine, "before_cursor_execute", capture)
        try:
            self.sync(*args, **kwargs)
        finally:
            event.remove(Engine, "before_cursor_execute", capture)
        return statements

    def assert_no_source_payload_selects(
        self,
        statements: list[tuple[str, Any]],
    ) -> None:
        offending = []
        for statement, parameters in statements:
            sql = _normalized_sql(statement)
            if not sql.startswith("select"):
                continue
            if re.search(r"(?<![a-z0-9_])source_cases\.payload", sql):
                offending.append((sql, parameters))
        self.assertEqual(offending, [], f"source payload SELECTs found: {offending}")

    def assert_case_payload_selects_are_manual_only(
        self,
        statements: list[tuple[str, Any]],
    ) -> None:
        offending = []
        for statement, parameters in statements:
            sql = _normalized_sql(statement)
            if not sql.startswith("select") or not re.search(
                r"(?<![a-z0-9_])cases\.payload",
                sql,
            ):
                continue
            parameters_text = _parameter_text(parameters).lower()
            if " where " not in f" {sql} " or "manual-" not in parameters_text:
                offending.append((sql, parameters))
        self.assertEqual(
            offending,
            [],
            f"non-manual case payload SELECTs found: {offending}",
        )

    def test_sync_never_downloads_official_or_source_payloads(self) -> None:
        url = self.database_url()
        original = make_payload("fbi-efficient-a", "Original title")

        first_sync = self.capture_sync_sql(
            [original],
            timestamp="2026-08-05T10:00:00+00:00",
            database_url=url,
        )
        self.assert_no_source_payload_selects(first_sync)
        self.assert_case_payload_selects_are_manual_only(first_sync)

        stable_sync = self.capture_sync_sql(
            [dict(reversed(list(original.items())))],
            timestamp="2026-08-05T11:00:00+00:00",
            database_url=url,
        )
        self.assert_no_source_payload_selects(stable_sync)
        case_payload_selects = [
            sql
            for statement, _parameters in stable_sync
            if (sql := _normalized_sql(statement)).startswith("select")
            and re.search(r"(?<![a-z0-9_])cases\.payload", sql)
        ]
        self.assertEqual(case_payload_selects, [])

        changed = deepcopy(original)
        changed["title"] = "Changed title"
        changed_sync = self.capture_sync_sql(
            [changed],
            timestamp="2026-08-05T12:00:00+00:00",
            database_url=url,
        )
        self.assert_no_source_payload_selects(changed_sync)
        self.assert_case_payload_selects_are_manual_only(changed_sync)

    def test_same_payload_with_different_key_order_is_not_rewritten(self) -> None:
        url = self.database_url()
        payload = make_payload("fbi-efficient-order", "Stable title")
        self.sync([payload], timestamp="2026-08-05T10:00:00+00:00", database_url=url)

        engine = initialize_database(url)
        try:
            with Session(engine) as session:
                first_case_updated_at = session.scalar(
                    select(CaseRow.updated_at).where(CaseRow.id == payload["id"])
                )
        finally:
            release_database_engine(engine)

        reordered = dict(reversed(list(payload.items())))
        self.sync(
            [reordered],
            timestamp="2026-08-05T11:00:00+00:00",
            database_url=url,
        )

        engine = initialize_database(url)
        try:
            with Session(engine) as session:
                self.assertEqual(
                    session.scalar(
                        select(CaseRow.updated_at).where(CaseRow.id == payload["id"])
                    ),
                    first_case_updated_at,
                )
        finally:
            release_database_engine(engine)

    def test_one_changed_payload_only_rewrites_that_row(self) -> None:
        url = self.database_url()
        changed_payload = make_payload("fbi-efficient-change", "Before")
        stable_payload = make_payload("fbi-efficient-stable", "Always stable")
        self.sync(
            [changed_payload, stable_payload],
            timestamp="2026-08-05T10:00:00+00:00",
            database_url=url,
        )

        engine = initialize_database(url)
        try:
            with Session(engine) as session:
                before = dict(
                    session.execute(select(CaseRow.id, CaseRow.updated_at)).all()
                )
        finally:
            release_database_engine(engine)

        changed_payload["title"] = "After"
        self.sync(
            [changed_payload, stable_payload],
            timestamp="2026-08-05T11:00:00+00:00",
            database_url=url,
        )

        engine = initialize_database(url)
        try:
            with Session(engine) as session:
                rows = {
                    row.id: row
                    for row in session.scalars(select(CaseRow)).all()
                }
                self.assertEqual(rows[changed_payload["id"]].payload["title"], "After")
                self.assertNotEqual(rows[changed_payload["id"]].updated_at, before[changed_payload["id"]])
                self.assertEqual(rows[stable_payload["id"]].updated_at, before[stable_payload["id"]])
        finally:
            release_database_engine(engine)

    def test_manual_case_and_override_survive_snapshot_sync_unchanged(self) -> None:
        url = self.database_url()
        official = make_payload("fbi-efficient-official", "Official")
        self.sync([official], timestamp="2026-08-05T10:00:00+00:00", database_url=url)

        manual = make_payload("manual-efficient-notice", "Manual notice")
        manual["sourceKind"] = "publisher"
        manual_timestamp = datetime(2026, 8, 5, 10, 30, tzinfo=UTC)
        engine = initialize_database(url)
        try:
            with Session(engine) as session, session.begin():
                upsert_case_payload(session, manual, now=manual_timestamp)
                session.add(
                    CaseOverrideRow(
                        case_id=manual["id"],
                        fields={"title": "Reviewed manual notice"},
                        is_visible=False,
                        review_status="draft",
                        note="Keep this editorial state",
                        updated_by="admin@example.test",
                        updated_at=manual_timestamp,
                    )
                )
        finally:
            release_database_engine(engine)

        official["title"] = "Official changed"
        self.sync([official], timestamp="2026-08-05T11:00:00+00:00", database_url=url)

        engine = initialize_database(url)
        try:
            with Session(engine) as session:
                row = session.get(CaseRow, manual["id"])
                override = session.get(CaseOverrideRow, manual["id"])
                fingerprint = session.get(
                    SnapshotFingerprintRow,
                    {"collection": "cases", "item_id": manual["id"]},
                )
                self.assertIsNotNone(row)
                self.assertEqual(row.payload, manual)
                self.assertEqual(row.created_at, manual_timestamp.replace(tzinfo=None))
                self.assertEqual(row.updated_at, manual_timestamp.replace(tzinfo=None))
                self.assertIsNotNone(override)
                self.assertEqual(override.fields, {"title": "Reviewed manual notice"})
                self.assertFalse(override.is_visible)
                self.assertEqual(override.review_status, "draft")
                self.assertEqual(override.note, "Keep this editorial state")
                self.assertIsNone(fingerprint)
        finally:
            release_database_engine(engine)

    def test_duplicate_ids_and_inconsistent_total_count_are_rejected(self) -> None:
        payload = make_payload("fbi-efficient-invalid", "Invalid snapshot")
        invalid_snapshots = (
            (
                "duplicate case ID",
                [payload, deepcopy(payload)],
                [payload],
                2,
                "duplicate IDs",
            ),
            (
                "duplicate source ID",
                [payload],
                [payload, deepcopy(payload)],
                1,
                "duplicate IDs",
            ),
            (
                "inconsistent total count",
                [payload],
                [payload],
                2,
                "count does not match",
            ),
        )
        for index, (label, cases, source_cases, total_count, error) in enumerate(
            invalid_snapshots
        ):
            with self.subTest(label=label):
                url = self.database_url(f"invalid-{index}.db")
                with self.assertRaisesRegex(ValueError, error):
                    self.sync(
                        cases,
                        source_cases=source_cases,
                        total_count=total_count,
                        timestamp="2026-08-05T10:00:00+00:00",
                        database_url=url,
                    )
                probe = create_engine(url)
                try:
                    self.assertNotIn("snapshot_fingerprints", inspect(probe).get_table_names())
                finally:
                    probe.dispose()

    def test_older_snapshot_is_rejected_without_changing_data(self) -> None:
        url = self.database_url()
        payload = make_payload("fbi-efficient-old", "Current title")
        self.sync([payload], timestamp="2026-08-05T12:00:00+00:00", database_url=url)

        stale = deepcopy(payload)
        stale["title"] = "Stale title"
        with self.assertRaisesRegex(ValueError, "newer database snapshot"):
            self.sync(
                [stale],
                timestamp="2026-08-05T11:00:00+00:00",
                database_url=url,
            )

        engine = initialize_database(url)
        try:
            with Session(engine) as session:
                row = session.get(CaseRow, payload["id"])
                self.assertEqual(row.payload["title"], "Current title")
                self.assertEqual(
                    session.scalar(select(func.count()).select_from(SyncRunRow)),
                    1,
                )
        finally:
            release_database_engine(engine)

    def test_fingerprint_table_is_created_and_seeded_on_first_sync(self) -> None:
        url = self.database_url()
        probe = create_engine(url)
        try:
            self.assertNotIn("snapshot_fingerprints", inspect(probe).get_table_names())
        finally:
            probe.dispose()

        payload = make_payload("fbi-efficient-first", "First snapshot")
        self.sync([payload], timestamp="2026-08-05T10:00:00+00:00", database_url=url)

        engine = initialize_database(url)
        try:
            self.assertIn("snapshot_fingerprints", inspect(engine).get_table_names())
            with Session(engine) as session:
                fingerprints = {
                    (row.collection, row.item_id): row.payload_hash
                    for row in session.scalars(select(SnapshotFingerprintRow)).all()
                }
                self.assertEqual(
                    set(fingerprints),
                    {("cases", payload["id"])},
                )
                self.assertTrue(all(len(value) == 64 for value in fingerprints.values()))
        finally:
            release_database_engine(engine)

    def test_first_catalog_migration_removes_legacy_source_payloads(self) -> None:
        url = self.database_url()
        legacy = make_payload("fbi-efficient-legacy-source", "Legacy source copy")
        engine = initialize_database(url)
        try:
            with Session(engine) as session, session.begin():
                session.add(
                    SourceCaseRow(
                        id=legacy["id"],
                        source_id="fbi",
                        payload=legacy,
                        updated_at=datetime.now(UTC),
                    )
                )
                session.add(
                    SnapshotFingerprintRow(
                        collection="source_cases",
                        item_id=legacy["id"],
                        payload_hash="0" * 64,
                    )
                )
        finally:
            release_database_engine(engine)

        current = make_payload("fbi-efficient-current", "Current case")
        self.sync(
            [current],
            source_cases=[legacy],
            timestamp="2026-08-05T10:00:00+00:00",
            database_url=url,
        )

        engine = initialize_database(url)
        try:
            with Session(engine) as session:
                self.assertEqual(
                    session.scalar(select(func.count()).select_from(SourceCaseRow)),
                    0,
                )
                self.assertEqual(
                    session.scalar(
                        select(func.count())
                        .select_from(SnapshotFingerprintRow)
                        .where(SnapshotFingerprintRow.collection == "source_cases")
                    ),
                    0,
                )
        finally:
            release_database_engine(engine)


if __name__ == "__main__":
    unittest.main()
