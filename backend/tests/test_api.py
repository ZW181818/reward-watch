import asyncio
import unittest
from unittest.mock import patch

from fastapi import Request, Response

from app.main import cache_public_reads, get_case, get_nearby_case_index, list_cases
from app.models import CaseMapItem, CaseMapLocation, RewardCase


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
    def test_public_reads_are_browser_cacheable(self):
        request = Request(
            {
                "type": "http",
                "http_version": "1.1",
                "method": "GET",
                "scheme": "https",
                "path": "/cases",
                "raw_path": b"/cases",
                "query_string": b"",
                "headers": [],
                "client": ("127.0.0.1", 1234),
                "server": ("testserver", 443),
            }
        )

        async def call_next(_request):
            return Response(status_code=200)

        response = asyncio.run(cache_public_reads(request, call_next))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["cache-control"],
            "public, max-age=60, stale-while-revalidate=300",
        )

    def test_nearby_index_uses_public_browser_cache(self):
        request = Request(
            {
                "type": "http",
                "http_version": "1.1",
                "method": "GET",
                "scheme": "https",
                "path": "/cases/nearby-index",
                "raw_path": b"/cases/nearby-index",
                "query_string": b"",
                "headers": [],
                "client": ("127.0.0.1", 1234),
                "server": ("testserver", 443),
            }
        )

        async def call_next(_request):
            return Response(status_code=200)

        response = asyncio.run(cache_public_reads(request, call_next))
        self.assertEqual(
            response.headers["cache-control"],
            "public, max-age=60, stale-while-revalidate=300",
        )

    @patch("app.main.get_database_url", return_value=None)
    @patch("app.main.load_cases")
    @patch("app.main.build_case_map_items")
    def test_nearby_index_returns_compact_map_items(
        self, build_case_map_items, load_cases, _get_database_url
    ):
        map_item = CaseMapItem(
            id="mapped",
            title="Mapped case",
            agency="Official Agency",
            country="US",
            reward=500,
            rewardCurrency="USD",
            status="Open",
            locations=[
                CaseMapLocation(
                    label="Austin, Texas",
                    latitude=30.26715,
                    longitude=-97.74306,
                    precision="city",
                    locationType="official_location",
                )
            ],
        )
        load_cases.return_value = [make_case("mapped", 500)]
        build_case_map_items.return_value = [map_item]

        response = get_nearby_case_index()

        self.assertEqual(response.total, 1)
        self.assertEqual(response.items[0].id, "mapped")
        self.assertEqual(response.items[0].locations[0].precision, "city")

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
