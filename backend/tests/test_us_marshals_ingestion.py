import unittest

from app.ingestion.us_marshals import (
    discover_page_count,
    discover_profile_urls,
    parse_us_marshals_profile,
)


INDEX_HTML = """
<main>
  <a href="/what-we-do/fugitive/local/example-person">Learn more</a>
  <a href="?page=0">1</a><a href="?page=3">Last</a>
</main>
"""

PROFILE_HTML = """
<html>
  <head>
    <meta property="article:published_time" content="2026-05-01">
    <meta property="article:modified_time" content="2026-05-03">
  </head>
  <body><main>
    <h1>Example Person</h1>
    <div class="slick--field-fugitive-image-asset-file">
      <img data-src="/sites/default/files/example.webp" alt="Example Person">
      <img data-src="/sites/default/files/example-side.webp" alt="Example Person side">
    </div>
    <div class="fugitivedetails-block">
      <h2 class="fugitivedetails-label">Wanted For</h2>
      <div class="fugitivedetails-content">Fictional parser offence</div>
    </div>
    <div class="fugitivedetails-block">
      <h2 class="fugitivedetails-label">Aliases</h2>
      <div class="fugitivedetails-content">Example One, Example Two</div>
    </div>
    <div class="fugitivedetails-block">
      <h2 class="fugitivedetails-label">Reward</h2>
      <div class="fugitivedetails-content">Up to $5,000</div>
    </div>
    <div class="fugitivedetails-block">
      <h2 class="fugitivedetails-label">Wanted In</h2>
      <div class="fugitivedetails-content">Richmond, VA</div>
    </div>
    <div class="fugitivedetails-block">
      <h2 class="fugitivedetails-label">Case outline</h2>
      <div class="fugitivedetails-content">
        The U.S. Marshals Service requests information about this fictional parser case.
      </div>
    </div>
  </main></body>
</html>
"""


class UsMarshalsIngestionTests(unittest.TestCase):
    def test_discovers_paginated_profile_catalog(self):
        self.assertEqual(discover_page_count(INDEX_HTML), 4)
        self.assertEqual(
            discover_profile_urls(INDEX_HTML),
            [
                "https://prod.usmarshals.gov/what-we-do/fugitive/local/example-person"
            ],
        )

    def test_maps_reward_profile_and_gallery(self):
        reward_case = parse_us_marshals_profile(
            PROFILE_HTML,
            "https://prod.usmarshals.gov/what-we-do/fugitive/local/example-person",
        )

        self.assertIsNotNone(reward_case)
        assert reward_case is not None
        self.assertEqual(reward_case["reward"], 5_000)
        self.assertEqual(reward_case["regions"], ["Virginia"])
        self.assertEqual(reward_case["aliases"], ["Example One", "Example Two"])
        self.assertEqual(reward_case["status"], "Open")
        self.assertEqual(len(reward_case["imageUrls"]), 2)
        self.assertTrue(reward_case["sourceUrl"].startswith("https://www.usmarshals.gov/"))

    def test_marks_explicit_apprehension_update_closed(self):
        closed_html = PROFILE_HTML.replace(
            "The U.S. Marshals Service requests information",
            "UPDATE: Example Person was apprehended. The agency requests information",
        )

        reward_case = parse_us_marshals_profile(
            closed_html,
            "https://prod.usmarshals.gov/what-we-do/fugitive/local/example-person",
        )

        assert reward_case is not None
        self.assertEqual(reward_case["status"], "Closed")


if __name__ == "__main__":
    unittest.main()
