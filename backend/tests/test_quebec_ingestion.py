import unittest

from app.ingestion.quebec import (
    discover_active_profile_urls,
    parse_quebec_profile,
)


INDEX_HTML = """
<main>
  <a class="item__link" href="/en/fugitive/jordan-example/">
    <h2>Example, Jordan</h2><span>View file</span>
  </a>
  <a class="item__link" href="/en/fugitive/casey-resolved/">
    <strong>Arrêtée</strong><h2>Resolved, Casey</h2>
  </a>
</main>
"""


PROFILE_HTML = """
<html><head>
  <meta property="article:modified_time" content="2026-07-03T14:30:00-04:00">
</head><body><div class="file-content">
  <div class="file-gallery-wrapper">
    <a data-fancybox="fugitive-gallery" data-src="/uploads/jordan-main.jpg"></a>
    <a data-fancybox="fugitive-gallery" href="/uploads/jordan-side.jpg"></a>
  </div>
  <div class="file-base-infos">
    <h1>Jordan Example</h1>
    <p>Posting date: July 2, 2026</p>
    <div class="base-infos-wrapper">
      <div class="base-infos"><p>Date of birth:</p><p>1990-01-02</p></div>
      <div class="base-infos"><p>Gender:</p><p>male</p></div>
      <div class="base-infos"><p>Eyes:</p><p>brown</p></div>
      <div class="base-infos"><p>Height:</p><p>1.8 m</p></div>
      <div class="base-infos"><p>Weight:</p><p>80 kg</p></div>
      <div class="base-infos"><p>Hair:</p><p>black</p></div>
      <div class="base-infos"><p>Citizenship:</p><p>Canadian</p></div>
    </div>
  </div>
  <div class="file-synopsis">
    <div class="wysi"><p>This is a fictional parser fixture.</p></div>
    <div class="searched-for"><p>Wanted for:</p><p>Test offence</p></div>
    <div class="police-force"><p>Police service:</p><div><p>Example Police</p></div></div>
  </div>
</div></body></html>
"""


class QuebecIngestionTests(unittest.TestCase):
    def test_discovers_only_active_profiles(self):
        result = discover_active_profile_urls(
            INDEX_HTML, "https://www.fugitifsquebec.com/en/"
        )

        self.assertEqual(
            result,
            ["https://www.fugitifsquebec.com/en/fugitive/jordan-example/"],
        )

    def test_maps_rich_profile_and_all_gallery_images(self):
        result = parse_quebec_profile(
            PROFILE_HTML,
            "https://www.fugitifsquebec.com/en/fugitive/jordan-example/",
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["id"], "fq-jordan-example")
        self.assertEqual(result["country"], "Canada")
        self.assertEqual(result["regions"], ["Quebec"])
        self.assertEqual(result["agency"], "Example Police")
        self.assertEqual(result["publishedDate"], "2026-07-02")
        self.assertEqual(result["sourceUpdatedDate"], "2026-07-03")
        self.assertEqual(result["description"], "Test offence")
        self.assertEqual(result["dateOfBirth"], "1990-01-02")
        self.assertEqual(result["sex"], "Male")
        self.assertEqual(result["nationality"], "Canadian")
        self.assertEqual(len(result["imageUrls"]), 2)

    def test_excludes_resolved_or_imageless_profiles(self):
        resolved = PROFILE_HTML.replace(
            "<h1>Jordan Example</h1>",
            '<strong class="file-state">Arrested</strong><h1>Jordan Example</h1>',
        )
        imageless = PROFILE_HTML.replace(
            '<a data-fancybox="fugitive-gallery" data-src="/uploads/jordan-main.jpg"></a>',
            "",
        ).replace(
            '<a data-fancybox="fugitive-gallery" href="/uploads/jordan-side.jpg"></a>',
            "",
        )

        self.assertIsNone(parse_quebec_profile(resolved, "https://example.test/profile/"))
        self.assertIsNone(parse_quebec_profile(imageless, "https://example.test/profile/"))


if __name__ == "__main__":
    unittest.main()
