from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from .wordpress import (
    clean_text,
    fetch_wordpress_posts,
    post_images,
    post_text,
    post_title,
)


REWARDS_API_URL = "https://rewardsforjustice.net/wp-json/wp/v2/rewards"
SOURCE_NAME = "U.S. Department of State - Rewards for Justice"
SAFETY_WARNING = (
    "Do not approach or attempt to engage any individual. "
    "Submit information directly to the official agency."
)


def fetch_rewards_for_justice_cases(
    limit: int | None = None,
    excluded_source_urls: set[str] | None = None,
) -> list[dict[str, Any]]:
    cases = [
        case
        for post in fetch_wordpress_posts(REWARDS_API_URL, "")
        if (
            case := normalize_rewards_for_justice_post(
                post,
                excluded_source_urls=excluded_source_urls,
            )
        )
    ]
    cases.sort(key=lambda item: item["publishedDate"], reverse=True)
    return cases[:limit] if limit else cases


def normalize_rewards_for_justice_post(
    post: dict[str, Any],
    excluded_source_urls: set[str] | None = None,
) -> dict[str, Any] | None:
    post_id = post.get("id")
    title = post_title(post)
    source_url = clean_text(post.get("link"))
    text = post_text(post)
    reward, reward_text = _reward_details(text)
    image_urls = list(
        dict.fromkeys(
            image_url.replace(
                "https://rewardsforjustice.net:8443/",
                "https://rewardsforjustice.net/",
            )
            for image_url in post_images(post)
        )
    )

    if (
        not post_id
        or not title
        or not source_url
        or source_url in (excluded_source_urls or set())
        or not reward
        or not image_urls
    ):
        return None

    last_verified = datetime.now(UTC).date().isoformat()
    published_date = _date_only(post.get("date_gmt") or post.get("date"))
    modified_date = _date_only(post.get("modified_gmt") or post.get("modified"))

    return {
        "id": f"rfj-{post_id}",
        "title": title,
        "agency": SOURCE_NAME,
        "country": "US",
        "regions": ["Federal"],
        "caseType": _case_type(post),
        "description": _shorten(_description(text, reward_text), 900),
        "reward": reward,
        "rewardText": reward_text,
        "status": "Information Requested",
        "summary": _shorten(text, 1400),
        "warningMessage": SAFETY_WARNING,
        "aliases": [],
        "age": None,
        "dateOfBirth": None,
        "placeOfBirth": None,
        "sex": None,
        "race": None,
        "nationality": None,
        "hair": None,
        "eyes": None,
        "height": None,
        "weight": None,
        "locations": _location_names(post),
        "distinguishingFeatures": None,
        "fieldOffice": "Federal",
        "publishedDate": published_date or modified_date or last_verified,
        "lastVerified": last_verified,
        "sourceUpdatedDate": modified_date or None,
        "sourceUrl": source_url,
        "sourceTitle": f"Rewards for Justice: {title}",
        "sourceAuthor": SOURCE_NAME,
        "imageUrl": image_urls[0],
        "imageUrls": image_urls,
    }


def _reward_details(text: str) -> tuple[int, str | None]:
    for sentence in re.split(r"(?<=[.!?])\s+", text[:1200]):
        if "reward" not in sentence.lower() or "$" not in sentence:
            continue
        match = re.search(
            r"\$\s*([0-9][0-9,.]*)\s*(million|billion)?",
            sentence,
            re.I,
        )
        if not match:
            continue

        try:
            amount = float(match.group(1).replace(",", ""))
        except ValueError:
            continue
        multiplier = {
            "million": 1_000_000,
            "billion": 1_000_000_000,
        }.get((match.group(2) or "").lower(), 1)
        return int(amount * multiplier), _shorten(sentence, 500)
    return 0, None


def _case_type(post: dict[str, Any]) -> str:
    for term in _terms(post):
        if clean_text(term.get("taxonomy")) == "crime-category":
            name = clean_text(term.get("name"))
            if name:
                return name
    return "Reward Information"


def _location_names(post: dict[str, Any]) -> str | None:
    names = [
        clean_text(term.get("name"))
        for term in _terms(post)
        if clean_text(term.get("taxonomy")) in {"location-country", "region"}
    ]
    unique_names = list(dict.fromkeys(name for name in names if name))
    return ", ".join(unique_names) or None


def _terms(post: dict[str, Any]) -> list[dict[str, Any]]:
    embedded = post.get("_embedded")
    groups = embedded.get("wp:term", []) if isinstance(embedded, dict) else []
    return [
        term
        for group in groups if isinstance(groups, list)
        for term in (group if isinstance(group, list) else [])
        if isinstance(term, dict)
    ]


def _description(text: str, reward_text: str | None) -> str:
    remainder = text
    if reward_text and remainder.startswith(reward_text):
        remainder = remainder[len(reward_text) :].strip()
    return remainder or text


def _date_only(value: Any) -> str:
    match = re.match(r"(\d{4}-\d{2}-\d{2})", clean_text(value))
    return match.group(1) if match else ""


def _shorten(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip(" ,.;:-") + "..."
