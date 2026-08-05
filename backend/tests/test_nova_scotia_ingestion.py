import unittest

from app.ingestion.nova_scotia import (
    discover_nova_scotia_case_urls,
    parse_nova_scotia_reward_case,
)


INDEX_HTML = """
<div id="main">
  <a href="case_detail_example.asp">Example case</a>
  <a href="case_detail_second.asp">Second case</a>
</div>
"""

CASE_HTML = """
<div id="main" role="main">
  <h1>Rewards for Major Unsolved Crimes</h1>
  <h2>Example Person</h2>
  <table><tr>
    <td><img src="images/example.jpg"><img src="images/example-two.jpg"></td>
    <td>
      <p><strong>Homicide</strong></p>
      <p>The Government of the Province of Nova Scotia is offering a reward in the
      amount of up to $150,000 for information leading to an arrest and conviction.</p>
      <p>On May 1, 2026, police began this fictional parser investigation.</p>
      <p>Police believe someone has information about this case.</p>
      <p>Any person with information should call the official reward program.</p>
      <p>The reward is payable in Canadian funds.</p>
    </td>
  </tr></table>
</div>
"""


class NovaScotiaIngestionTests(unittest.TestCase):
    def test_discovers_case_detail_links(self):
        self.assertEqual(
            discover_nova_scotia_case_urls(INDEX_HTML),
            [
                "https://novascotia.ca/just/public_safety/rewards/case_detail_example.asp",
                "https://novascotia.ca/just/public_safety/rewards/case_detail_second.asp",
            ],
        )

    def test_maps_government_reward_case_with_gallery(self):
        reward_case = parse_nova_scotia_reward_case(
            CASE_HTML,
            source_url=(
                "https://novascotia.ca/just/public_safety/rewards/"
                "case_detail_example.asp"
            ),
            last_modified="Mon, 4 May 2026 14:49:03 GMT",
        )

        self.assertIsNotNone(reward_case)
        assert reward_case is not None
        self.assertEqual(reward_case["reward"], 150_000)
        self.assertEqual(reward_case["regions"], ["Nova Scotia"])
        self.assertEqual(reward_case["caseType"], "Homicide")
        self.assertEqual(reward_case["publishedDate"], "2026-05-04")
        self.assertEqual(len(reward_case["imageUrls"]), 2)

    def test_excludes_case_without_an_image(self):
        self.assertIsNone(
            parse_nova_scotia_reward_case(
                CASE_HTML.replace('<img src="images/example.jpg"><img src="images/example-two.jpg">', ""),
                source_url=(
                    "https://novascotia.ca/just/public_safety/rewards/"
                    "case_detail_example.asp"
                ),
            )
        )

    def test_legacy_query_links_receive_distinct_ids(self):
        first = parse_nova_scotia_reward_case(
            CASE_HTML,
            source_url=(
                "https://novascotia.ca/just/public_safety/rewards/"
                "case_detail.asp?cid=1"
            ),
        )
        second = parse_nova_scotia_reward_case(
            CASE_HTML,
            source_url=(
                "https://novascotia.ca/just/public_safety/rewards/"
                "case_detail.asp?cid=2"
            ),
        )

        assert first is not None and second is not None
        self.assertNotEqual(first["id"], second["id"])


if __name__ == "__main__":
    unittest.main()
