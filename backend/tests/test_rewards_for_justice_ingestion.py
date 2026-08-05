import unittest

from app.ingestion.rewards_for_justice import normalize_rewards_for_justice_post


class RewardsForJusticeIngestionTests(unittest.TestCase):
    def test_maps_only_explicit_cash_reward_with_official_image(self):
        post = {
            "id": 42,
            "date_gmt": "2026-07-01T12:00:00",
            "modified_gmt": "2026-07-02T12:00:00",
            "link": "https://rewardsforjustice.net/rewards/example-notice/",
            "title": {"rendered": "Example Official Notice"},
            "content": {
                "rendered": (
                    "<p>Rewards for Justice is offering a reward of up to "
                    "$10 million for information about a fictional test case.</p>"
                    "<p>The agency requests information through official channels.</p>"
                )
            },
            "_embedded": {
                "wp:featuredmedia": [
                    {"source_url": "https://rewardsforjustice.net/example.jpg"}
                ],
                "wp:term": [
                    [
                        {
                            "taxonomy": "crime-category",
                            "name": "Cyber",
                        }
                    ],
                    [
                        {
                            "taxonomy": "location-country",
                            "name": "Exampleland",
                        }
                    ],
                ],
            },
        }

        reward_case = normalize_rewards_for_justice_post(post)

        self.assertIsNotNone(reward_case)
        assert reward_case is not None
        self.assertEqual(reward_case["id"], "rfj-42")
        self.assertEqual(reward_case["reward"], 10_000_000)
        self.assertEqual(reward_case["regions"], ["Federal"])
        self.assertEqual(reward_case["caseType"], "Cyber")
        self.assertEqual(reward_case["locations"], "Exampleland")
        self.assertEqual(reward_case["imageUrls"], ["https://rewardsforjustice.net/example.jpg"])

    def test_excludes_profile_without_explicit_reward(self):
        post = {
            "id": 43,
            "link": "https://rewardsforjustice.net/rewards/background-profile/",
            "title": {"rendered": "Background Profile"},
            "content": {"rendered": "<p>Background information only.</p>"},
            "_embedded": {
                "wp:featuredmedia": [
                    {"source_url": "https://rewardsforjustice.net/background.jpg"}
                ]
            },
        }

        self.assertIsNone(normalize_rewards_for_justice_post(post))

    def test_excludes_reviewed_broken_source_media(self):
        source_url = "https://rewardsforjustice.net/rewards/example-notice/"
        post = {
            "id": 44,
            "link": source_url,
            "title": {"rendered": "Reviewed Broken Media"},
            "content": {
                "rendered": "<p>A reward of up to $1 million is offered for information.</p>"
            },
            "_embedded": {
                "wp:featuredmedia": [
                    {"source_url": "https://rewardsforjustice.net/broken.jpg"}
                ]
            },
        }

        self.assertIsNone(
            normalize_rewards_for_justice_post(
                post,
                excluded_source_urls={source_url},
            )
        )


if __name__ == "__main__":
    unittest.main()
