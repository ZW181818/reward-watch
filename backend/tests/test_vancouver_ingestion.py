import unittest

from app.ingestion.vancouver import parse_vancouver_posts


def make_post(post_id: int, date: str, title: str, content: str) -> dict:
    return {
        "id": post_id,
        "date": f"{date}T10:00:00",
        "modified": f"{date}T11:00:00",
        "link": f"https://vpd.ca/news/{post_id}/",
        "title": {"rendered": title},
        "content": {"rendered": content},
    }


class VancouverIngestionTests(unittest.TestCase):
    def test_maps_gallery_profiles_and_excludes_subject_with_later_arrest(self):
        wanted_post = make_post(
            100,
            "2026-07-01",
            "VPD searches for two people wanted Canada-wide",
            """
            <div class="gallery-item">
              <a href="https://vpd.ca/uploads/avery-north.jpg"><img src="avery-small.jpg"></a>
              <div class="gallery-caption">Avery North</div>
            </div>
            <div class="gallery-item">
              <a href="https://vpd.ca/uploads/morgan-lake.jpg"><img src="morgan-small.jpg"></a>
              <div class="gallery-caption">Morgan Lake</div>
            </div>
            <p>Police are requesting help to locate 31-year-old Avery North and
            40-year-old Morgan Lake, both wanted Canada-wide in a fictional test.</p>
            <p>Avery North is 5'7", 165 pounds, and has brown hair.</p>
            """,
        )
        closure_post = make_post(
            101,
            "2026-07-03",
            "Update: Morgan Lake arrested",
            "<p>Morgan Lake has been arrested and is back in custody.</p>",
        )

        cases = parse_vancouver_posts([closure_post, wanted_post])

        self.assertEqual(len(cases), 1)
        reward_case = cases[0]
        self.assertEqual(reward_case["title"], "Avery North")
        self.assertEqual(reward_case["regions"], ["British Columbia"])
        self.assertEqual(reward_case["age"], "31")
        self.assertEqual(reward_case["sourceAuthor"], "Vancouver Police Department")
        self.assertTrue(reward_case["imageUrl"].endswith("avery-north.jpg"))


if __name__ == "__main__":
    unittest.main()
