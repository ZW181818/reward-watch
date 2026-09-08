import unittest
from unittest.mock import patch

from app.map_data import build_case_map_item
from scripts.build_case_map_locations import (
    CA_GEONAMES_ADMIN_CODES,
    Place,
    build_map_locations,
    case_candidates,
)


class CaseMapLocationTests(unittest.TestCase):
    def test_postal_title_city_replaces_broad_state_center(self):
        reward_case = {
            "id": "uspis-example",
            "title": "San Bruno, CA: ROBBERY OF A POST OFFICE",
            "country": "US",
            "regions": ["California"],
            "locations": "California",
        }

        candidates = case_candidates(reward_case)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].city, "San Bruno")
        self.assertEqual(candidates[0].admin_code, "CA")
        self.assertEqual(candidates[0].location_type, "title_location")

    def test_city_and_broad_region_are_marked_with_different_precision(self):
        cases = [
            {
                "id": "city-case",
                "title": "City case",
                "country": "US",
                "regions": ["Texas"],
                "locations": "Austin, Texas",
            },
            {
                "id": "region-case",
                "title": "Region case",
                "country": "Canada",
                "regions": ["Nova Scotia"],
                "locations": "Nova Scotia",
            },
        ]
        places = {
            ("US", "TX", "austin"): Place("Austin", 30.26715, -97.74306, 950_000)
        }

        mapped, counts, unresolved = build_map_locations(cases, places)

        self.assertEqual(mapped["city-case"][0]["precision"], "city")
        self.assertFalse(mapped["city-case"][0]["approximate"])
        self.assertEqual(mapped["region-case"][0]["precision"], "region")
        self.assertTrue(mapped["region-case"][0]["approximate"])
        self.assertEqual(counts, {"city": 1, "region": 1})
        self.assertEqual(unresolved, [])

    def test_canadian_province_codes_are_translated_for_geonames(self):
        self.assertEqual(CA_GEONAMES_ADMIN_CODES["BC"], "02")
        self.assertEqual(CA_GEONAMES_ADMIN_CODES["ON"], "08")

    def test_malformed_location_text_is_not_mapped(self):
        reward_case = {
            "id": "bad-location",
            "title": "Bad location",
            "country": "Canada",
            "regions": ["British Columbia"],
            "locations": (
                "Fort Nelson Two counts of possession of a controlled substance "
                "contrary to section 5"
            ),
        }
        self.assertEqual(case_candidates(reward_case), [])

    @patch("app.map_data._load_map_data")
    def test_region_only_case_is_not_exposed_as_a_nearby_result(self, load_map_data):
        load_map_data.return_value = (
            "2026-09-08T00:00:00Z",
            {
                "region-case": [
                    {
                        "label": "Nova Scotia",
                        "latitude": 44.682,
                        "longitude": -63.7443,
                        "precision": "region",
                        "locationType": "broad_region",
                        "approximate": True,
                    }
                ]
            },
        )
        reward_case = {
            "id": "region-case",
            "title": "Region case",
            "agency": "Official Agency",
            "country": "Canada",
            "status": "Open",
            "summary": "Summary",
            "publishedDate": "2026-09-08",
            "lastVerified": "2026-09-08",
            "sourceUrl": "https://example.test/region-case",
        }

        self.assertIsNone(build_case_map_item(reward_case))


if __name__ == "__main__":
    unittest.main()
