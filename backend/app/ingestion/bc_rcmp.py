from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup, Tag

from .reward_amount import extract_cash_amount
from .wordpress import clean_text, has_closed_title, looks_like_person_name, slugify


BC_RCMP_NEWS_URL = "https://rcmp.ca/en/bc/news"
SOURCE_NAME = "British Columbia RCMP"
SAFETY_WARNING = (
    "Do not approach or attempt to apprehend this person. "
    "Submit information directly to the RCMP."
)


def fetch_bc_rcmp_wanted_cases(limit: int | None = None) -> list[dict[str, Any]]:
    records = discover_bc_wanted_releases(_fetch_html(BC_RCMP_NEWS_URL))
    cases: list[dict[str, Any]] = []

    for record in records:
        case = parse_bc_wanted_release(
            _fetch_html(record["view_node"]),
            source_url=record["view_node"],
            published_date=record.get("field_publish_date"),
            source_author=record.get("field_division_or_detachment"),
            source_location=record.get("field_location"),
        )
        if case:
            cases.append(case)
        if limit and len(cases) >= limit:
            break

    return cases


def discover_bc_wanted_releases(news_html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(news_html, "html.parser")
    settings_script = soup.find(
        "script", attrs={"data-drupal-selector": "drupal-settings-json"}
    )
    if not settings_script:
        raise ValueError("BC RCMP newsroom did not include Drupal settings data")

    settings = json.loads(settings_script.get_text())
    feeds = settings.get("poweb", {}).get("all_news", {})
    if not isinstance(feeds, dict):
        raise ValueError("BC RCMP newsroom did not include its official news feed")

    records: list[dict[str, Any]] = []
    for encoded_feed in feeds.values():
        if not isinstance(encoded_feed, str):
            continue
        payload = json.loads(encoded_feed)
        if isinstance(payload, list):
            records.extend(item for item in payload if isinstance(item, dict))

    candidates = [record for record in records if _is_wanted_record(record)]
    candidates.sort(
        key=lambda record: clean_text(record.get("field_publish_date")), reverse=True
    )
    return [
        {
            "title": clean_text(record.get("title")),
            "view_node": clean_text(record.get("view_node")),
            "field_publish_date": _date_only(record.get("field_publish_date")),
            "field_division_or_detachment": clean_text(
                record.get("field_division_or_detachment")
            ),
            "field_location": clean_text(record.get("field_location")),
        }
        for record in candidates
    ]


def parse_bc_wanted_release(
    release_html: str,
    source_url: str,
    published_date: str | None = None,
    source_author: str | None = None,
    source_location: str | None = None,
) -> dict[str, Any] | None:
    soup = BeautifulSoup(release_html, "html.parser")
    content = soup.find("section", id="s1")
    if not content:
        raise ValueError("BC RCMP wanted release did not include a content section")

    heading = soup.find("h1")
    source_title = clean_text(heading.get_text(" ", strip=True)) if heading else ""
    text = clean_text(content.get_text(" ", strip=True))
    subject = _subject_name(source_title, text, content)
    image_urls = _extract_images(content, source_url)
    if not subject or not image_urls or not _is_still_active(subject, text):
        return None

    last_verified = datetime.now(UTC).date().isoformat()
    author = clean_text(source_author) or _page_author(soup) or SOURCE_NAME
    details = _description_context(text, subject)
    reward = _reward_amount(text)
    node_id = urlsplit(source_url).path.rstrip("/").rsplit("/", 1)[-1]

    return {
        "id": f"rcmp-bc-{slugify(node_id)}-{slugify(subject)}",
        "title": subject,
        "agency": author,
        "country": "Canada",
        "regions": ["British Columbia"],
        "caseType": "Wanted Person",
        "description": _shorten(details, 900),
        "reward": reward,
        "rewardText": (
            f"The official source lists a reward of up to ${reward:,}." if reward else None
        ),
        "status": "Open",
        "summary": _shorten(text.removeprefix("Content "), 1400),
        "warningMessage": SAFETY_WARNING,
        "aliases": _aliases(subject),
        "age": _age(text, subject),
        "dateOfBirth": None,
        "placeOfBirth": None,
        "sex": _sex(details),
        "race": _race(details),
        "nationality": None,
        "hair": _physical_value(details, "hair"),
        "eyes": _physical_value(details, "eyes"),
        "height": _height(details),
        "weight": _weight(details),
        "locations": _location(source_location),
        "distinguishingFeatures": _distinguishing_features(details),
        "fieldOffice": clean_text(source_location) or "British Columbia",
        "publishedDate": _date_only(published_date) or last_verified,
        "lastVerified": last_verified,
        "sourceUpdatedDate": _meta_date(soup, "dcterms.modified") or None,
        "sourceUrl": source_url,
        "sourceTitle": source_title,
        "sourceAuthor": author,
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


def _is_wanted_record(record: dict[str, Any]) -> bool:
    title = clean_text(record.get("title"))
    lowered = title.lower()
    source_url = clean_text(record.get("view_node"))
    if not source_url.startswith("https://rcmp.ca/en/bc/") or has_closed_title(title):
        return False
    if "search warrant" in lowered:
        return False
    return bool(
        re.match(r"^wanted(?:\b|\s*[:\-])", lowered)
        or re.match(r"^warrant issued\b", lowered)
        or "canada-wide warrant issued" in lowered
        or ("wanted" in lowered and any(word in lowered for word in ("locate", "seeking")))
    )


def _subject_name(title: str, text: str, content: Tag) -> str:
    title_patterns = (
        r"^wanted(?:\s+person(?:\s+to\s+locate)?)?\s*[:\-]\s*(.+)$",
        r"^wanted\s+person\s*[:\-]\s*(.+)$",
    )
    for pattern in title_patterns:
        match = re.match(pattern, title, re.I)
        if match:
            candidate = _clean_name(match.group(1))
            if looks_like_person_name(candidate):
                return candidate

    for image in content.find_all("img"):
        alt = clean_text(image.get("alt"))
        candidate = re.sub(r"^(?:photo|image|picture)\s+of\s+", "", alt, flags=re.I)
        candidate = _clean_name(candidate)
        if looks_like_person_name(candidate):
            return candidate

    name_pattern = r"([A-Z][A-Za-z'\-]+(?:\s+(?:[\"'][A-Z][A-Za-z'\-]+[\"']|[A-Z][A-Za-z'\-]+)){1,4})"
    patterns = (
        rf"(?:locate|featuring)\s+(?:\d{{1,3}}-year-old\s+)?{name_pattern}(?=\s+who|\s+for|\s+is|[,.;])",
        rf"warrant\s+(?:has\s+been\s+)?issued\s+for\s+(?:the\s+arrest\s+of\s+)?(?:\d{{1,3}}-year-old\s+)?{name_pattern}(?=\s+after|\s+who|[,.;])",
        rf"(?:\d{{1,3}})-year-old\s+{name_pattern}\s+(?:who\s+is\s+wanted|is\s+wanted)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            candidate = _clean_name(match.group(1))
            if looks_like_person_name(candidate):
                return candidate
    return ""


def _is_still_active(subject: str, text: str) -> bool:
    lowered = text.lower()
    if not any(marker in lowered for marker in ("wanted", "warrant")):
        return False
    if not any(marker in lowered for marker in ("whereabouts", "locate", "public assistance")):
        return False

    escaped = re.escape(subject.lower())
    closed_patterns = (
        rf"{escaped}.{{0,80}}(?:has been|was|is)\s+(?:located|arrested|found|taken into custody)",
        rf"(?:located|arrested|found)\s+{escaped}",
    )
    return not any(re.search(pattern, lowered) for pattern in closed_patterns)


def _extract_images(content: Tag, source_url: str) -> list[str]:
    image_urls: list[str] = []
    for image in content.find_all("img"):
        candidate = clean_text(
            image.get("data-large-file")
            or image.get("data-src")
            or image.get("src")
        )
        if not candidate:
            continue
        image_url = urljoin(source_url, candidate)
        path = urlsplit(image_url).path.lower()
        if not path.endswith((".jpg", ".jpeg", ".png", ".webp")):
            continue
        if any(token in path for token in ("logo", "no-photo", "placeholder")):
            continue
        if image_url not in image_urls:
            image_urls.append(image_url)
    return image_urls


def _description_context(text: str, subject: str) -> str:
    position = text.lower().find(subject.lower())
    if position < 0:
        return text[:900]
    return text[max(0, position - 100) : position + 1000]


def _age(text: str, subject: str) -> str | None:
    escaped = re.escape(subject)
    patterns = (
        rf"(\d{{1,3}})-year-old\s+{escaped}",
        rf"{escaped}\s+is\s+described\s+as:.{{0,100}}?\b(\d{{1,3}})\s+years?\s+old",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1)
    return None


def _height(text: str) -> str | None:
    metric = re.search(r"\b(\d{3})\s*cm\b", text, re.I)
    imperial = re.search(r"\b(\d)\s*(?:feet|foot|['\u2019])\s*(\d{1,2})?", text, re.I)
    if imperial:
        return f"{imperial.group(1)}'{imperial.group(2) or '0'}\""
    return f"{metric.group(1)} cm" if metric else None


def _weight(text: str) -> str | None:
    match = re.search(r"\b(\d{2,3})\s*(?:lb|lbs|pounds)\b", text, re.I)
    return f"{match.group(1)} lbs" if match else None


def _physical_value(text: str, field: str) -> str | None:
    match = re.search(
        rf"\b(black|brown|blond|blonde|red|grey|gray|green|blue|hazel)\s+{field}\b",
        text,
        re.I,
    )
    return match.group(1).title() if match else None


def _sex(text: str) -> str | None:
    match = re.search(r"\b(male|female|man|woman)\b", text, re.I)
    if not match:
        return None
    return "Female" if match.group(1).lower() in {"female", "woman"} else "Male"


def _race(text: str) -> str | None:
    match = re.search(r"\b(Indigenous|White|Black|Asian|South Asian)\s+(?:male|female|man|woman)\b", text, re.I)
    return match.group(1).title() if match else None


def _distinguishing_features(text: str) -> str | None:
    match = re.search(r"((?:tattoo|scar)[^.;]{0,180})", text, re.I)
    return clean_text(match.group(1)) if match else None


def _reward_amount(text: str) -> int:
    return extract_cash_amount(text, require_reward_context=True)


def _aliases(subject: str) -> list[str]:
    return [clean_text(value) for value in re.findall(r'["\u201c]([^"\u201d]+)["\u201d]', subject)]


def _location(value: str | None) -> str:
    location = clean_text(value)
    return f"{location}, British Columbia" if location else "British Columbia"


def _page_author(soup: BeautifulSoup) -> str:
    for selector in (".field--name-field-from", ".gc-byline"):
        element = soup.select_one(selector)
        if element:
            value = clean_text(element.get_text(" ", strip=True))
            if value:
                return re.sub(r"^From:\s*", "", value, flags=re.I)
    return ""


def _meta_date(soup: BeautifulSoup, name: str) -> str:
    meta = soup.find("meta", attrs={"name": name})
    return _date_only(meta.get("content")) if meta else ""


def _date_only(value: Any) -> str:
    match = re.search(r"(\d{4}-\d{2}-\d{2})", clean_text(value))
    return match.group(1) if match else ""


def _clean_name(value: str) -> str:
    return clean_text(re.sub(r"\s+(?:update|file)\b.*$", "", value, flags=re.I)).strip(" .:-")


def _shorten(value: str, maximum: int) -> str:
    if len(value) <= maximum:
        return value
    shortened = value[: maximum - 1].rsplit(" ", 1)[0]
    return f"{shortened}."
