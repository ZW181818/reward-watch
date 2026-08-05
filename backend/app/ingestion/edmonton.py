from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup, Tag

from .reward_amount import extract_cash_amount

EDMONTON_MOST_WANTED_URL = (
    "https://www.edmontonpolice.ca/CrimeFiles/EdmontonsMostWanted"
)
SOURCE_NAME = "Edmonton Police Service"
SAFETY_WARNING = (
    "Do not approach or attempt to apprehend this person. "
    "Submit information directly to the Edmonton Police Service."
)


def fetch_edmonton_most_wanted_cases(
    limit: int | None = None,
) -> list[dict[str, Any]]:
    index_html = _fetch_html(EDMONTON_MOST_WANTED_URL)
    profile_urls = discover_edmonton_profile_urls(
        index_html, EDMONTON_MOST_WANTED_URL
    )
    if limit:
        profile_urls = profile_urls[:limit]

    cases: list[dict[str, Any]] = []
    for profile_url in profile_urls:
        case = parse_edmonton_profile(_fetch_html(profile_url), profile_url)
        if case:
            cases.append(case)
    return cases


def discover_edmonton_profile_urls(index_html: str, source_url: str) -> list[str]:
    soup = BeautifulSoup(index_html, "html.parser")
    profile_urls: list[str] = []

    for anchor in soup.select("#mostWantedListing .mostWanted .info h2 a[href]"):
        profile_url = urljoin(source_url, _clean_text(anchor.get("href")))
        if "/CrimeFiles/EdmontonsMostWanted/" not in profile_url:
            continue
        if profile_url not in profile_urls:
            profile_urls.append(profile_url)

    if not profile_urls:
        raise ValueError("Edmonton most-wanted index did not include active profiles")
    return profile_urls


def parse_edmonton_profile(
    profile_html: str, source_url: str
) -> dict[str, Any] | None:
    soup = BeautifulSoup(profile_html, "html.parser")
    profile = soup.select_one("#mostWanted")
    if not profile:
        raise ValueError("Edmonton profile did not include most-wanted content")

    title_element = profile.find("h1")
    title = _clean_text(title_element.get_text(" ", strip=True)) if title_element else ""
    image_urls = _extract_images(profile, source_url)
    wanted_for = _element_text(profile.select_one("#content"))
    if not title or not image_urls or not wanted_for:
        return None

    physical_description = _element_text(profile.select_one("#description"))
    summary = wanted_for
    if physical_description:
        summary += f" Physical description published by the agency: {physical_description}"

    last_verified = datetime.now(UTC).date().isoformat()
    published_date = _posted_date(soup) or last_verified
    source_updated_date = _meta_date(soup, "SCLastUpdatedDate") or published_date
    profile_slug = urlsplit(source_url).path.rstrip("/").rsplit("/", 1)[-1]

    return {
        "id": f"eps-{_slugify(profile_slug or title)}",
        "title": title,
        "agency": SOURCE_NAME,
        "country": "Canada",
        "regions": ["Alberta"],
        "caseType": "Wanted Person",
        "description": wanted_for,
        "reward": (reward := _reward_amount(wanted_for)),
        "rewardText": (
            f"The official source lists a reward of up to ${reward:,}." if reward else None
        ),
        "status": "Open",
        "summary": summary,
        "warningMessage": SAFETY_WARNING,
        "aliases": [],
        "age": _field_value(profile.select_one("#age")),
        "dateOfBirth": None,
        "placeOfBirth": None,
        "sex": None,
        "race": None,
        "nationality": None,
        "hair": _physical_value(physical_description, "hair"),
        "eyes": _physical_value(physical_description, "eyes"),
        "height": _field_value(profile.select_one("#height")),
        "weight": _field_value(profile.select_one("#weight")),
        "locations": "Edmonton, Alberta",
        "distinguishingFeatures": physical_description or None,
        "fieldOffice": "Edmonton",
        "publishedDate": published_date,
        "lastVerified": last_verified,
        "sourceUpdatedDate": source_updated_date,
        "sourceUrl": source_url,
        "sourceTitle": f"Edmonton's Most Wanted: {title}",
        "sourceAuthor": SOURCE_NAME,
        "imageUrl": image_urls[0],
        "imageUrls": image_urls,
    }


def _fetch_html(url: str) -> str:
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-CA,en;q=0.9",
            "User-Agent": "RewardWatchMVP0/0.1 (+official-source-research)",
        },
    )
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def _extract_images(profile: Tag, source_url: str) -> list[str]:
    image_urls: list[str] = []
    for anchor in profile.select("#Image1 a[href], #images a[href]"):
        href = _clean_text(anchor.get("href"))
        if not href:
            continue
        image_url = urljoin(source_url, href)
        if not urlsplit(image_url).path.lower().endswith(
            (".jpg", ".jpeg", ".png", ".webp")
        ):
            continue
        if image_url not in image_urls:
            image_urls.append(image_url)
    return image_urls


def _field_value(element: Tag | None) -> str | None:
    if not element:
        return None
    label = element.select_one(".FieldTitle")
    if label:
        label.extract()
    value = _clean_text(element.get_text(" ", strip=True))
    return value or None


def _physical_value(description: str, field: str) -> str | None:
    if not description:
        return None
    match = re.search(rf"([a-z]+(?:\s+[a-z]+)?)\s+{field}\b", description, re.IGNORECASE)
    return match.group(1).title() if match else None


def _posted_date(soup: BeautifulSoup) -> str:
    element = soup.select_one(".datePosted")
    if not element:
        return ""
    value = re.sub(
        r"^Date Posted:\s*", "", _clean_text(element.get_text(" ", strip=True)), flags=re.I
    )
    try:
        return datetime.strptime(value, "%d-%b-%Y").date().isoformat()
    except ValueError:
        return ""


def _meta_date(soup: BeautifulSoup, name: str) -> str:
    meta = soup.find("meta", attrs={"name": name})
    if not meta:
        return ""
    match = re.match(r"(\d{4})/(\d{2})/(\d{2})", _clean_text(meta.get("content")))
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}" if match else ""


def _reward_amount(value: str) -> int:
    return extract_cash_amount(value, require_reward_context=True)


def _element_text(element: Tag | None) -> str:
    return _clean_text(element.get_text(" ", strip=True)) if element else ""


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\u00a0", " ")).strip()


def _slugify(value: str) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug or "unknown"
