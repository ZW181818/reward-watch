import unittest

from app.ingestion.uspis import normalize_uspis_item, parse_catalog_config


INDEX_HTML = """
<html><body>
  <select name="location">
    <option value="0">Location</option>
    <option value="national">National</option>
    <option value="CA">California</option>
  </select>
  <script id="uspis-news-js-extra">
    var news_ajax = {"ajaxurl":"https://agency.test/ajax","nonce":"abc123"};
  </script>
</body></html>
"""

DETAIL_HTML = """
<html><head>
  <title>Los Angeles, CA: ROBBERY OF A UNITED STATES POST OFFICE – United States Postal Inspection Service</title>
</head><body><article class="wanted">
  <header>
    <h1>Los Angeles, CA: ROBBERY OF A UNITED STATES POST OFFICE</h1>
    <time datetime="06/18/2025T5:53:50">06.18.2025</time>
    <span class="post-locale">California</span>
  </header>
  <section class="article">
    <div class="photos">
      <img src="https://agency.test/primary.jpg">
      <img src="/secondary.jpg">
    </div>
    <div class="details">
      <h2>Reward up to $100,000</h2>
      <span>The agency requests information about this fictional postal robbery.</span>
      <span>The official reward is offered for information leading to an arrest.</span>
    </div>
  </section>
</article></body></html>
"""

ITEM = {
    "ID": 123,
    "link": "https://agency.test/news/wanted/example",
    "image": "https://agency.test/catalog.jpg",
    "date": "06.17.2025",
    "title": "Los Angeles, CA: ROBBERY OF A POST OFFICE",
    "body": "The agency offers a reward of up to $100,000 for information.",
    "location": {"value": "CA", "label": "California"},
}


class UspisIngestionTests(unittest.TestCase):
    def test_reads_ajax_configuration_and_locations(self):
        ajax_url, nonce, locations = parse_catalog_config(INDEX_HTML)

        self.assertEqual(ajax_url, "https://agency.test/ajax")
        self.assertEqual(nonce, "abc123")
        self.assertEqual(locations, ["national", "CA"])

    def test_maps_reward_notice_with_region_and_gallery(self):
        reward_case = normalize_uspis_item(ITEM, DETAIL_HTML)

        self.assertIsNotNone(reward_case)
        assert reward_case is not None
        self.assertEqual(reward_case["id"], "uspis-123")
        self.assertEqual(
            reward_case["title"],
            "Los Angeles, CA: ROBBERY OF A UNITED STATES POST OFFICE",
        )
        self.assertEqual(reward_case["reward"], 100_000)
        self.assertEqual(reward_case["regions"], ["California"])
        self.assertEqual(
            reward_case["caseType"],
            "Robbery Of A United States Post Office",
        )
        self.assertEqual(reward_case["status"], "Information Requested")
        self.assertEqual(len(reward_case["imageUrls"]), 3)
        self.assertEqual(reward_case["publishedDate"], "2025-06-17")
        self.assertEqual(reward_case["sourceUpdatedDate"], "2025-06-18")

    def test_skips_records_without_cash_reward(self):
        item = {**ITEM, "body": "The agency requests information."}
        detail = DETAIL_HTML.replace("Reward up to $100,000", "Information requested")

        self.assertIsNone(normalize_uspis_item(item, detail))

    def test_skips_explicitly_closed_records(self):
        detail = DETAIL_HTML.replace(
            "The agency requests information",
            "The suspect has been apprehended. The agency requests information",
        )

        self.assertIsNone(normalize_uspis_item(ITEM, detail))

    def test_skips_record_whose_official_title_says_subject_was_arrested(self):
        detail = DETAIL_HTML.replace(
            "Los Angeles, CA: ROBBERY OF A UNITED STATES POST OFFICE",
            "Fugitive Example Person was arrested on June 1, 2025",
        )

        self.assertIsNone(normalize_uspis_item(ITEM, detail))

    def test_skips_record_with_only_generic_placeholder_image(self):
        detail = DETAIL_HTML.replace(
            "https://agency.test/primary.jpg",
            "https://agency.test/NO_IMAGE_WantedPoster.png",
        ).replace(
            "/secondary.jpg",
            "https://agency.test/placeholder.jpg",
        )
        item = {
            **ITEM,
            "image": "https://agency.test/NO_IMAGE_WantedPoster-1.png",
        }

        self.assertIsNone(normalize_uspis_item(item, detail))


if __name__ == "__main__":
    unittest.main()
