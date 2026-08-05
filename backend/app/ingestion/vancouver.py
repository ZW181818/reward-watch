from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from .reward_amount import extract_cash_amount
from .wordpress import (
    clean_text,
    fetch_wordpress_posts,
    gallery_subject_images,
    has_closed_title,
    looks_like_person_name,
    post_images,
    post_text,
    post_title,
    slugify,
    subject_has_later_closure,
)


VPD_POSTS_API = "https://vpd.ca/wp-json/wp/v2/posts"
SOURCE_NAME = "Vancouver Police Department"
SAFETY_WARNING = (
    "Do not approach or attempt to apprehend this person. "
    "Submit information directly to the Vancouver Police Department."
)


def fetch_vancouver_wanted_cases(limit: int | None = None) -> list[dict[str, Any]]:
    posts = fetch_wordpress_posts(VPD_POSTS_API, "wanted")
    cases = parse_vancouver_posts(posts)
    cases.sort(key=lambda item: str(item.get("publishedDate", "")), reverse=True)
    return cases[:limit] if limit else cases


def parse_vancouver_posts(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    minimum_date = (datetime.now(UTC).date() - timedelta(days=1095)).isoformat()
    last_verified = datetime.now(UTC).date().isoformat()
    cases: list[dict[str, Any]] = []

    for post in posts:
        title = post_title(post)
        lowered_title = title.lower()
        published_date = clean_text(post.get("date"))[:10]
        if published_date < minimum_date or not _is_wanted_notice(lowered_title):
            continue

        text = post_text(post)
        gallery = gallery_subject_images(post)
        subjects = list(gallery) or _extract_subjects(text)
        all_images = post_images(post)

        for subject in subjects:
            if not looks_like_person_name(subject):
                continue
            if subject_has_later_closure(subject, post, posts):
                continue

            image_urls = gallery.get(subject, [])
            if not image_urls and len(subjects) == 1:
                image_urls = all_images
            if not image_urls:
                continue

            context = _subject_context(text, subject)
            cases.append(
                {
                    "id": f"vpd-{post.get('id')}-{slugify(subject)}",
                    "title": subject,
                    "agency": SOURCE_NAME,
                    "country": "Canada",
                    "regions": ["British Columbia"],
                    "caseType": "Wanted Person",
                    "description": _shorten(context, 900),
                    "reward": (reward := _reward_amount(context)),
                    "rewardText": (
                        f"The official source lists a reward of up to ${reward:,}."
                        if reward
                        else None
                    ),
                    "status": "Open",
                    "summary": _shorten(text, 1400),
                    "warningMessage": SAFETY_WARNING,
                    "aliases": _aliases(subject),
                    "age": _age_for_subject(text, subject),
                    "dateOfBirth": None,
                    "placeOfBirth": None,
                    "sex": None,
                    "race": None,
                    "nationality": None,
                    "hair": _physical_value(context, "hair"),
                    "eyes": _physical_value(context, "eyes"),
                    "height": _height(context),
                    "weight": _weight(context),
                    "locations": "Vancouver, British Columbia",
                    "distinguishingFeatures": None,
                    "fieldOffice": "Vancouver",
                    "publishedDate": published_date or last_verified,
                    "lastVerified": last_verified,
                    "sourceUpdatedDate": clean_text(post.get("modified"))[:10] or None,
                    "sourceUrl": clean_text(post.get("link")),
                    "sourceTitle": title,
                    "sourceAuthor": SOURCE_NAME,
                    "imageUrl": image_urls[0],
                    "imageUrls": image_urls,
                }
            )

    return cases


def _is_wanted_notice(title: str) -> bool:
    if "wanted" not in title or has_closed_title(title):
        return False
    return any(
        marker in title
        for marker in ("search", "locate", "seek", "looking", "warrant", "appeal")
    )


def _extract_subjects(text: str) -> list[str]:
    name_pattern = r"([A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){1,3})"
    patterns = (
        rf"(?:locate|searching for)\s+(?:\d{{1,3}}-year-old\s+)?{name_pattern}(?=,|\s+who\s+is\s+wanted)",
        rf"(\d{{1,3}})-year-old\s+{name_pattern}(?=,|\s+who|\s+is)",
    )
    subjects: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            candidate = clean_text(match.group(match.lastindex or 1))
            if candidate.isdigit() and match.lastindex and match.lastindex >= 2:
                candidate = clean_text(match.group(2))
            if looks_like_person_name(candidate) and candidate not in subjects:
                subjects.append(candidate)
    return subjects


def _subject_context(text: str, subject: str) -> str:
    position = text.lower().find(subject.lower())
    if position < 0:
        return text[:900]
    return text[max(0, position - 120) : position + 900]


def _age_for_subject(text: str, subject: str) -> str | None:
    escaped = re.escape(subject)
    patterns = (
        rf"(\d{{1,3}})-year-old\s+{escaped}",
        rf"{escaped},?\s+(\d{{1,3}})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _height(text: str) -> str | None:
    match = re.search(r"\b(\d)\s*(?:feet|foot|['\u2019])\s*(\d{1,2})?", text, re.I)
    if not match:
        return None
    inches = match.group(2) or "0"
    return f"{match.group(1)}'{inches}\""


def _weight(text: str) -> str | None:
    match = re.search(r"\b(\d{2,3})\s*(?:pounds|lbs?)\b", text, re.I)
    return f"{match.group(1)} lbs" if match else None


def _physical_value(text: str, field: str) -> str | None:
    match = re.search(
        rf"\b(black|brown|blond|blonde|red|grey|gray|green|blue|hazel)\s+{field}\b",
        text,
        re.I,
    )
    return match.group(1).title() if match else None


def _reward_amount(text: str) -> int:
    return extract_cash_amount(text, require_reward_context=True)


def _aliases(subject: str) -> list[str]:
    return [clean_text(value) for value in re.findall(r'["\u201c]([^"\u201d]+)["\u201d]', subject)]


def _shorten(value: str, maximum: int) -> str:
    if len(value) <= maximum:
        return value
    shortened = value[: maximum - 1].rsplit(" ", 1)[0]
    return f"{shortened}."
