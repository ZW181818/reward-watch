import hashlib
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from app.ingestion.china_police import (
    CHINA_POLICE_NOTICES,
    GUANGZHOU_CYBER_2025_NOTICE,
    MPS_HANGZHOU_2025_NOTICE,
    MPS_LONGYAN_2025_NOTICE,
    QUANZHOU_2025_NOTICE,
    _cache_verified_poster,
    discover_notice_poster_url,
    parse_china_police_notice,
)
from app.models import RewardCase


PAGE_HTML = """
<html><head>
  <meta name="ArticleTitle" content="悬赏通告">
  <meta name="PubDate" content="2025-11-13">
</head><body>
  <div class="TRS_Editor">
    <p><img src="./W020251113318965478061.jpg"></p>
  </div>
</body></html>
"""
TEST_POSTER = b"\xff\xd8\xff" + (b"official-poster-test" * 8)


class ChinaPoliceIngestionTests(unittest.TestCase):
    def test_discovers_poster_on_issuing_police_website(self):
        self.assertEqual(
            discover_notice_poster_url(PAGE_HTML, QUANZHOU_2025_NOTICE.source_url),
            (
                "https://gaj.quanzhou.gov.cn/jwzx/gayw/202511/"
                "W020251113318965478061.jpg"
            ),
        )

    def test_selects_the_reviewed_poster_from_a_multi_poster_page(self):
        page_html = """
        <div class="trs_editor_view">
          <img src="./unreviewed.jpg">
          <img src="./W020251210350394014512_ORIGIN.jpg">
        </div>
        """

        self.assertEqual(
            discover_notice_poster_url(
                page_html,
                MPS_HANGZHOU_2025_NOTICE.source_url,
                expected_filename=MPS_HANGZHOU_2025_NOTICE.poster_filename,
            ),
            (
                "https://gaj.wuhan.gov.cn/jmzx/gayw/202512/"
                "W020251210350394014512_ORIGIN.jpg"
            ),
        )

    def test_reviewed_manifest_contains_complete_100_subject_mps_release(self):
        mps_notices = [
            notice
            for notice in CHINA_POLICE_NOTICES
            if notice.notice_id.startswith("mps-")
        ]
        subjects = [subject for notice in mps_notices for subject in notice.subjects]

        self.assertEqual(len(mps_notices), 8)
        self.assertEqual(len(subjects), 100)
        self.assertEqual(len({subject.case_id for subject in subjects}), 100)
        self.assertTrue(all(notice.reward == 200_000 for notice in mps_notices))
        self.assertEqual(len(MPS_LONGYAN_2025_NOTICE.subjects), 43)

    def test_guangzhou_cyber_notice_contains_20_reviewed_subjects(self):
        self.assertEqual(len(GUANGZHOU_CYBER_2025_NOTICE.subjects), 20)
        self.assertEqual(GUANGZHOU_CYBER_2025_NOTICE.reward, 10_000)
        self.assertEqual(GUANGZHOU_CYBER_2025_NOTICE.source_encoding, "gb18030")
        self.assertTrue(
            all(
                subject.case_id.startswith("cn-police-gz-20250605-")
                for subject in GUANGZHOU_CYBER_2025_NOTICE.subjects
            )
        )

    def test_xinhua_mps_page_metadata_and_poster_layout_are_supported(self):
        page_html = f"""
        <html><head>
          <meta name="publishdate" content="2025-12-09">
        </head><body>
          <h1>{MPS_LONGYAN_2025_NOTICE.source_title}</h1>
          <span id="detailContent">
            <img src="{MPS_LONGYAN_2025_NOTICE.poster_filename}">
          </span>
        </body></html>
        """

        poster_url = discover_notice_poster_url(
            page_html,
            MPS_LONGYAN_2025_NOTICE.source_url,
            expected_filename=MPS_LONGYAN_2025_NOTICE.poster_filename,
        )
        cases = parse_china_police_notice(
            page_html,
            notice=MPS_LONGYAN_2025_NOTICE,
            image_urls={
                subject.case_id: ["/media/china-police/poster.jpg"]
                for subject in MPS_LONGYAN_2025_NOTICE.subjects
            },
        )

        self.assertTrue(poster_url.startswith("https://www.news.cn/legal/20251209/"))
        self.assertEqual(len(cases), 43)

    def test_every_reviewed_subject_maps_to_the_public_api_schema(self):
        mapped_cases = []
        for notice in CHINA_POLICE_NOTICES:
            page_html = f"""
            <html><head>
              <meta name="PubDate" content="{notice.source_published_date}">
            </head><body><h1>{notice.source_title}</h1></body></html>
            """
            mapped_cases.extend(
                parse_china_police_notice(
                    page_html,
                    notice=notice,
                    image_urls={
                        subject.case_id: [
                            f"/media/china-police/{subject.case_id}-portrait.jpg",
                            f"/media/china-police/{notice.notice_id}-poster.jpg",
                        ]
                        for subject in notice.subjects
                    },
                )
            )

        validated_cases = [RewardCase.model_validate(case) for case in mapped_cases]
        self.assertEqual(len(validated_cases), 122)
        self.assertTrue(all(case.rewardCurrency == "CNY" for case in validated_cases))

    def test_maps_reviewed_criminal_reward_subjects(self):
        cases = parse_china_police_notice(
            PAGE_HTML,
            notice=QUANZHOU_2025_NOTICE,
            image_urls={
                subject.case_id: [
                    f"/media/china-police/{subject.case_id}-portrait.jpg",
                    "/media/china-police/quanzhou-20251113-poster.jpg",
                ]
                for subject in QUANZHOU_2025_NOTICE.subjects
            },
        )

        self.assertEqual(len(cases), 2)
        self.assertEqual(cases[0]["country"], "China")
        self.assertEqual(cases[0]["reward"], 250_000)
        self.assertEqual(cases[0]["rewardCurrency"], "CNY")
        self.assertEqual(cases[0]["regions"], ["福建省"])
        self.assertEqual(cases[0]["sourceAuthor"], "泉州市公安局")
        self.assertEqual(cases[0]["sourceKind"], "official")
        self.assertEqual(len(cases[0]["imageUrls"]), 2)
        self.assertIn("portrait.jpg", cases[0]["imageUrl"])

    def test_explicit_revocation_removes_notice_subjects(self):
        revoked_page = PAGE_HTML.replace(
            "</body>",
            "<p>本局决定撤销悬赏。</p></body>",
        )

        self.assertEqual(
            parse_china_police_notice(
                revoked_page,
                notice=QUANZHOU_2025_NOTICE,
                image_urls={
                    subject.case_id: ["/media/china-police/poster.jpg"]
                    for subject in QUANZHOU_2025_NOTICE.subjects
                },
            ),
            [],
        )

    def test_generic_surrender_request_does_not_close_cases(self):
        exhortation_page = PAGE_HTML.replace(
            "</body>",
            "<p>公安机关敦促相关犯罪嫌疑人主动投案自首。</p></body>",
        )

        cases = parse_china_police_notice(
            exhortation_page,
            notice=QUANZHOU_2025_NOTICE,
            image_urls={
                subject.case_id: ["/media/china-police/poster.jpg"]
                for subject in QUANZHOU_2025_NOTICE.subjects
            },
        )

        self.assertEqual(len(cases), 2)

    def test_subject_specific_capture_removes_only_that_subject(self):
        updated_page = PAGE_HTML.replace(
            "</body>",
            "<p>温子渝已抓获归案。</p></body>",
        )

        cases = parse_china_police_notice(
            updated_page,
            notice=QUANZHOU_2025_NOTICE,
            image_urls={
                subject.case_id: ["/media/china-police/poster.jpg"]
                for subject in QUANZHOU_2025_NOTICE.subjects
            },
        )

        self.assertEqual([case["title"] for case in cases], ["陈柏源"])

    def test_caches_only_the_reviewed_poster_hash(self):
        test_notice = replace(
            QUANZHOU_2025_NOTICE,
            expected_poster_sha256=hashlib.sha256(TEST_POSTER).hexdigest(),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            image_url = _cache_verified_poster(
                test_notice,
                TEST_POSTER,
                media_dir=Path(temporary_directory),
            )
            self.assertEqual(
                image_url,
                "/media/china-police/quanzhou-20251113-poster.jpg",
            )
            self.assertTrue(
                (Path(temporary_directory) / "quanzhou-20251113-poster.jpg").is_file()
            )

            with self.assertRaisesRegex(ValueError, "manual review required"):
                _cache_verified_poster(
                    test_notice,
                    TEST_POSTER + b"changed",
                    media_dir=Path(temporary_directory),
                )


if __name__ == "__main__":
    unittest.main()
