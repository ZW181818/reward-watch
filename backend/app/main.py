from collections import Counter
from math import ceil
import os
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .data import load_cases
from .admin import router as admin_router
from .settings import router as settings_router
from .models import (
    CaseFacetOption,
    CaseFacets,
    CaseListResponse,
    CountryCode,
    HealthResponse,
    RewardCase,
)


SortMode = Literal["published_desc", "reward_desc", "reward_asc", "title_asc"]
MEDIA_DIR = Path(__file__).resolve().parents[1] / "data" / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


app = FastAPI(
    title="Reward Watch API",
    version="0.1.0",
    description="Public reward and wanted-case aggregation API for MVP0.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:8081,http://127.0.0.1:8081,http://localhost:19006,http://127.0.0.1:19006",
        ).split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")
app.include_router(admin_router)
app.include_router(settings_router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="reward-watch-api")


def _case_sources(reward_case: RewardCase) -> set[str]:
    return {
        source_name
        for source_name in [
            reward_case.sourceAuthor or reward_case.agency,
            *(source.author for source in reward_case.sourceRecords),
        ]
        if source_name
    }


def _facet_options(values: Counter[str]) -> list[CaseFacetOption]:
    return [
        CaseFacetOption(value=value, count=count)
        for value, count in sorted(values.items(), key=lambda item: item[0].lower())
    ]


@app.get("/cases", response_model=CaseListResponse)
def list_cases(
    q: Annotated[str | None, Query(min_length=1)] = None,
    country: CountryCode | None = None,
    region: str | None = None,
    status: str | None = None,
    source: str | None = None,
    reward_min: Annotated[int | None, Query(ge=0)] = None,
    reward_max: Annotated[int | None, Query(ge=0)] = None,
    sort: SortMode = "published_desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 12,
) -> CaseListResponse:
    cases = load_cases()

    if q:
        needle = q.lower()
        cases = [
            case
            for case in cases
            if needle in case.title.lower()
            or needle in (case.sourceAuthor or case.agency).lower()
            or needle in (case.sourceTitle or "").lower()
            or any(
                needle in source.author.lower()
                or needle in (source.title or "").lower()
                for source in case.sourceRecords
            )
            or any(needle in region_name.lower() for region_name in case.regions)
            or needle in case.summary.lower()
        ]

    if country:
        cases = [case for case in cases if case.country == country]

    facet_cases = cases.copy()

    facets = CaseFacets(
        statuses=_facet_options(Counter(case.status for case in facet_cases)),
        regions=_facet_options(
            Counter(region_name for case in facet_cases for region_name in case.regions)
        ),
        sources=_facet_options(
            Counter(source_name for case in facet_cases for source_name in _case_sources(case))
        ),
    )

    if region:
        cases = [case for case in cases if region in case.regions]

    if status:
        cases = [case for case in cases if case.status == status]

    if source:
        cases = [case for case in cases if source in _case_sources(case)]

    if reward_min is not None:
        cases = [case for case in cases if case.reward is not None and case.reward >= reward_min]

    if reward_max is not None:
        cases = [case for case in cases if case.reward is not None and case.reward <= reward_max]

    if sort == "reward_desc":
        cases = sorted(
            cases,
            key=lambda case: case.reward if case.reward is not None else -1,
            reverse=True,
        )
    elif sort == "reward_asc":
        cases = sorted(
            cases,
            key=lambda case: (case.reward is None, case.reward or 0),
        )
    elif sort == "title_asc":
        cases = sorted(cases, key=lambda case: case.title.lower())
    else:
        cases = sorted(cases, key=lambda case: case.publishedDate, reverse=True)

    total = len(cases)
    total_pages = ceil(total / page_size) if total else 0
    start = (page - 1) * page_size

    return CaseListResponse(
        items=cases[start : start + page_size],
        total=total,
        page=page,
        pageSize=page_size,
        totalPages=total_pages,
        facets=facets,
    )


@app.get("/cases/{case_id}", response_model=RewardCase)
def get_case(case_id: str) -> RewardCase:
    for reward_case in load_cases():
        if reward_case.id == case_id or any(
            source.caseId == case_id for source in reward_case.sourceRecords
        ):
            return reward_case

    raise HTTPException(status_code=404, detail="Case not found")
