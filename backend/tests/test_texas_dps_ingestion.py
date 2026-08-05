import tempfile
import unittest
from pathlib import Path

from app.ingestion.texas_dps import discover_detail_urls, parse_texas_dps_detail


TINY_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "/w8AAusB9Y9Z4QAAAABJRU5ErkJggg=="
)
INDEX_HTML = """
<html><body>
  <a href="/Texas10MostWanted/MostWanted/fugitiveDetails?id=1900">Active</a>
  <a href="/Texas10MostWanted/MostWanted/fugitiveDetails?id=1900">Duplicate</a>
  <a href="/Texas10MostWanted/MostWanted/capturedDetails?id=1800">Captured</a>
  <a href="/unrelated?id=1">Other</a>
</body></html>
"""
DETAIL_HTML = f"""
<html><body><main class="myDetailsPages">
  <h1 class="bigNameLabel">Alex Example</h1>
  <div class="rewardtext"><span>Up To $30,000 Reward</span></div>
  <div class="row1">
    <span class="labelText1a">RACE:</span><span class="detailText1a">White</span>
    <span class="labelText1b">SEX:</span><span class="detailText1b">Male</span>
    <span class="labelText1c">DOB:</span><span class="detailText1c">01/02/1980</span>
  </div>
  <div class="row1">
    <span class="labelText1a">HEIGHT:</span><span class="detailText1a">6'0&quot;</span>
    <span class="labelText1b">WEIGHT:</span><span class="detailText1b">195</span>
  </div>
  <div class="row4"><span class="labelText4">AKA:</span><span class="detailText4">A. Example; Example Person</span></div>
  <div class="row4"><span class="labelText4">SMT:</span><span class="detailText4">Scar on left arm</span></div>
  <div class="row4"><span class="labelText4">WANTED FOR:</span><span class="detailText4">Murder</span></div>
  <div class="row1"><span class="labelText1">LKC:</span><span class="detailText1">Austin, Texas</span></div>
  <p class="FinalDetailsText">This fictional official profile requests information concerning an active Texas warrant and directs tips to law enforcement.</p>
  <img id="mainImg" src="data:image/png;base64,{TINY_PNG}">
  <img class="imgOnButton" src="data:image/png;base64,{TINY_PNG}">
  <img class="imgOnButton" src="/Texas10MostWanted/Images/imageMale.jpg" alt="No Picture Available">
</main></body></html>
"""


class TexasDpsIngestionTests(unittest.TestCase):
    def test_discovers_active_detail_links_only(self):
        urls = discover_detail_urls(
            INDEX_HTML,
            "https://www.dps.texas.gov/Texas10MostWanted/MostWanted/fugitives",
        )

        self.assertEqual(
            urls,
            [
                "https://www.dps.texas.gov/Texas10MostWanted/MostWanted/fugitiveDetails?id=1900"
            ],
        )

    def test_maps_profile_fields_and_caches_unique_official_images(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            reward_case = parse_texas_dps_detail(
                DETAIL_HTML,
                "https://www.dps.texas.gov/Texas10MostWanted/MostWanted/fugitiveDetails?id=1900",
                published_date="2026-08-05",
                media_dir=Path(temporary_directory),
            )

            self.assertIsNotNone(reward_case)
            assert reward_case is not None
            self.assertEqual(reward_case["id"], "txdps-1900")
            self.assertEqual(reward_case["title"], "Alex Example")
            self.assertEqual(reward_case["reward"], 30_000)
            self.assertEqual(reward_case["description"], "Murder")
            self.assertEqual(reward_case["regions"], ["Texas"])
            self.assertEqual(reward_case["aliases"], ["A. Example", "Example Person"])
            self.assertEqual(reward_case["dateOfBirth"], "01/02/1980")
            self.assertEqual(reward_case["locations"], "Austin, Texas")
            self.assertEqual(reward_case["publishedDate"], "2026-08-05")
            self.assertEqual(
                reward_case["imageUrls"],
                ["/media/texas-dps/txdps-1900-1.png"],
            )
            self.assertTrue(
                (Path(temporary_directory) / "txdps-1900-1.png").is_file()
            )

    def test_skips_profile_without_a_real_embedded_image(self):
        placeholder_only = DETAIL_HTML.replace(
            f'data:image/png;base64,{TINY_PNG}',
            "/Texas10MostWanted/Images/imageMale.jpg",
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            reward_case = parse_texas_dps_detail(
                placeholder_only,
                "https://www.dps.texas.gov/Texas10MostWanted/MostWanted/fugitiveDetails?id=1900",
                published_date="2026-08-05",
                media_dir=Path(temporary_directory),
            )

        self.assertIsNone(reward_case)

    def test_skips_profile_without_a_cash_reward(self):
        without_reward = DETAIL_HTML.replace("Up To $30,000 Reward", "Information requested")
        with tempfile.TemporaryDirectory() as temporary_directory:
            reward_case = parse_texas_dps_detail(
                without_reward,
                "https://www.dps.texas.gov/Texas10MostWanted/MostWanted/fugitiveDetails?id=1900",
                published_date="2026-08-05",
                media_dir=Path(temporary_directory),
            )

        self.assertIsNone(reward_case)

    def test_skips_profile_with_an_explicit_capture_update(self):
        captured = DETAIL_HTML.replace(
            "This fictional official profile requests information",
            "Alex Example was captured on July 17, 2026. The official profile requests information",
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            reward_case = parse_texas_dps_detail(
                captured,
                "https://www.dps.texas.gov/Texas10MostWanted/MostWanted/fugitiveDetails?id=1900",
                published_date="2026-08-05",
                media_dir=Path(temporary_directory),
            )

        self.assertIsNone(reward_case)


if __name__ == "__main__":
    unittest.main()
