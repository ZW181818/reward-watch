import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import CaseOverrideRow, CaseRow, initialize_database
from app.storage import load_database_cases, sync_case_snapshot
from scripts.hourly_sync import next_run


def make_payload(title: str = "Original title"):
    return {
        "id": "fbi-storage-test",
        "title": title,
        "agency": "Federal Bureau of Investigation",
        "country": "US",
        "regions": ["Federal"],
        "reward": 1000,
        "rewardCurrency": "USD",
        "status": "Open",
        "summary": "A detailed official summary used by the database test.",
        "publishedDate": "2026-08-01",
        "lastVerified": "2026-08-05",
        "sourceUrl": "https://fbi.test/storage",
        "sourceAuthor": "Federal Bureau of Investigation",
        "sourceRecords": [],
        "imageUrl": "https://fbi.test/storage.jpg",
        "imageUrls": ["https://fbi.test/storage.jpg"],
    }


def sync_payload(database_url: str, title: str = "Original title"):
    payload = make_payload(title)
    status = {
        "updatedAt": "2026-08-05T10:00:00+00:00",
        "allSourcesFresh": True,
        "totalCount": 1,
        "sources": [],
    }
    sync_case_snapshot(
        cases=[payload],
        source_cases=[payload],
        update_status=status,
        quality_report={"qualityGate": {"passed": True}},
        database_url=database_url,
    )


class StorageTests(unittest.TestCase):
    def test_admin_override_survives_a_source_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            database_url = f"sqlite:///{Path(directory, 'reward-watch.db').as_posix()}"
            sync_payload(database_url)

            engine = initialize_database(database_url)
            with Session(engine) as session, session.begin():
                session.add(
                    CaseOverrideRow(
                        case_id="fbi-storage-test",
                        fields={"title": "Reviewed title"},
                        is_visible=True,
                        review_status="published",
                        updated_by="admin@example.test",
                    )
                )
            engine.dispose()

            sync_payload(database_url, title="New upstream title")
            cases = load_database_cases(database_url)

            self.assertIsNotNone(cases)
            self.assertEqual(cases[0].title, "Reviewed title")

    def test_hidden_case_is_not_returned(self):
        with tempfile.TemporaryDirectory() as directory:
            database_url = f"sqlite:///{Path(directory, 'reward-watch.db').as_posix()}"
            sync_payload(database_url)

            engine = initialize_database(database_url)
            with Session(engine) as session, session.begin():
                session.add(
                    CaseOverrideRow(
                        case_id="fbi-storage-test",
                        fields={},
                        is_visible=False,
                        review_status="published",
                    )
                )
            engine.dispose()

            self.assertEqual(load_database_cases(database_url), [])

    def test_snapshot_sync_does_not_query_each_row_by_primary_key(self):
        with tempfile.TemporaryDirectory() as directory:
            database_url = f"sqlite:///{Path(directory, 'reward-watch.db').as_posix()}"

            with patch.object(
                Session,
                "get",
                side_effect=AssertionError("snapshot sync must use the preloaded row maps"),
            ):
                sync_payload(database_url)

            self.assertEqual(len(load_database_cases(database_url)), 1)

    def test_unchanged_snapshot_does_not_rewrite_case_row(self):
        with tempfile.TemporaryDirectory() as directory:
            database_url = f"sqlite:///{Path(directory, 'reward-watch.db').as_posix()}"
            sync_payload(database_url)

            engine = initialize_database(database_url)
            with Session(engine) as session:
                first_updated_at = session.scalar(select(CaseRow.updated_at))
            engine.dispose()

            sync_payload(database_url)

            engine = initialize_database(database_url)
            with Session(engine) as session:
                second_updated_at = session.scalar(select(CaseRow.updated_at))
            engine.dispose()

            self.assertEqual(second_updated_at, first_updated_at)

    def test_scheduler_uses_six_hour_intervals_at_minute_twenty(self):
        now = datetime(2026, 8, 5, 10, 25, tzinfo=UTC)
        self.assertEqual(next_run(now), datetime(2026, 8, 5, 12, 20, tzinfo=UTC))
        before_slot = datetime(2026, 8, 5, 12, 19, tzinfo=UTC)
        self.assertEqual(next_run(before_slot), datetime(2026, 8, 5, 12, 20, tzinfo=UTC))


if __name__ == "__main__":
    unittest.main()

