from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Iterable

from .models import CaseMapItem, CaseMapLocation, RewardCase


MAP_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "case_map_locations.json"


@lru_cache(maxsize=1)
def _load_map_data() -> tuple[str | None, dict[str, list[dict[str, Any]]]]:
    if not MAP_DATA_PATH.exists():
        return None, {}

    payload = json.loads(MAP_DATA_PATH.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases", {})
    if not isinstance(raw_cases, dict):
        return payload.get("generatedAt"), {}
    return payload.get("generatedAt"), raw_cases


def get_map_generated_at() -> str | None:
    return _load_map_data()[0]


def get_case_map_locations(case_id: str) -> list[CaseMapLocation]:
    _, locations_by_id = _load_map_data()
    return [
        CaseMapLocation.model_validate(item)
        for item in locations_by_id.get(case_id, [])
    ]


def get_case_map_location_ids() -> tuple[set[str], set[str]]:
    """Return generated city IDs and region-only IDs without loading case payloads."""

    _, locations_by_id = _load_map_data()
    city_ids: set[str] = set()
    region_ids: set[str] = set()
    for case_id, items in locations_by_id.items():
        locations = [CaseMapLocation.model_validate(item) for item in items]
        if any(location.precision == "city" for location in locations):
            city_ids.add(case_id)
        elif locations:
            region_ids.add(case_id)
    return city_ids, region_ids


def build_case_map_item(
    reward_case: RewardCase | dict[str, Any],
    override_locations: list[dict[str, Any]] | None = None,
) -> CaseMapItem | None:
    case = (
        reward_case
        if isinstance(reward_case, RewardCase)
        else RewardCase.model_validate(reward_case)
    )
    raw_locations = (
        override_locations
        if override_locations is not None
        else [location.model_dump(mode="json") for location in get_case_map_locations(case.id)]
    )
    locations = [
        location
        for item in raw_locations
        if (location := CaseMapLocation.model_validate(item)).precision == "city"
    ]
    if not locations:
        return None

    return CaseMapItem(
        id=case.id,
        title=case.title,
        agency=case.sourceAuthor or case.agency,
        country=case.country,
        reward=case.reward,
        rewardCurrency=case.rewardCurrency,
        status=case.status,
        imageUrl=case.imageUrl,
        locations=locations,
    )


def build_case_map_items(cases: Iterable[RewardCase]) -> list[CaseMapItem]:
    return [item for reward_case in cases if (item := build_case_map_item(reward_case))]
