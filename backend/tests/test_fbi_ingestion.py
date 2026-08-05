import unittest
from unittest.mock import patch

from app.ingestion.fbi import fetch_fbi_cases, normalize_fbi_item


def make_item(**overrides):
    item = {
        "uid": "test-id",
        "title": "TEST OFFICIAL NOTICE",
        "url": "https://www.fbi.gov/wanted/fugitives/test-official-notice",
        "status": "na",
        "description": "Federal charge description",
        "caution": "<p>This official notice contains enough verified narrative context for display.</p>",
        "publication": "2026-07-20T10:00:00",
        "modified": "2026-07-21T10:00:00+00:00",
        "reward_text": "The FBI is offering a reward of up to $25,000.",
        "aliases": ["Test Alias"],
        "subjects": ["Additional Violent Crimes"],
        "dates_of_birth_used": ["January 1, 1990"],
        "place_of_birth": "Test City",
        "sex": "male",
        "race": "white",
        "nationality": "American",
        "hair": "brown",
        "eyes": "blue",
        "height_min": 72,
        "height_max": 72,
        "weight_min": 200,
        "weight_max": 200,
        "field_offices": ["losangeles"],
        "images": [{"original": "https://www.fbi.gov/example/image.jpg"}],
    }
    item.update(overrides)
    return item


class NormalizeFbiItemTests(unittest.TestCase):
    @patch("app.ingestion.fbi._fetch_page")
    def test_fetches_every_reported_page_when_no_limit_is_set(self, fetch_page):
        fetch_page.side_effect = [
            ([make_item(uid="first")], 51),
            ([make_item(uid="second")], 51),
        ]

        cases = fetch_fbi_cases()

        self.assertEqual([item["id"] for item in cases], ["fbi-first", "fbi-second"])
        self.assertEqual(fetch_page.call_count, 2)

    @patch("app.ingestion.fbi._fetch_page")
    def test_stops_when_publishable_limit_is_reached(self, fetch_page):
        fetch_page.return_value = (
            [make_item(uid="first"), make_item(uid="second")],
            100,
        )

        cases = fetch_fbi_cases(limit=1)

        self.assertEqual([item["id"] for item in cases], ["fbi-first"])
        self.assertEqual(fetch_page.call_count, 1)

    def test_excludes_resolved_cases(self):
        self.assertIsNone(normalize_fbi_item(make_item(status="captured")))

    def test_excludes_records_without_images(self):
        self.assertIsNone(normalize_fbi_item(make_item(images=[])))

    def test_excludes_reviewed_broken_sources(self):
        source_url = "https://www.fbi.gov/wanted/fugitives/test-official-notice"

        self.assertIsNone(
            normalize_fbi_item(make_item(url=source_url), excluded_source_urls={source_url})
        )

    def test_maps_rich_person_information(self):
        result = normalize_fbi_item(make_item())

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["status"], "Open")
        self.assertEqual(result["caseType"], "Additional Violent Crimes")
        self.assertEqual(result["aliases"], ["Test Alias"])
        self.assertEqual(result["height"], "6'0\"")
        self.assertEqual(result["weight"], "200 pounds")
        self.assertEqual(result["fieldOffice"], "Los Angeles")
        self.assertEqual(result["regions"], ["California"])
        self.assertEqual(result["sourceAuthor"], "Federal Bureau of Investigation")
        self.assertEqual(result["sourceTitle"], "FBI Wanted: TEST OFFICIAL NOTICE")
        self.assertEqual(result["reward"], 25000)
        self.assertIn("verified narrative context", result["summary"])

    def test_expands_reward_unit_words(self):
        result = normalize_fbi_item(
            make_item(reward_text="The FBI offers a reward of up to $5 million.")
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["reward"], 5_000_000)

    def test_derives_region_from_title_when_field_office_is_missing(self):
        result = normalize_fbi_item(
            make_item(title="FICTIONAL NOTICE - CHICAGO, ILLINOIS", field_offices=[])
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["regions"], ["Illinois"])

    def test_classifies_seeking_information_urls(self):
        result = normalize_fbi_item(
            make_item(url="https://www.fbi.gov/wanted/seeking-info/test-notice")
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["status"], "Information Requested")
        self.assertEqual(result["caseType"], "Seeking Information")


if __name__ == "__main__":
    unittest.main()
