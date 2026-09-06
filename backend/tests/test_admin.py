import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from sqlalchemy.orm import Session

from app import media_storage
from app.admin import (
    CaseUpdateRequest,
    ChangePasswordRequest,
    LoginRequest,
    ManualCaseCreateRequest,
    audit_log,
    change_password,
    create_manual_case,
    delete_manual_case,
    get_admin_case,
    get_admin_home_settings,
    login,
    reset_admin_case,
    publish_admin_home_settings,
    save_admin_home_settings,
    update_admin_case,
)
from app.admin_security import hash_password
from app.database import AdminUserRow, initialize_database
from app.main import get_case
from app.storage import load_database_cases, sync_case_snapshot
from app.settings import HomeSettings, get_home_settings


def case_payload():
    return {
        "id": "fbi-admin-test",
        "title": "Original title",
        "agency": "Federal Bureau of Investigation",
        "country": "US",
        "regions": ["Federal"],
        "reward": 1000,
        "rewardCurrency": "USD",
        "status": "Open",
        "summary": "A detailed official summary used by the administrator test.",
        "publishedDate": "2026-08-01",
        "lastVerified": "2026-08-05",
        "sourceUrl": "https://fbi.test/admin",
        "sourceAuthor": "Federal Bureau of Investigation",
        "sourceRecords": [],
        "imageUrl": "https://fbi.test/admin.jpg",
        "imageUrls": ["https://fbi.test/admin.jpg"],
    }


class AdminTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database_url = f"sqlite:///{Path(self.directory.name, 'admin.db').as_posix()}"
        self.environment = patch.dict(
            os.environ,
            {
                "DATABASE_URL": self.database_url,
                "ADMIN_JWT_SECRET": "a-test-secret-that-is-long-enough-for-admin-tokens",
            },
        )
        self.environment.start()
        payload = case_payload()
        sync_case_snapshot(
            cases=[payload],
            source_cases=[payload],
            update_status={
                "updatedAt": "2026-08-05T10:00:00+00:00",
                "allSourcesFresh": True,
                "totalCount": 1,
                "sources": [],
            },
            quality_report={"qualityGate": {"passed": True}},
            database_url=self.database_url,
        )
        engine = initialize_database(self.database_url)
        with Session(engine) as session, session.begin():
            session.add(
                AdminUserRow(
                    email="admin@example.test",
                    password_hash=hash_password("correct horse battery staple"),
                    role="admin",
                )
            )
        engine.dispose()

    def tearDown(self):
        self.environment.stop()
        self.directory.cleanup()

    def test_login_returns_a_token(self):
        result = login(
            LoginRequest(
                email="admin@example.test",
                password="correct horse battery staple",
            )
        )
        self.assertTrue(result["accessToken"])
        self.assertEqual(result["admin"]["role"], "admin")

    def test_admin_can_change_password(self):
        result = change_password(
            ChangePasswordRequest(
                currentPassword="correct horse battery staple",
                newPassword="replacement horse battery staple",
            ),
            "admin@example.test",
        )

        self.assertTrue(result["changed"])
        login(
            LoginRequest(
                email="admin@example.test",
                password="replacement horse battery staple",
            )
        )
        self.assertEqual(audit_log(30, "admin@example.test")[0]["action"], "admin.password.changed")

    def test_case_override_and_reset_are_audited(self):
        update_admin_case(
            "fbi-admin-test",
            CaseUpdateRequest(title="Reviewed title", isVisible=False, note="Needs source review"),
            "admin@example.test",
        )

        detail = get_admin_case("fbi-admin-test", "admin@example.test")
        self.assertEqual(detail["effective"]["title"], "Reviewed title")
        self.assertFalse(detail["override"]["isVisible"])
        self.assertEqual(load_database_cases(self.database_url), [])

        reset_admin_case("fbi-admin-test", "admin@example.test")
        self.assertEqual(load_database_cases(self.database_url)[0].title, "Original title")
        self.assertEqual(len(audit_log(30, "admin@example.test")), 2)

    def test_admin_can_override_the_complete_case_payload(self):
        update_admin_case(
            "fbi-admin-test",
            CaseUpdateRequest(
                title="Reviewed public title",
                agency="Reviewed Agency",
                country="Canada",
                regions=["Ontario", "Ontario", "Quebec"],
                caseType="Public information request",
                description="Reviewed description",
                reward=2500,
                rewardCurrency="CAD",
                rewardText="Up to CAD 2,500",
                status="Information Requested",
                summary="A complete reviewed summary with enough detail for publication.",
                warningMessage="Do not approach. Contact the official agency directly with information.",
                aliases=["Example Alias", "Example Alias"],
                age="42",
                dateOfBirth="1984-01-02",
                placeOfBirth="Ottawa, Ontario",
                sex="Female",
                race="Not published",
                nationality="Canadian",
                hair="Brown",
                eyes="Green",
                height="170 cm",
                weight="65 kg",
                locations="Ontario and Quebec",
                distinguishingFeatures="Reviewed public identifying details.",
                fieldOffice="Ottawa",
                publishedDate="2026-08-10",
                lastVerified="2026-08-11",
                sourceUpdatedDate="2026-08-09",
                sourceUrl="https://agency.example.test/notices/reviewed",
                sourceTitle="Reviewed source notice",
                sourceAuthor="Reviewed Agency",
                sourceKind="official",
                sourceRecords=[
                    {
                        "caseId": "fbi-admin-test",
                        "url": "https://agency.example.test/notices/reviewed",
                        "title": "Reviewed source notice",
                        "author": "Reviewed Agency",
                        "reward": 2500,
                        "rewardCurrency": "CAD",
                        "rewardText": "Up to CAD 2,500",
                        "sourceUpdatedDate": "2026-08-09",
                    }
                ],
                imageUrl="https://agency.example.test/images/cover.jpg",
                imageUrls=[
                    "https://agency.example.test/images/cover.jpg",
                    "https://agency.example.test/images/profile.jpg",
                    "https://agency.example.test/images/profile.jpg",
                ],
            ),
            "admin@example.test",
        )

        effective = get_admin_case("fbi-admin-test", "admin@example.test")["effective"]
        self.assertEqual(effective["agency"], "Reviewed Agency")
        self.assertEqual(effective["country"], "Canada")
        self.assertEqual(effective["regions"], ["Ontario", "Quebec"])
        self.assertEqual(effective["aliases"], ["Example Alias"])
        self.assertEqual(effective["lastVerified"], "2026-08-11")
        self.assertEqual(effective["sourceRecords"][0]["rewardCurrency"], "CAD")
        self.assertEqual(
            effective["imageUrls"],
            [
                "https://agency.example.test/images/cover.jpg",
                "https://agency.example.test/images/profile.jpg",
            ],
        )
        self.assertEqual(load_database_cases(self.database_url)[0].agency, "Reviewed Agency")

    def test_home_settings_require_draft_then_publish(self):
        settings = HomeSettings(
            brandSubtitle="Verified notices from official North American sources",
            safetyMessage="Do not approach any individual. Contact the official agency with information.",
            featuredCaseIds=["fbi-admin-test"],
            recentCaseLimit=5,
        )

        save_admin_home_settings(settings, "admin@example.test")
        before_publish = get_admin_home_settings("admin@example.test")
        self.assertEqual(before_publish["draft"]["recentCaseLimit"], 5)
        self.assertEqual(get_home_settings().recentCaseLimit, 4)

        publish_admin_home_settings("admin@example.test")
        self.assertEqual(get_home_settings().recentCaseLimit, 5)
        self.assertIsNone(get_admin_home_settings("admin@example.test")["draft"])

    def test_manual_case_stays_draft_until_published_and_survives_sync(self):
        created = create_manual_case(
            ManualCaseCreateRequest(
                title="Verified community reward notice",
                summary="A source-backed public notice requesting information from the public.",
                country="US",
                regions=["Washington"],
                generalLocation="Seattle metropolitan area",
                reward=5000,
                rewardCurrency="USD",
                sourceUrl="https://example.test/public-notice",
                sourceTitle="Public information request",
                sourceAuthor="Example Public Safety Foundation",
                imageUrls=["https://example.test/notice.jpg"],
            ),
            "admin@example.test",
        )
        case_id = created["case"]["id"]

        self.assertTrue(case_id.startswith("manual-"))
        self.assertEqual(created["case"]["sourceKind"], "publisher")
        self.assertEqual(load_database_cases(self.database_url)[0].id, "fbi-admin-test")
        detail = get_admin_case(case_id, "admin@example.test")
        self.assertTrue(detail["isManual"])
        self.assertEqual(detail["override"]["reviewStatus"], "draft")
        self.assertFalse(detail["override"]["isVisible"])

        update_admin_case(
            case_id,
            CaseUpdateRequest(reviewStatus="published", isVisible=True),
            "admin@example.test",
        )
        self.assertIn(case_id, {case.id for case in load_database_cases(self.database_url)})

        payload = case_payload()
        sync_case_snapshot(
            cases=[payload],
            source_cases=[payload],
            update_status={
                "updatedAt": "2026-08-05T11:00:00+00:00",
                "allSourcesFresh": True,
                "totalCount": 1,
                "sources": [],
            },
            quality_report={"qualityGate": {"passed": True}},
            database_url=self.database_url,
        )
        self.assertIn(case_id, {case.id for case in load_database_cases(self.database_url)})

        delete_manual_case(case_id, "admin@example.test")
        self.assertNotIn(case_id, {case.id for case in load_database_cases(self.database_url)})

    def test_uploaded_photo_can_be_previewed_in_a_draft_and_published(self):
        source = BytesIO()
        Image.new("RGB", (640, 480), "#4466AA").save(source, format="PNG")

        empty_cloudinary = {
            key: "" for key in media_storage.CLOUDINARY_ENVIRONMENT_KEYS
        }
        with tempfile.TemporaryDirectory() as media_directory, patch.object(
            media_storage, "MEDIA_DIR", Path(media_directory)
        ), patch.dict(
            os.environ,
            {"APP_ENV": "development", **empty_cloudinary},
            clear=False,
        ):
            storage_status = media_storage.media_storage_status()
            self.assertTrue(storage_status["ready"])
            self.assertEqual(storage_status["provider"], "local")

            image_url = media_storage.store_admin_image(source.getvalue())
            self.assertTrue((Path(media_directory) / image_url.removeprefix("/media/")).exists())

            created = create_manual_case(
                ManualCaseCreateRequest(
                    title="Previewable test notice",
                    summary="A complete test notice used to verify draft image preview and publication.",
                    agency="Example Test Agency",
                    country="US",
                    regions=["Washington"],
                    status="Information Requested",
                    sourceUrl="https://example.test/notices/previewable",
                    sourceTitle="Previewable public test notice",
                    sourceAuthor="Example Test Agency",
                    imageUrls=[image_url],
                ),
                "admin@example.test",
            )
            case_id = created["case"]["id"]
            self.assertEqual(created["case"]["imageUrl"], image_url)
            self.assertNotIn(case_id, {case.id for case in load_database_cases(self.database_url)})

            update_admin_case(
                case_id,
                CaseUpdateRequest(isVisible=True, reviewStatus="published"),
                "admin@example.test",
            )
            public_case = get_case(case_id)
            self.assertEqual(public_case.imageUrls, [image_url])

    def test_manual_case_requires_a_real_region(self):
        with self.assertRaises(ValueError):
            ManualCaseCreateRequest(
                title="Verified public notice",
                summary="A sufficiently detailed public notice summary for validation.",
                country="US",
                regions=["  "],
                sourceUrl="https://example.test/notices/region-check",
                sourceTitle="Verified public notice source",
                sourceAuthor="Example Public Safety Foundation",
            )


if __name__ == "__main__":
    unittest.main()
