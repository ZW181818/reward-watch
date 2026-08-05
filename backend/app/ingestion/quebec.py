from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup, Tag


QUEBEC_FUGITIVES_URL = "https://www.fugitifsquebec.com/en/"
SOURCE_NAME = "Fugitifs Quebec"
SAFETY_WARNING = (
    "These individuals may be dangerous and armed. Do not intervene. "
    "Submit information directly to the official police service."
)


def fetch_quebec_fugitive_cases(limit: int | None = None) -> list[dict[str, Any]]:
    index_html = _fetch_html(QUEBEC_FUGITIVES_URL)
    profile_urls = discover_active_profile_urls(index_html, QUEBEC_FUGITIVES_URL)
    if limit:
        profile_urls = profile_urls[:limit]

    cases: list[dict[str, Any]] = []
    for profile_url in profile_urls:
        case = parse_quebec_profile(_fetch_html(profile_url), profile_url)
        if case:
            cases.append(case)

    return cases


def discover_active_profile_urls(index_html: str, source_url: str) -> list[str]:
    soup = BeautifulSoup(index_html, "html.parser")
    profile_urls: list[str] = []

    for anchor in soup.select("a.item__link[href]"):
        href = _clean_text(anchor.get("href"))
        if "/en/fugitive/" not in href:
            continue

        card_text = _clean_text(anchor.get_text(" ", strip=True)).lower()
        if _is_resolved_text(card_text):
            continue

        profile_url = urljoin(source_url, href)
        if profile_url not in profile_urls:
            profile_urls.append(profile_url)

    if not profile_urls:
        raise ValueError("Fugitifs Quebec index did not include active profiles")

    return profile_urls


def parse_quebec_profile(
    profile_html: str, source_url: str
) -> dict[str, Any] | None:
    soup = BeautifulSoup(profile_html, "html.parser")
    content = soup.select_one(".file-content")
    if not content:
        raise ValueError("Fugitifs Quebec profile did not include file content")

    state = content.select_one(".file-state")
    if content.select_one(".info--arrested") or (
        state and _is_resolved_text(_clean_text(state.get_text(" ", strip=True)).lower())
    ):
        return None

    title_element = content.find("h1")
    title = _clean_text(title_element.get_text(" ", strip=True)) if title_element else ""
    image_urls = _extract_images(content, source_url)
    if not title or not image_urls:
        return None

    fields = _extract_base_fields(content)
    summary = _extract_summary(content)
    wanted_for = _section_value(content.select_one(".searched-for"))
    agency = _section_value(content.select_one(".police-force")) or SOURCE_NAME
    if not summary or not wanted_for:
        return None

    last_verified = datetime.now(UTC).date().isoformat()
    published_date = _posting_date(content) or last_verified
    source_updated_date = _meta_date(soup, "article:modified_time") or published_date
    profile_slug = urlsplit(source_url).path.rstrip("/").rsplit("/", 1)[-1]

    return {
        "id": f"fq-{_slugify(profile_slug or title)}",
        "title": title,
        "agency": agency,
        "country": "Canada",
        "regions": ["Quebec"],
        "caseType": "Wanted Person",
        "description": wanted_for,
        "reward": 0,
        "rewardText": None,
        "status": "Open",
        "summary": summary,
        "warningMessage": SAFETY_WARNING,
        "aliases": [],
        "age": None,
        "dateOfBirth": _optional_value(fields.get("date of birth")),
        "placeOfBirth": None,
        "sex": _title_value(fields.get("gender")),
        "race": None,
        "nationality": _optional_value(fields.get("citizenship")),
        "hair": _title_value(fields.get("hair")),
        "eyes": _title_value(fields.get("eyes")),
        "height": _optional_value(fields.get("height")),
        "weight": _optional_value(fields.get("weight")),
        "locations": "Quebec",
        "distinguishingFeatures": None,
        "fieldOffice": "Quebec",
        "publishedDate": published_date,
        "lastVerified": last_verified,
        "sourceUpdatedDate": source_updated_date,
        "sourceUrl": source_url,
        "sourceTitle": f"Quebec's Most Wanted Fugitives: {title}",
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


def _extract_base_fields(content: Tag) -> dict[str, str]:
    fields: dict[str, str] = {}
    for row in content.select(".base-infos-wrapper .base-infos"):
        paragraphs = row.find_all("p", recursive=False)
        if len(paragraphs) < 2:
            continue
        label = _clean_text(paragraphs[0].get_text(" ", strip=True)).rstrip(":").lower()
        value = _clean_text(paragraphs[1].get_text(" ", strip=True))
        if label and value:
            fields[label] = value
    return fields


def _extract_summary(content: Tag) -> str:
    summary = content.select_one(".file-synopsis .wysi")
    return _clean_text(summary.get_text(" ", strip=True)) if summary else ""


def _section_value(section: Tag | None) -> str:
    if not section:
        return ""
    paragraphs = section.find_all("p")
    return _clean_text(paragraphs[-1].get_text(" ", strip=True)) if len(paragraphs) > 1 else ""


def _extract_images(content: Tag, source_url: str) -> list[str]:
    image_urls: list[str] = []
    for anchor in content.select('[data-fancybox="fugitive-gallery"]'):
        candidate = _clean_text(anchor.get("data-src") or anchor.get("href"))
        image_url = urljoin(source_url, candidate)
        path = urlsplit(image_url).path.lower()
        if not path.endswith((".jpg", ".jpeg", ".png", ".webp")):
            continue
        if image_url not in image_urls:
            image_urls.append(image_url)
    return image_urls


def _posting_date(content: Tag) -> str:
    for paragraph in content.find_all("p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        match = re.match(r"Posting date:\s*(.+)$", text, re.IGNORECASE)
        if match:
            return _parse_english_date(match.group(1))
    return ""


def _parse_english_date(value: str) -> str:
    for pattern in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(_clean_text(value), pattern).date().isoformat()
        except ValueError:
            continue
    return ""


def _meta_date(soup: BeautifulSoup, property_name: str) -> str:
    meta = soup.find("meta", attrs={"property": property_name})
    if not meta:
        return ""
    match = re.search(r"(\d{4}-\d{2}-\d{2})", _clean_text(meta.get("content")))
    return match.group(1) if match else ""


def _is_resolved_text(value: str) -> bool:
    normalized = _ascii_text(value).lower()
    return any(
        marker in normalized
        for marker in ("arretee", "arrete le", "arrested", "captured")
    )


def _optional_value(value: Any) -> str | None:
    cleaned = _clean_text(value)
    return cleaned or None


def _title_value(value: Any) -> str | None:
    cleaned = _optional_value(value)
    return cleaned.title() if cleaned else None


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\u00a0", " ")).strip()


def _ascii_text(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", _ascii_text(value).lower()).strip("-")
    return slug or "unknown"
