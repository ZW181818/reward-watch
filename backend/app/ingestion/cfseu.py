from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from .reward_amount import extract_cash_amount
from .wordpress import (
    clean_text,
    fetch_wordpress_posts,
    has_closed_title,
    looks_like_person_name,
    post_images,
    post_text,
    post_title,
    slugify,
    subject_has_later_closure,
)


CFSEU_POSTS_API = "https://cfseu.bc.ca/wp-json/wp/v2/posts"
SOURCE_NAME = "Combined Forces Special Enforcement Unit BC"
SAFETY_WARNING = (
    "Do not approach or attempt to apprehend this person. "
    "Submit information directly to the police agency identified by CFSEU-BC."
)


def fetch_cfseu_bc_wanted_cases(limit: int | None = None) -> list[dict[str, Any]]:
    posts = fetch_wordpress_posts(CFSEU_POSTS_API, "wanted")
    cases = parse_cfseu_posts(posts)
    cases.sort(key=lambda item: str(item.get("publishedDate", "")), reverse=True)
    return cases[:limit] if limit else cases


def parse_cfseu_posts(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    minimum_date = (datetime.now(UTC).date() - timedelta(days=1095)).isoformat()
    last_verified = datetime.now(UTC).date().isoformat()
    cases: list[dict[str, Any]] = []

    for post in posts:
        title = post_title(post)
        published_date = clean_text(post.get("date"))[:10]
        if published_date < minimum_date or not _is_wanted_notice(title):
            continue

        text = post_text(post)
        subjects = _extract_subjects(text)
        images = post_images(post)
        if not subjects or not images:
            continue

        reward = _reward_amount(text)

        for subject in subjects:
            if subject_has_later_closure(subject, post, posts):
                continue

            subject_images = [
                image for image in images if slugify(subject.split()[-1]) in image.lower()
            ] or images
            context = _subject_context(text, subject)
            cases.append(
                {
                    "id": f"cfseu-bc-{post.get('id')}-{slugify(subject)}",
                    "title": subject,
                    "agency": SOURCE_NAME,
                    "country": "Canada",
                    "regions": ["British Columbia"],
                    "caseType": "Wanted Person",
                    "description": _shorten(context, 900),
                    "reward": reward,
                    "rewardText": (
                        f"The official source lists a reward of up to ${reward:,}."
                        if reward
                        else None
                    ),
                    "status": "Open",
                    "summary": _shorten(text, 1400),
                    "warningMessage": SAFETY_WARNING,
                    "aliases": [],
                    "age": _age_for_subject(text, subject),
                    "dateOfBirth": None,
                    "placeOfBirth": None,
                    "sex": _sex_for_subject(context),
                    "race": None,
                    "nationality": None,
                    "hair": None,
                    "eyes": None,
                    "height": None,
                    "weight": None,
                    "locations": _location_for_subject(text, subject),
                    "distinguishingFeatures": None,
                    "fieldOffice": "British Columbia",
                    "publishedDate": published_date or last_verified,
                    "lastVerified": last_verified,
                    "sourceUpdatedDate": clean_text(post.get("modified"))[:10] or None,
                    "sourceUrl": clean_text(post.get("link")),
                    "sourceTitle": title,
                    "sourceAuthor": "CFSEU-BC",
                    "imageUrl": subject_images[0],
                    "imageUrls": subject_images,
                }
            )

    return cases


def _is_wanted_notice(title: str) -> bool:
    lowered = title.lower()
    if has_closed_title(lowered):
        return False
    return "wanted" in lowered or "arrest warrant" in lowered


def _extract_subjects(text: str) -> list[str]:
    name_pattern = r"([A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){1,3})"
    patterns = (
        rf"{name_pattern},?\s+(?:a\s+)?\d{{1,3}}-year-old",
        rf"{name_pattern}\s+was\s+to\s+appear\b",
        rf"warrant\s+(?:has\s+been\s+)?issued\s+for\s+{name_pattern}\b",
    )
    subjects: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            candidate = clean_text(match.group(1))
            if looks_like_person_name(candidate) and candidate not in subjects:
                subjects.append(candidate)
    return subjects


def _subject_context(text: str, subject: str) -> str:
    position = text.lower().find(subject.lower())
    if position < 0:
        return text[:900]
    return text[max(0, position - 100) : position + 900]


def _age_for_subject(text: str, subject: str) -> str | None:
    escaped = re.escape(subject)
    patterns = (
        rf"{escaped},?\s+(?:a\s+)?(\d{{1,3}})-year-old",
        rf"(\d{{1,3}})-year-old\s+{escaped}",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1)
    return None


def _sex_for_subject(text: str) -> str | None:
    match = re.search(r"\b(male|female|man|woman)\b", text, re.I)
    if not match:
        return None
    return "Female" if match.group(1).lower() in {"female", "woman"} else "Male"


def _location_for_subject(text: str, subject: str) -> str:
    escaped = re.escape(subject)
    match = re.search(
        rf"{escaped}.{{0,120}}?(?:reside|from|area of)\s+(?:in\s+|the\s+)?([^.;]+)",
        text,
        re.I,
    )
    return clean_text(match.group(1)) if match else "British Columbia"


def _reward_amount(text: str) -> int:
    return extract_cash_amount(text, require_reward_context=True)


def _shorten(value: str, maximum: int) -> str:
    if len(value) <= maximum:
        return value
    shortened = value[: maximum - 1].rsplit(" ", 1)[0]
    return f"{shortened}."
