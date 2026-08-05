import unittest
from unittest.mock import patch

from app.main import get_case, list_cases
from app.models import RewardCase


def make_case(case_id: str, reward: int | None) -> RewardCase:
    return RewardCase.model_validate(
        {
            "id": case_id,
            "title": f"Case {case_id}",
            "agency": "Official Agency",
            "country": "US",
            "regions": ["Federal"],
            "reward": reward,
            "rewardCurrency": "USD" if reward is not None else None,
            "status": "Open",
            "summary": "A sufficiently detailed official summary for an API test case.",
            "publishedDate": "2026-08-01",
            "lastVerified": "2026-08-05",
            "sourceUrl": f"https://agency.test/{case_id}",
            "sourceAuthor": "Official Agency",
            "imageUrl": f"https://agency.test/{case_id}.jpg",
            "imageUrls": [f"https://agency.test/{case_id}.jpg"],
        }
    )


class ApiTests(unittest.TestCase):
    @patch("app.main.load_cases")
    def test_reward_sort_keeps_unpublished_amounts_last(self, load_cases):
        load_cases.return_value = [make_case("unknown", None), make_case("known", 500)]

        ascending = list_cases(q=None, country=None, region=None, sort="reward_asc")
        descending = list_cases(q=None, country=None, region=None, sort="reward_desc")

        self.assertEqual([item.id for item in ascending.items], ["known", "unknown"])
        self.assertEqual([item.id for item in descending.items], ["known", "unknown"])

    @patch("app.main.load_cases")
    def test_case_list_is_paginated(self, load_cases):
        load_cases.return_value = [make_case(str(index), index) for index in range(25)]

        result = list_cases(page=2, page_size=10)

        self.assertEqual(result.total, 25)
        self.assertEqual(result.totalPages, 3)
        self.assertEqual(result.page, 2)
        self.assertEqual(len(result.items), 10)

    @patch("app.main.load_cases")
    def test_filters_and_facets_are_computed_server_side(self, load_cases):
        open_case = make_case("open", 500)
        closed_case = RewardCase.model_validate(
            {
                **make_case("closed", 250).model_dump(),
                "status": "Closed",
                "regions": ["Texas"],
                "sourceAuthor": "Texas DPS",
            }
        )
        load_cases.return_value = [open_case, closed_case]

        result = list_cases(status="Closed", source="Texas DPS")

        self.assertEqual([item.id for item in result.items], ["closed"])
        self.assertEqual({option.value for option in result.facets.statuses}, {"Closed", "Open"})
        self.assertIn("Texas DPS", {option.value for option in result.facets.sources})

    @patch("app.main.load_cases")
    def test_legacy_source_id_resolves_to_merged_case(self, load_cases):
        reward_case = RewardCase.model_validate(
            {
                **make_case("rfj-canonical", 5_000_000).model_dump(),
                "sourceRecords": [
                    {
                        "caseId": "fbi-legacy",
                        "url": "https://fbi.test/legacy",
                        "author": "Federal Bureau of Investigation",
                        "reward": 5_000_000,
                        "rewardCurrency": "USD",
                    }
                ],
            }
        )
        load_cases.return_value = [reward_case]

        self.assertEqual(get_case("fbi-legacy").id, "rfj-canonical")


if __name__ == "__main__":
    unittest.main()
