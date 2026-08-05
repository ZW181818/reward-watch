import json
import unittest

from app.ingestion.bc_rcmp import (
    discover_bc_wanted_releases,
    parse_bc_wanted_release,
)


def make_news_index_html() -> str:
    records = [
        {
            "title": "Wanted: Avery North",
            "view_node": "https://rcmp.ca/en/bc/example/news/2026/07/1001",
            "field_publish_date": "2026-07-28",
            "field_division_or_detachment": "Example RCMP",
            "field_location": "Example",
        },
        {
            "title": "Wanted person located",
            "view_node": "https://rcmp.ca/en/bc/example/news/2026/07/1002",
            "field_publish_date": "2026-07-29",
        },
        {
            "title": "Search warrant execution yields evidence",
            "view_node": "https://rcmp.ca/en/bc/example/news/2026/07/1003",
            "field_publish_date": "2026-07-30",
        },
    ]
    settings = {"poweb": {"all_news": {"test_feed": json.dumps(records)}}}
    return (
        '<script type="application/json" '
        'data-drupal-selector="drupal-settings-json">'
        f"{json.dumps(settings)}"
        "</script>"
    )


ACTIVE_RELEASE_HTML = """
<html>
  <head><meta name="dcterms.modified" content="2026-07-29"></head>
  <body>
    <h1>Wanted: Avery North</h1>
    <section id="s1">
      <p>Example RCMP is featuring 27-year-old Avery North for Wanted Wednesday.</p>
      <p>Avery North is wanted on an active warrant for a fictional parser offence.</p>
      <p>Avery North is described as:</p>
      <ul>
        <li>White female</li><li>5'6&quot;</li><li>130 lbs</li>
        <li>Blonde hair</li><li>Brown eyes</li><li>Small test tattoo</li>
      </ul>
      <p>If you have information about Avery North's whereabouts, contact Example RCMP.</p>
      <img src="/sites/default/files/public/avery-north.jpg" alt="Photo of Avery North">
    </section>
  </body>
</html>
"""


class BcRcmpIngestionTests(unittest.TestCase):
    def test_discovers_only_explicit_active_wanted_releases(self):
        records = discover_bc_wanted_releases(make_news_index_html())

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["title"], "Wanted: Avery North")
        self.assertEqual(records[0]["field_location"], "Example")

    def test_maps_bc_profile_with_source_image_and_physical_details(self):
        reward_case = parse_bc_wanted_release(
            ACTIVE_RELEASE_HTML,
            source_url="https://rcmp.ca/en/bc/example/news/2026/07/1001",
            published_date="2026-07-28",
            source_author="Example RCMP",
            source_location="Example",
        )

        self.assertIsNotNone(reward_case)
        assert reward_case is not None
        self.assertEqual(reward_case["title"], "Avery North")
        self.assertEqual(reward_case["regions"], ["British Columbia"])
        self.assertEqual(reward_case["age"], "27")
        self.assertEqual(reward_case["sex"], "Female")
        self.assertEqual(reward_case["height"], "5'6\"")
        self.assertEqual(reward_case["weight"], "130 lbs")
        self.assertEqual(reward_case["sourceAuthor"], "Example RCMP")
        self.assertTrue(reward_case["imageUrl"].endswith("avery-north.jpg"))

    def test_excludes_release_after_subject_is_located(self):
        closed_html = ACTIVE_RELEASE_HTML.replace(
            "If you have information about Avery North's whereabouts",
            "Update: Avery North has been located. If you have information about Avery North's whereabouts",
        )

        reward_case = parse_bc_wanted_release(
            closed_html,
            source_url="https://rcmp.ca/en/bc/example/news/2026/07/1001",
        )

        self.assertIsNone(reward_case)


if __name__ == "__main__":
    unittest.main()
