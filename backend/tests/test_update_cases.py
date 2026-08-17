import unittest

from scripts.update_cases import deduplicate_cases, refresh_source


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


if __name__ == "__main__":
    unittest.main()
