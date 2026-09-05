import unittest
from datetime import UTC, datetime

from scripts.update_cases import (
    CATCH_UP_REDUNDANCY,
    SOURCE_BATCHES,
    SOURCE_IDS,
    attach_source_refresh_history,
    deduplicate_cases,
    refresh_or_retain_source,
    refresh_source,
    source_ids_for_batch,
)


class UpdateCasesTests(unittest.TestCase):
    def test_retains_only_previous_source_data_when_source_fails(self):
        existing = [
            {"id": "opp-previous", "country": "Canada"},
            {"id": "rcmp-sk-current", "country": "Canada"},
        ]

        def fail_fetch():
            raise TimeoutError("test timeout")

        cases, status = refresh_source(
            country="Canada",
            existing_cases=existing,
            fetcher=fail_fetch,
            id_prefix="opp-",
            name="Test Canada source",
        )

        self.assertEqual(cases, [{"id": "opp-previous", "country": "Canada"}])
        self.assertFalse(status["success"])
        self.assertTrue(status["usedStaleData"])
        self.assertIn("TimeoutError", status["error"])

    def test_replaces_previous_source_data_after_success(self):
        existing = [{"id": "opp-previous", "country": "Canada"}]
        current = [{"id": "opp-current", "country": "Canada"}]

        cases, status = refresh_source(
            country="Canada",
            existing_cases=existing,
            fetcher=lambda: current,
            id_prefix="opp-",
            name="Test Canada source",
        )

        self.assertEqual(cases, current)
        self.assertTrue(status["success"])
        self.assertFalse(status["usedStaleData"])

    def test_allows_a_verified_source_to_remove_every_record(self):
        cases, status = refresh_source(
            country="China",
            existing_cases=[{"id": "cn-police-previous", "country": "China"}],
            fetcher=lambda: [],
            id_prefix="cn-police-",
            name="Test China police source",
            allow_empty=True,
        )

        self.assertEqual(cases, [])
        self.assertTrue(status["success"])
        self.assertFalse(status["usedStaleData"])

    def test_deduplicates_ids_but_keeps_shared_release_urls(self):
        cases = deduplicate_cases(
            [
                {"id": "first", "sourceUrl": "https://agency.test/first"},
                {"id": "first", "sourceUrl": "https://agency.test/duplicate-id"},
                {"id": "third", "sourceUrl": "https://agency.test/first"},
                {"id": "fourth", "sourceUrl": "https://agency.test/fourth"},
            ]
        )

        self.assertEqual([item["id"] for item in cases], ["first", "third", "fourth"])

    def test_primary_batches_cover_every_source_once(self):
        covered = [source_id for batch in SOURCE_BATCHES.values() for source_id in batch]

        self.assertCountEqual(covered, SOURCE_IDS)
        self.assertEqual(len(covered), len(set(covered)))

    def test_catch_up_retries_missing_sources_and_redundant_sources(self):
        now = datetime(2026, 9, 5, 21, 37, tzinfo=UTC)
        statuses = [
            {
                "id": source_id,
                "success": True,
                "lastSuccessAt": "2026-09-05T10:00:00+00:00",
            }
            for source_id in SOURCE_IDS
        ]
        next(item for item in statuses if item["id"] == "uspis")["lastSuccessAt"] = (
            "2026-09-04T10:00:00+00:00"
        )

        selected = source_ids_for_batch(
            "catch-up",
            {"updatedAt": "2026-09-05T18:00:00+00:00", "sources": statuses},
            now=now,
        )

        self.assertEqual(selected, {"uspis", *CATCH_UP_REDUNDANCY})

    def test_unselected_source_is_retained_without_calling_fetcher(self):
        existing = [{"id": "opp-previous", "country": "Canada"}]

        def unexpected_fetch():
            raise AssertionError("unselected source must not be fetched")

        cases, status = refresh_or_retain_source(
            country="Canada",
            existing_cases=existing,
            fetcher=unexpected_fetch,
            id_prefix="opp-",
            name="Test Canada source",
            selected_source_ids={"fbi"},
            previous_status={"success": True, "usedStaleData": False, "error": None},
        )

        self.assertEqual(cases, existing)
        self.assertTrue(status["success"])

    def test_refresh_history_tracks_attempts_without_resetting_other_sources(self):
        statuses = [
            {"id": "fbi", "success": True},
            {"id": "opp", "success": True},
        ]
        previous = {
            "updatedAt": "2026-09-04T10:00:00+00:00",
            "sources": [
                {"id": "fbi", "success": True},
                {"id": "opp", "success": True},
            ],
        }

        attach_source_refresh_history(
            statuses,
            previous,
            selected_source_ids={"fbi"},
            updated_at="2026-09-05T00:37:00+00:00",
        )

        self.assertTrue(statuses[0]["attemptedThisRun"])
        self.assertEqual(statuses[0]["lastSuccessAt"], "2026-09-05T00:37:00+00:00")
        self.assertFalse(statuses[1]["attemptedThisRun"])
        self.assertEqual(statuses[1]["lastSuccessAt"], "2026-09-04T10:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
