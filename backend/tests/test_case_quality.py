import unittest

from app.case_quality import (
    build_data_quality_report,
    merge_cross_source_cases,
    normalize_reward_metadata,
    validate_data_quality,
)


def make_case(case_id: str, **overrides):
    reward_case = {
        "id": case_id,
        "title": "Example Person",
        "agency": "Example Agency",
        "country": "US",
        "regions": ["Federal"],
        "reward": 0,
        "rewardText": None,
        "status": "Open",
        "summary": "A sufficiently detailed official summary for this fictional test record.",
        "aliases": [],
        "publishedDate": "2026-08-01",
        "lastVerified": "2026-08-05",
        "sourceUpdatedDate": None,
        "sourceUrl": f"https://agency.test/{case_id}",
        "sourceTitle": f"Official source for {case_id}",
        "sourceAuthor": "Example Agency",
        "imageUrl": f"https://agency.test/{case_id}.jpg",
        "imageUrls": [f"https://agency.test/{case_id}.jpg"],
    }
    reward_case.update(overrides)
    return reward_case


class CaseQualityTests(unittest.TestCase):
    def test_normalizes_unpublished_reward_and_currency(self):
        cases = normalize_reward_metadata(
            [
                make_case("fbi-none"),
                make_case("opp-cad", country="Canada", reward=50_000),
            ]
        )

        self.assertIsNone(cases[0]["reward"])
        self.assertIsNone(cases[0]["rewardCurrency"])
        self.assertEqual(cases[1]["reward"], 50_000)
        self.assertEqual(cases[1]["rewardCurrency"], "CAD")

    def test_merges_matching_fbi_and_rewards_for_justice_records(self):
        cases = normalize_reward_metadata(
            [
                make_case(
                    "fbi-person",
                    agency="Federal Bureau of Investigation",
                    sourceAuthor="Federal Bureau of Investigation",
                    regions=["California"],
                    reward=5_000_000,
                    rewardText="Reward up to $5 million",
                    aliases=["Example Alias"],
                    height='6\'0"',
                ),
                make_case(
                    "rfj-person",
                    agency="U.S. Department of State",
                    sourceAuthor="U.S. Department of State - Rewards for Justice",
                    reward=10_000_000,
                    rewardText="Reward up to $10 million",
                ),
            ]
        )

        merged = merge_cross_source_cases(cases)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["id"], "rfj-person")
        self.assertEqual(merged[0]["reward"], 10_000_000)
        self.assertEqual(len(merged[0]["sourceRecords"]), 2)
        self.assertEqual(merged[0]["regions"], ["California", "Federal"])
        self.assertEqual(merged[0]["aliases"], ["Example Alias"])
        self.assertEqual(merged[0]["height"], '6\'0"')
        self.assertEqual(len(merged[0]["imageUrls"]), 2)

    def test_does_not_merge_same_source_records_with_repeated_titles(self):
        cases = normalize_reward_metadata(
            [make_case("fbi-first"), make_case("fbi-second")]
        )

        self.assertEqual(len(merge_cross_source_cases(cases)), 2)

    def test_rejects_scaled_reward_mismatch(self):
        cases = normalize_reward_metadata(
            [make_case("fbi-person", reward=5, rewardText="Reward up to $5 million")]
        )

        with self.assertRaisesRegex(ValueError, "does not match"):
            validate_data_quality(cases)

    def test_builds_auditable_report(self):
        cases = merge_cross_source_cases(
            normalize_reward_metadata(
                [
                    make_case("fbi-none"),
                    make_case("opp-cad", country="Canada", reward=50_000),
                ]
            )
        )
        report = build_data_quality_report(
            cases,
            generated_at="2026-08-05T00:00:00+00:00",
            source_statuses=[{"id": "test", "success": True}],
        )

        self.assertEqual(report["totalCases"], 2)
        self.assertEqual(report["rewards"]["published"], 1)
        self.assertEqual(report["rewards"]["notPublished"], 1)
        self.assertTrue(report["freshness"]["allSourcesFresh"])


if __name__ == "__main__":
    unittest.main()
