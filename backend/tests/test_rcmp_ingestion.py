import json
import unittest

from app.ingestion.rcmp import (
    discover_latest_wanted_release,
    parse_rcmp_wanted_release,
)


def make_news_index_html() -> str:
    records = [
        {
            "title": "UPDATE: Saskatchewan RCMP: Wanted Persons",
            "view_node": "https://rcmp.ca/en/saskatchewan/news/2026/08/update",
            "field_publish_date": "2026-08-02",
        },
        {
            "title": "Saskatchewan RCMP: Wanted Persons",
            "view_node": "https://rcmp.ca/en/saskatchewan/news/2026/07/current",
            "field_publish_date": "2026-07-23",
        },
        {
            "title": "Saskatchewan RCMP: Wanted Persons",
            "view_node": "https://rcmp.ca/en/saskatchewan/news/2026/06/previous",
            "field_publish_date": "2026-06-17",
        },
    ]
    settings = {
        "poweb": {"all_news": {"rest_export_all_news": json.dumps(records)}}
    }
    return (
        '<script type="application/json" '
        'data-drupal-selector="drupal-settings-json">'
        f"{json.dumps(settings)}"
        "</script>"
    )


RELEASE_HTML = """
<html>
  <head><meta name="dcterms.modified" content="2026-07-24"></head>
  <body>
    <section id="s1">
      <h3>Saskatchewan RCMP: Wanted Persons</h3>
      <p>2026-07-23</p>
      <p><b>1. Avery North</b></p>
      <p>Aliases: Avery Test, A. North</p>
      <p>Gender: female</p>
      <p>Age: 31</p>
      <p>Height: 5'8&quot;</p>
      <p>Weight: 150 lbs</p>
      <p>Hair: brown</p>
      <p>Eyes: green</p>
      <p>Scars/Tattoos:</p>
      <ul><li>Small fictional test mark</li></ul>
      <p><b>May be in these communities:</b></p>
      <p>Example, SK</p>
      <p><b>Offences</b>:</p>
      <p>Fictional warrant offence used only for parser testing</p>
      <h4>2. Morgan Lake</h4>
      <p>Aliases: nil</p>
      <p>Offences:</p>
      <p>Another fictional parser test offence</p>
      <h4>3. ARRESTED</h4>
    </section>
    <section id="s2">
      <a href="/sites/default/files/public/2026-07/avery.jpg"><img></a>
      <a href="/sites/default/files/public/2026-07/no-photo-available-en.png"><img></a>
    </section>
  </body>
</html>
"""


class RcmpIngestionTests(unittest.TestCase):
    def test_discovers_latest_current_release_and_ignores_updates(self):
        release = discover_latest_wanted_release(make_news_index_html())

        self.assertEqual(release["field_publish_date"], "2026-07-23")
        self.assertEqual(
            release["view_node"],
            "https://rcmp.ca/en/saskatchewan/news/2026/07/current",
        )

    def test_maps_rich_profile_and_excludes_no_photo_records(self):
        cases = parse_rcmp_wanted_release(
            RELEASE_HTML,
            source_url="https://rcmp.ca/en/saskatchewan/news/2026/07/current",
            published_date="2026-07-23",
        )

        self.assertEqual(len(cases), 1)
        reward_case = cases[0]
        self.assertEqual(reward_case["id"], "rcmp-sk-avery-north")
        self.assertEqual(reward_case["country"], "Canada")
        self.assertEqual(reward_case["regions"], ["Saskatchewan"])
        self.assertEqual(reward_case["aliases"], ["Avery Test", "A. North"])
        self.assertEqual(reward_case["age"], "31")
        self.assertEqual(reward_case["locations"], "Example, SK")
        self.assertEqual(
            reward_case["distinguishingFeatures"], "Small fictional test mark"
        )
        self.assertEqual(reward_case["sourceUpdatedDate"], "2026-07-24")
        self.assertEqual(
            reward_case["sourceTitle"], "Saskatchewan RCMP: Wanted Persons"
        )
        self.assertEqual(reward_case["sourceAuthor"], "Saskatchewan RCMP")
        self.assertTrue(reward_case["imageUrl"].endswith("/avery.jpg"))


if __name__ == "__main__":
    unittest.main()
