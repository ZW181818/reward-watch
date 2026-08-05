import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy.orm import Session

from app.admin import (
    CaseUpdateRequest,
    LoginRequest,
    audit_log,
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


if __name__ == "__main__":
    unittest.main()
