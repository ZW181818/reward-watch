import unittest

from app.ingestion.edmonton import (
    discover_edmonton_profile_urls,
    parse_edmonton_profile,
)


INDEX_HTML = """
<div id="mostWantedListing">
  <div class="mostWanted"><div class="info"><h2>
    <a href="/CrimeFiles/EdmontonsMostWanted/JordanExample">Jordan EXAMPLE</a>
  </h2></div></div>
</div>
"""


PROFILE_HTML = """
<html><head>
  <meta name="SCLastUpdatedDate" content="2026/07/03 14:30:00">
</head><body>
  <div id="mostWanted">
    <h1>Jordan EXAMPLE</h1>
    <div id="Image1"><a href="/-/media/example-main.png"><img></a></div>
    <div id="personInfo">
      <div id="age"><span class="FieldTitle">DOB/Age:</span> 35</div>
      <div id="height"><span class="FieldTitle">Height:</span> 6 ft.</div>
      <div id="weight"><span class="FieldTitle">Weight:</span> 180 lbs</div>
      <div id="description">Brown eyes, black hair, fictional test tattoo.</div>
    </div>
    <div id="content"><p>Wanted on a fictional test warrant.</p></div>
    <div id="images"><a href="/-/media/example-side.jpg"></a></div>
  </div>
  <span class="datePosted">Date Posted: 02-Jul-2026</span>
</body></html>
"""


class EdmontonIngestionTests(unittest.TestCase):
    def test_discovers_current_profile_urls(self):
        result = discover_edmonton_profile_urls(
            INDEX_HTML,
            "https://www.edmontonpolice.ca/CrimeFiles/EdmontonsMostWanted",
        )

        self.assertEqual(
            result,
            [
                "https://www.edmontonpolice.ca/CrimeFiles/EdmontonsMostWanted/"
                "JordanExample"
            ],
        )

    def test_maps_profile_fields_and_gallery(self):
        result = parse_edmonton_profile(
            PROFILE_HTML,
            "https://www.edmontonpolice.ca/CrimeFiles/EdmontonsMostWanted/"
            "JordanExample",
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["id"], "eps-jordanexample")
        self.assertEqual(result["agency"], "Edmonton Police Service")
        self.assertEqual(result["regions"], ["Alberta"])
        self.assertEqual(result["publishedDate"], "2026-07-02")
        self.assertEqual(result["sourceUpdatedDate"], "2026-07-03")
        self.assertEqual(result["age"], "35")
        self.assertEqual(result["height"], "6 ft.")
        self.assertEqual(result["eyes"], "Brown")
        self.assertEqual(result["hair"], "Black")
        self.assertEqual(len(result["imageUrls"]), 2)

    def test_excludes_profiles_without_image_or_narrative(self):
        imageless = PROFILE_HTML.replace(
            '<a href="/-/media/example-main.png"><img></a>', ""
        ).replace('<a href="/-/media/example-side.jpg"></a>', "")
        empty_content = PROFILE_HTML.replace(
            "<p>Wanted on a fictional test warrant.</p>", ""
        )

        self.assertIsNone(
            parse_edmonton_profile(imageless, "https://example.test/profile")
        )
        self.assertIsNone(
            parse_edmonton_profile(empty_content, "https://example.test/profile")
        )


if __name__ == "__main__":
    unittest.main()
