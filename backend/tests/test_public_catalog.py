import os
import tempfile
import unittest
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import event

from app.admin import (
    CaseUpdateRequest,
    ManualCaseCreateRequest,
    create_manual_case,
    delete_manual_case,
    update_admin_case,
)
from app.database import initialize_database
from app.storage import (
    clear_public_query_cache,
    load_database_case,
    query_database_case_page,
    sync_case_snapshot,
)


ADMIN_EMAIL = "catalog-admin@example.test"


def make_case(
    case_id: str,
    *,
    title: str,
    country: str,
    regions: list[str],
    status: str,
    reward: int | None,
    reward_currency: str | None,
    published_date: str,
    source: str,
    legacy_id: str,
) -> dict:
    return {
        "id": case_id,
        "title": title,
        "agency": source,
        "country": country,
        "regions": regions,
        "reward": reward,
        "rewardCurrency": reward_currency,
        "status": status,
        "summary": "A sufficiently detailed official summary for public catalog testing.",
        "publishedDate": published_date,
        "lastVerified": "2026-08-10",
        "sourceUrl": f"https://agency.test/notices/{case_id}",
        "sourceTitle": f"Official source for {title}",
        "sourceAuthor": source,
        "sourceRecords": [
            {
                "caseId": legacy_id,
                "url": f"https://agency.test/legacy/{legacy_id}",
                "title": f"Legacy record for {title}",
                "author": source,
                "reward": reward,
                "rewardCurrency": reward_currency,
            }
        ],
        "imageUrl": f"https://agency.test/images/{case_id}.jpg",
        "imageUrls": [f"https://agency.test/images/{case_id}.jpg"],
    }


def facet_map(options) -> dict[str, int]:
    return {option.value: option.count for option in options}


class PublicCatalogTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database_url = f"sqlite:///{Path(self.directory.name, 'catalog.db').as_posix()}"
        self.environment = patch.dict(os.environ, {"DATABASE_URL": self.database_url})
        self.environment.start()
        self.cases = [
            make_case(
                "fbi-alpha",
                title="Alpha Notice",
                country="US",
                regions=["Federal"],
                status="Open",
                reward=500,
                reward_currency="USD",
                published_date="2026-08-01",
                source="Federal Bureau of Investigation",
                legacy_id="legacy-alpha",
            ),
            make_case(
                "usms-bravo",
                title="Bravo Notice",
                country="US",
                regions=["Texas"],
                status="Closed",
                reward=None,
                reward_currency=None,
                published_date="2026-08-04",
                source="U.S. Marshals Service",
                legacy_id="legacy-bravo",
            ),
            make_case(
                "rcmp-charlie",
                title="Charlie Notice",
                country="Canada",
                regions=["Ontario"],
                status="Information Requested",
                reward=2_000,
                reward_currency="CAD",
                published_date="2026-08-03",
                source="Royal Canadian Mounted Police",
                legacy_id="legacy-charlie",
            ),
            make_case(
                "cn-police-delta",
                title="Delta Notice",
                country="China",
                regions=["Guangdong"],
                status="Open",
                reward=10_000,
                reward_currency="CNY",
                published_date="2026-08-02",
                source="Guangzhou Public Security Bureau",
                legacy_id="legacy-delta",
            ),
            make_case(
                "fbi-echo",
                title="Echo Notice",
                country="US",
                regions=["Texas"],
                status="Open",
                reward=1_500,
                reward_currency="USD",
                published_date="2026-08-05",
                source="Federal Bureau of Investigation",
                legacy_id="legacy-echo",
            ),
        ]
        sync_case_snapshot(
            cases=self.cases,
            source_cases=self.cases,
            update_status={
                "updatedAt": "2026-08-10T10:00:00+00:00",
                "allSourcesFresh": True,
                "totalCount": len(self.cases),
                "sources": [],
            },
            quality_report={"qualityGate": {"passed": True}},
            database_url=self.database_url,
        )

    def tearDown(self):
        self.environment.stop()
        self.directory.cleanup()

    @contextmanager
    def capture_storage_sql(self):
        engine = initialize_database(self.database_url)
        statements: list[str] = []

        def record_statement(_connection, _cursor, statement, _parameters, _context, _many):
            statements.append(" ".join(statement.casefold().split()))

        event.listen(engine, "before_cursor_execute", record_statement)
        try:
            with patch("app.storage.create_database_engine", return_value=engine), patch(
                "app.storage.release_database_engine"
            ):
                yield statements
        finally:
            event.remove(engine, "before_cursor_execute", record_statement)
            engine.dispose()

    def test_database_list_filters_pages_facets_and_sorts(self):
        second_page = query_database_case_page(
            country="US",
            sort="published_desc",
            page=2,
            page_size=2,
            database_url=self.database_url,
        )
        self.assertIsNotNone(second_page)
        self.assertEqual([case.id for case in second_page.items], ["fbi-alpha"])
        self.assertEqual(second_page.total, 3)
        self.assertEqual(second_page.totalPages, 2)
        self.assertEqual(
            facet_map(second_page.facets.statuses),
            {"Closed": 1, "Open": 2},
        )
        self.assertEqual(
            facet_map(second_page.facets.regions),
            {"Federal": 1, "Texas": 2},
        )
        self.assertEqual(
            facet_map(second_page.facets.sources),
            {
                "Federal Bureau of Investigation": 2,
                "U.S. Marshals Service": 1,
            },
        )

        filtered = query_database_case_page(
            q="echo",
            country="US",
            region="texas",
            status="Open",
            source="federal bureau of investigation",
            reward_min=1_000,
            reward_max=1_600,
            database_url=self.database_url,
        )
        self.assertEqual([case.id for case in filtered.items], ["fbi-echo"])

        expected_orders = {
            "published_desc": [
                "fbi-echo",
                "usms-bravo",
                "rcmp-charlie",
                "cn-police-delta",
                "fbi-alpha",
            ],
            "reward_desc": [
                "cn-police-delta",
                "rcmp-charlie",
                "fbi-echo",
                "fbi-alpha",
                "usms-bravo",
            ],
            "reward_asc": [
                "fbi-alpha",
                "fbi-echo",
                "rcmp-charlie",
                "cn-police-delta",
                "usms-bravo",
            ],
            "title_asc": [
                "fbi-alpha",
                "usms-bravo",
                "rcmp-charlie",
                "cn-police-delta",
                "fbi-echo",
            ],
        }
        for sort, expected_ids in expected_orders.items():
            with self.subTest(sort=sort):
                result = query_database_case_page(
                    sort=sort,
                    page_size=10,
                    database_url=self.database_url,
                )
                self.assertEqual([case.id for case in result.items], expected_ids)

    def test_override_changes_every_public_query_projection(self):
        update_admin_case(
            "fbi-alpha",
            CaseUpdateRequest(
                title="Zulu Reviewed Notice",
                agency="Pacific Review Unit",
                country="Canada",
                regions=["British Columbia"],
                status="Information Requested",
                reward=9_000,
                rewardCurrency="CAD",
                publishedDate=date(2026, 9, 10),
                sourceTitle="Pacific reviewed source",
                sourceAuthor="Pacific Review Unit",
                sourceRecords=[
                    {
                        "caseId": "legacy-alpha-reviewed",
                        "url": "https://review.test/notices/zulu",
                        "title": "Pacific reviewed source",
                        "author": "Pacific Review Unit",
                        "reward": 9_000,
                        "rewardCurrency": "CAD",
                    }
                ],
            ),
            ADMIN_EMAIL,
        )

        result = query_database_case_page(
            q="zulu",
            country="Canada",
            region="british columbia",
            status="Information Requested",
            source="pacific review unit",
            reward_min=8_500,
            reward_max=9_500,
            sort="published_desc",
            database_url=self.database_url,
        )
        self.assertEqual([case.id for case in result.items], ["fbi-alpha"])
        self.assertEqual(result.items[0].title, "Zulu Reviewed Notice")
        self.assertEqual(result.items[0].publishedDate, "2026-09-10")
        self.assertEqual(
            facet_map(result.facets.regions),
            {"British Columbia": 1},
        )
        self.assertEqual(
            facet_map(result.facets.sources),
            {"Pacific Review Unit": 1},
        )
        self.assertEqual(
            facet_map(result.facets.statuses),
            {"Information Requested": 1},
        )

        old_country = query_database_case_page(
            q="alpha notice",
            country="US",
            database_url=self.database_url,
        )
        self.assertEqual(old_country.total, 0)

        ready, old_alias = load_database_case("legacy-alpha", self.database_url)
        self.assertTrue(ready)
        self.assertIsNone(old_alias)
        ready, new_alias = load_database_case("legacy-alpha-reviewed", self.database_url)
        self.assertTrue(ready)
        self.assertEqual(new_alias.id, "fbi-alpha")

        canada = query_database_case_page(
            country="Canada",
            sort="published_desc",
            page_size=10,
            database_url=self.database_url,
        )
        self.assertEqual(
            [case.id for case in canada.items],
            ["fbi-alpha", "rcmp-charlie"],
        )

    def test_hidden_and_draft_canonical_and_legacy_ids_are_not_public(self):
        update_admin_case(
            "cn-police-delta",
            CaseUpdateRequest(isVisible=False),
            ADMIN_EMAIL,
        )
        update_admin_case(
            "usms-bravo",
            CaseUpdateRequest(reviewStatus="draft"),
            ADMIN_EMAIL,
        )

        result = query_database_case_page(page_size=10, database_url=self.database_url)
        self.assertEqual(
            {case.id for case in result.items},
            {"fbi-alpha", "rcmp-charlie", "fbi-echo"},
        )
        self.assertEqual(result.total, 3)
        self.assertNotIn("Closed", facet_map(result.facets.statuses))
        self.assertNotIn("Guangdong", facet_map(result.facets.regions))
        self.assertNotIn(
            "Guangzhou Public Security Bureau",
            facet_map(result.facets.sources),
        )
        self.assertNotIn("U.S. Marshals Service", facet_map(result.facets.sources))

        for case_id in (
            "cn-police-delta",
            "legacy-delta",
            "usms-bravo",
            "legacy-bravo",
        ):
            with self.subTest(case_id=case_id):
                ready, reward_case = load_database_case(case_id, self.database_url)
                self.assertTrue(ready)
                self.assertIsNone(reward_case)

    def test_manual_case_publish_hide_and_delete_updates_public_catalog(self):
        created = create_manual_case(
            ManualCaseCreateRequest(
                title="Manual Public Notice",
                summary="A manually reviewed notice with enough detail for publication testing.",
                agency="Example Review Agency",
                country="Canada",
                regions=["Alberta"],
                status="Information Requested",
                reward=3_000,
                rewardCurrency="CAD",
                publishedDate=date(2026, 9, 12),
                lastVerified=date(2026, 9, 12),
                sourceUrl="https://publisher.test/notices/manual-public",
                sourceTitle="Manual public source notice",
                sourceAuthor="Example Review Agency",
            ),
            ADMIN_EMAIL,
        )
        case_id = created["case"]["id"]

        ready, reward_case = load_database_case(case_id, self.database_url)
        self.assertTrue(ready)
        self.assertIsNone(reward_case)

        update_admin_case(
            case_id,
            CaseUpdateRequest(isVisible=True, reviewStatus="published"),
            ADMIN_EMAIL,
        )
        ready, reward_case = load_database_case(case_id, self.database_url)
        self.assertTrue(ready)
        self.assertEqual(reward_case.id, case_id)
        listed = query_database_case_page(q="manual public", database_url=self.database_url)
        self.assertEqual([case.id for case in listed.items], [case_id])

        update_admin_case(
            case_id,
            CaseUpdateRequest(isVisible=False),
            ADMIN_EMAIL,
        )
        self.assertIsNone(load_database_case(case_id, self.database_url)[1])

        update_admin_case(
            case_id,
            CaseUpdateRequest(isVisible=True),
            ADMIN_EMAIL,
        )
        self.assertIsNotNone(load_database_case(case_id, self.database_url)[1])
        delete_manual_case(case_id, ADMIN_EMAIL)
        self.assertIsNone(load_database_case(case_id, self.database_url)[1])
        self.assertEqual(
            query_database_case_page(q="manual public", database_url=self.database_url).total,
            0,
        )

    def test_legacy_alias_resolves_to_canonical_case(self):
        ready, reward_case = load_database_case("legacy-alpha", self.database_url)
        self.assertTrue(ready)
        self.assertEqual(reward_case.id, "fbi-alpha")

        ready, missing = load_database_case("legacy-does-not-exist", self.database_url)
        self.assertTrue(ready)
        self.assertIsNone(missing)

    def test_public_sql_transfers_only_bounded_payload_rows(self):
        with self.capture_storage_sql() as list_sql:
            result = query_database_case_page(
                country="US",
                page=2,
                page_size=2,
                database_url=self.database_url,
            )
        self.assertEqual(result.total, 3)

        payload_selects = [
            statement
            for statement in list_sql
            if statement.startswith("select ") and "public_cases.payload" in statement
        ]
        self.assertEqual(len(payload_selects), 1, list_sql)
        self.assertIn(" limit ", f" {payload_selects[0]} ")
        self.assertIn(" offset ", f" {payload_selects[0]} ")
        for statement in list_sql:
            if " union all " in statement:
                self.assertNotIn("public_cases.payload", statement)
        self.assertIn("over", payload_selects[0])

        with self.capture_storage_sql() as canonical_sql:
            ready, reward_case = load_database_case("fbi-alpha", self.database_url)
        self.assertTrue(ready)
        self.assertEqual(reward_case.id, "fbi-alpha")
        canonical_payload_selects = [
            statement
            for statement in canonical_sql
            if statement.startswith("select ") and "public_cases.payload" in statement
        ]
        self.assertEqual(len(canonical_payload_selects), 1, canonical_sql)
        self.assertIn("where public_cases.id =", canonical_payload_selects[0])
        self.assertIn(" limit ", f" {canonical_payload_selects[0]} ")

        with self.capture_storage_sql() as alias_sql:
            ready, reward_case = load_database_case("legacy-alpha", self.database_url)
        self.assertTrue(ready)
        self.assertEqual(reward_case.id, "fbi-alpha")
        alias_payload_selects = [
            statement
            for statement in alias_sql
            if statement.startswith("select ") and "public_cases.payload" in statement
        ]
        self.assertEqual(len(alias_payload_selects), 1, alias_sql)
        self.assertIn("where public_cases.id =", alias_payload_selects[0])
        self.assertIn("public_case_aliases.case_id", alias_payload_selects[0])
        self.assertIn("where public_case_aliases.alias_id =", alias_payload_selects[0])
        self.assertIn(" limit ", f" {alias_payload_selects[0]} ")

    def test_environment_public_queries_cache_identical_list_and_detail_requests(self):
        clear_public_query_cache()

        with self.capture_storage_sql() as statements:
            first_page = query_database_case_page(page=1, page_size=3)
            self.assertIsNotNone(first_page)
            after_first_page = len(statements)
            self.assertGreater(after_first_page, 0)

            second_page = query_database_case_page(page=1, page_size=3)
            self.assertEqual(second_page, first_page)
            self.assertEqual(len(statements), after_first_page)

            first_ready, first_detail = load_database_case("fbi-alpha")
            self.assertTrue(first_ready)
            self.assertIsNotNone(first_detail)
            after_first_detail = len(statements)
            self.assertGreater(after_first_detail, after_first_page)

            second_ready, second_detail = load_database_case("fbi-alpha")
            self.assertTrue(second_ready)
            self.assertEqual(second_detail, first_detail)
            self.assertEqual(len(statements), after_first_detail)

    def test_admin_commit_immediately_invalidates_public_query_caches(self):
        clear_public_query_cache()

        with self.capture_storage_sql() as statements:
            before_page = query_database_case_page(page=1, page_size=10)
            before_ready, before_detail = load_database_case("fbi-alpha")
            self.assertIsNotNone(before_page)
            self.assertTrue(before_ready)
            self.assertEqual(before_detail.title, "Alpha Notice")

            cached_statement_count = len(statements)
            self.assertEqual(
                query_database_case_page(page=1, page_size=10),
                before_page,
            )
            self.assertEqual(
                load_database_case("fbi-alpha"),
                (before_ready, before_detail),
            )
            self.assertEqual(len(statements), cached_statement_count)

            update_admin_case(
                "fbi-alpha",
                CaseUpdateRequest(title="Alpha Notice After Commit"),
                ADMIN_EMAIL,
            )

            after_page = query_database_case_page(page=1, page_size=10)
            after_ready, after_detail = load_database_case("fbi-alpha")
            self.assertGreater(len(statements), cached_statement_count)
            self.assertIsNotNone(after_page)
            self.assertTrue(after_ready)
            self.assertEqual(after_detail.title, "Alpha Notice After Commit")
            self.assertEqual(
                next(case.title for case in after_page.items if case.id == "fbi-alpha"),
                "Alpha Notice After Commit",
            )


if __name__ == "__main__":
    unittest.main()
