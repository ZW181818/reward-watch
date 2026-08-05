from __future__ import annotations

import re
from collections import Counter
from copy import deepcopy
from typing import Any

from .ingestion.reward_amount import extract_cash_amount


MERGEABLE_SOURCE_PREFIXES = frozenset({"fbi", "rfj"})
_PERSON_KEY_PATTERN = re.compile(r"[^a-z0-9]")


def normalize_reward_metadata(
    cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in cases:
        reward_case = deepcopy(item)
        raw_reward = reward_case.get("reward")
        reward = int(raw_reward) if isinstance(raw_reward, (int, float)) else 0
        if reward > 0:
            reward_case["reward"] = reward
            reward_case["rewardCurrency"] = reward_case.get(
                "rewardCurrency"
            ) or ("CAD" if reward_case.get("country") == "Canada" else "USD")
        else:
            reward_case["reward"] = None
            reward_case["rewardCurrency"] = None
        normalized.append(reward_case)
    return normalized


def merge_cross_source_cases(
    cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for reward_case in cases:
        key = (
            str(reward_case.get("country", "")),
            _PERSON_KEY_PATTERN.sub("", str(reward_case.get("title", "")).lower()),
        )
        groups.setdefault(key, []).append(reward_case)

    merged: list[dict[str, Any]] = []
    consumed_ids: set[str] = set()
    for reward_case in cases:
        case_id = str(reward_case.get("id", ""))
        if case_id in consumed_ids:
            continue

        key = (
            str(reward_case.get("country", "")),
            _PERSON_KEY_PATTERN.sub("", str(reward_case.get("title", "")).lower()),
        )
        group = groups[key]
        prefixes = {_source_prefix(item) for item in group}
        merge_group = (
            group
            if len(group) > 1 and MERGEABLE_SOURCE_PREFIXES.issubset(prefixes)
            else [reward_case]
        )
        consumed_ids.update(str(item.get("id", "")) for item in merge_group)
        merged.append(_merge_group(merge_group))
    return merged


def validate_data_quality(cases: list[dict[str, Any]]) -> None:
    errors: list[str] = []
    ids = [str(item.get("id", "")) for item in cases]
    duplicate_ids = [case_id for case_id, count in Counter(ids).items() if count > 1]
    if duplicate_ids:
        errors.append(f"duplicate case ids: {', '.join(duplicate_ids[:5])}")

    for reward_case in cases:
        case_id = str(reward_case.get("id", ""))
        reward = reward_case.get("reward")
        currency = reward_case.get("rewardCurrency")
        reward_text = str(reward_case.get("rewardText") or "")
        if reward is None and currency is not None:
            errors.append(f"{case_id}: currency exists without a published reward")
        if isinstance(reward, int) and reward > 0 and currency not in {"USD", "CAD"}:
            errors.append(f"{case_id}: published reward is missing a supported currency")
        if reward_text and re.search(r"\b(?:million|billion|thousand|[kmb])\b", reward_text, re.I):
            parsed = extract_cash_amount(reward_text)
            if parsed and reward != parsed:
                errors.append(
                    f"{case_id}: reward {reward!r} does not match reward text amount {parsed}"
                )

    if errors:
        raise ValueError("Data quality validation failed: " + "; ".join(errors[:12]))


def build_data_quality_report(
    cases: list[dict[str, Any]],
    *,
    generated_at: str,
    source_statuses: list[dict[str, Any]],
) -> dict[str, Any]:
    positive_rewards = [
        int(item["reward"])
        for item in cases
        if isinstance(item.get("reward"), int) and int(item["reward"]) > 0
    ]
    source_names = [
        source_name
        for item in cases
        for source_name in _case_source_names(item)
    ]
    return {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "totalCases": len(cases),
        "sourceRecords": sum(
            max(1, len(item.get("sourceRecords", []))) for item in cases
        ),
        "multiSourceCases": sum(len(item.get("sourceRecords", [])) > 1 for item in cases),
        "countries": dict(sorted(Counter(item.get("country") for item in cases).items())),
        "statuses": dict(sorted(Counter(item.get("status") for item in cases).items())),
        "sources": dict(sorted(Counter(source_names).items())),
        "rewards": {
            "published": len(positive_rewards),
            "notPublished": len(cases) - len(positive_rewards),
            "maximum": max(positive_rewards, default=None),
            "currencies": dict(
                sorted(
                    Counter(
                        item.get("rewardCurrency")
                        for item in cases
                        if item.get("reward") is not None
                    ).items()
                )
            ),
        },
        "images": {
            "casesWithoutPrimaryImage": sum(not item.get("imageUrl") for item in cases),
            "localPrimaryImages": sum(
                str(item.get("imageUrl", "")).startswith("/media/") for item in cases
            ),
            "remotePrimaryImages": sum(
                str(item.get("imageUrl", "")).startswith("http") for item in cases
            ),
        },
        "regions": {
            "casesWithoutRegion": sum(not item.get("regions") for item in cases),
        },
        "freshness": {
            "allSourcesFresh": all(status.get("success") for status in source_statuses),
            "staleSources": [
                status.get("id") for status in source_statuses if not status.get("success")
            ],
        },
        "checks": {
            "uniqueCaseIds": True,
            "rewardUnitsConsistent": True,
            "rewardCurrenciesPresent": True,
        },
    }


def _merge_group(group: list[dict[str, Any]]) -> dict[str, Any]:
    if len(group) == 1:
        return deepcopy(group[0])

    primary = max(
        group,
        key=lambda item: (
            int(item.get("reward") or -1),
            _source_prefix(item) == "rfj",
            len(str(item.get("summary", ""))),
        ),
    )
    merged = deepcopy(primary)
    merged["sourceRecords"] = _unique_source_records(group)
    merged["regions"] = _unique_values(group, "regions")
    merged["aliases"] = _unique_values(group, "aliases")
    merged["imageUrls"] = _unique_values(group, "imageUrls")
    if merged["imageUrls"]:
        merged["imageUrl"] = merged["imageUrls"][0]

    richest_summary = max(group, key=lambda item: len(str(item.get("summary", ""))))
    merged["summary"] = richest_summary.get("summary") or merged.get("summary")
    richest_description = max(
        group,
        key=lambda item: len(str(item.get("description") or "")),
    )
    merged["description"] = richest_description.get("description") or merged.get("description")
    merged["lastVerified"] = max(str(item.get("lastVerified", "")) for item in group)
    updated_dates = [
        str(item.get("sourceUpdatedDate"))
        for item in group
        if item.get("sourceUpdatedDate")
    ]
    merged["sourceUpdatedDate"] = max(updated_dates, default=None)
    merged["status"] = (
        "Closed"
        if all(str(item.get("status", "")).lower() == "closed" for item in group)
        else str(primary.get("status", "Open"))
    )

    for field in (
        "age",
        "dateOfBirth",
        "placeOfBirth",
        "sex",
        "race",
        "nationality",
        "hair",
        "eyes",
        "height",
        "weight",
        "locations",
        "distinguishingFeatures",
        "fieldOffice",
    ):
        if not merged.get(field):
            merged[field] = next((item.get(field) for item in group if item.get(field)), None)
    return merged


def _unique_source_records(group: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for item in sorted(group, key=lambda value: int(value.get("reward") or -1), reverse=True):
        source_url = str(item.get("sourceUrl", ""))
        if not source_url or source_url in seen_urls:
            continue
        seen_urls.add(source_url)
        records.append(
            {
                "caseId": str(item.get("id", "")),
                "url": source_url,
                "title": item.get("sourceTitle"),
                "author": item.get("sourceAuthor") or item.get("agency"),
                "reward": item.get("reward"),
                "rewardCurrency": item.get("rewardCurrency"),
                "rewardText": item.get("rewardText"),
                "sourceUpdatedDate": item.get("sourceUpdatedDate"),
            }
        )
    return records


def _unique_values(group: list[dict[str, Any]], field: str) -> list[str]:
    values: list[str] = []
    for item in group:
        raw_values = item.get(field, [])
        candidates = raw_values if isinstance(raw_values, list) else []
        for value in candidates:
            text = str(value)
            if text and text not in values:
                values.append(text)
    return values


def _source_prefix(reward_case: dict[str, Any]) -> str:
    return str(reward_case.get("id", "")).split("-", 1)[0]


def _case_source_names(reward_case: dict[str, Any]) -> list[str]:
    source_records = reward_case.get("sourceRecords", [])
    if isinstance(source_records, list) and source_records:
        return [
            str(record.get("author") or "Unknown")
            for record in source_records
            if isinstance(record, dict)
        ]
    return [str(reward_case.get("sourceAuthor") or reward_case.get("agency") or "Unknown")]
