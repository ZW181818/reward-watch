import unittest

from app.ingestion.cfseu import parse_cfseu_posts


def make_post(post_id: int, date: str, title: str, content: str) -> dict:
    return {
        "id": post_id,
        "date": f"{date}T10:00:00",
        "modified": f"{date}T11:00:00",
        "link": f"https://cfseu.bc.ca/test-{post_id}/",
        "title": {"rendered": title},
        "content": {"rendered": content},
        "_embedded": {
            "wp:featuredmedia": [
                {"source_url": "https://cfseu.bc.ca/uploads/test-wanted-poster.jpg"}
            ]
        },
    }


class CfseuIngestionTests(unittest.TestCase):
    def test_maps_wanted_profiles_and_applies_later_closure(self):
        wanted_post = make_post(
            200,
            "2026-06-01",
            "Two people wanted in connection to a CFSEU-BC investigation",
            """
            <p>Avery North, a 33-year-old female from Example, British Columbia,</p>
            <p>Morgan Lake, a 36-year-old male from Sample, British Columbia.</p>
            <p>Arrest warrants have been issued for these individuals. Police are
            seeking public assistance to locate them in this fictional parser test.</p>
            """,
        )
        closure_post = make_post(
            201,
            "2026-06-05",
            "Morgan Lake arrested",
            "<p>Morgan Lake has been arrested.</p>",
        )

        cases = parse_cfseu_posts([closure_post, wanted_post])

        self.assertEqual(len(cases), 1)
        reward_case = cases[0]
        self.assertEqual(reward_case["title"], "Avery North")
        self.assertEqual(reward_case["age"], "33")
        self.assertEqual(reward_case["sex"], "Female")
        self.assertEqual(reward_case["regions"], ["British Columbia"])
        self.assertEqual(reward_case["sourceAuthor"], "CFSEU-BC")
        self.assertTrue(reward_case["imageUrl"].endswith("test-wanted-poster.jpg"))


if __name__ == "__main__":
    unittest.main()
