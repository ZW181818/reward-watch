from __future__ import annotations

import concurrent.futures
import json
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from .fbi import US_STATE_ABBREVIATIONS
from .wordpress import clean_text


NEWS_URL = "https://www.uspis.gov/news?filters=wanted"
SOURCE_NAME = "United States Postal Inspection Service"
SAFETY_WARNING = (
    "Do not approach or attempt to apprehend any individual. "
    "Submit information directly to the U.S. Postal Inspection Service."
)
USER_AGENT = "RewardWatchMVP0/0.1 (+official-source-research)"
_CLOSED_MARKERS = (
    "has been apprehended",
    "has been arrested",
    "have been arrested",
    "was arrested",
    "were arrested",
    "is no longer wanted",
    "are no longer wanted",
    "suspect was arrested",
    "suspects were arrested",
)


def fetch_uspis_cases(
    limit: int | None = None,
    excluded_source_urls: set[str] | None = None,
) -> list[dict[str, Any]]:
    index_html = _fetch_html(NEWS_URL)
    ajax_url, nonce, locations = parse_catalog_config(index_html)
    first_pages = _fetch_first_catalog_pages(ajax_url, nonce, locations)
    catalog_items = _fetch_remaining_catalog_pages(ajax_url, nonce, first_pages)

    unique_items: dict[int, dict[str, Any]] = {}
    for item in catalog_items:
        item_id = item.get("ID")
        source_url = clean_text(item.get("link"))
        if (
            isinstance(item_id, int)
            and source_url
            and source_url not in (excluded_source_urls or set())
        ):
            unique_items[item_id] = item

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        documents = executor.map(
            _fetch_detail_or_empty,
            (clean_text(item.get("link")) for item in unique_items.values()),
        )
        cases = [
            case
            for item, document in zip(unique_items.values(), documents, strict=True)
            if (case := normalize_uspis_item(item, document))
        ]

    cases.sort(key=lambda item: item["publishedDate"], reverse=True)
    return cases[:limit] if limit else cases


def parse_catalog_config(index_html: str) -> tuple[str, str, list[str]]:
    soup = BeautifulSoup(index_html, "html.parser")
    config_script = soup.find("script", id="uspis-news-js-extra")
    script_text = config_script.get_text(" ", strip=True) if config_script else ""
    match = re.search(r"var\s+news_ajax\s*=\s*(\{.*?\})\s*;", script_text)
    if not match:
        raise ValueError("USPIS news AJAX configuration was not found")

    config = json.loads(match.group(1))
    ajax_url = clean_text(config.get("ajaxurl"))
    nonce = clean_text(config.get("nonce"))
    if not ajax_url or not nonce:
        raise ValueError("USPIS news AJAX configuration is incomplete")

    location_select = soup.select_one('select[name="location"]')
    locations = [
        clean_text(option.get("value"))
        for option in location_select.select("option[value]")
        if clean_text(option.get("value")) not in {"", "0"}
    ] if location_select else []
    if not locations:
        locations = ["national", *US_STATE_ABBREVIATIONS]
    return ajax_url, nonce, locations


def normalize_uspis_item(
    item: dict[str, Any],
    detail_html: str,
) -> dict[str, Any] | None:
    source_url = clean_text(item.get("link"))
    item_id = item.get("ID")
    if not source_url or not isinstance(item_id, int):
        return None

    soup = (
        BeautifulSoup(detail_html, "html.parser")
        if detail_html
        else BeautifulSoup("", "html.parser")
    )
    article = soup.select_one("article.wanted")
    heading = article.select_one("header h1") if article else None
    heading_title = (
        clean_text(heading.get_text(" ", strip=True))
        if heading
        else clean_text(item.get("title"))
    )
    document_title = clean_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
    document_title = re.sub(
        r"\s+[–-]\s+United States Postal Inspection Service$",
        "",
        document_title,
        flags=re.I,
    )
    title = (
        document_title
        if heading_title.endswith(("...", "…")) and document_title
        else heading_title
    )
    if not title:
        return None
    details = article.select_one("section.article .details") if article else None
    detail_text = clean_text(details.get_text(" ", strip=True)) if details else ""
    catalog_text = clean_text(item.get("body"))
    searchable_text = f"{title} {detail_text} {catalog_text}"
    if _is_closed(searchable_text):
        return None

    reward, reward_text = _reward_details(searchable_text)
    image_urls = _image_urls(article, item, source_url)
    summary = _summary(details, catalog_text, reward_text)
    if not reward or not image_urls or len(summary) < 30:
        return None

    catalog_date = _date_value(clean_text(item.get("date")))
    detail_date = _detail_date(article)
    source_updated_date = detail_date or catalog_date
    last_verified = datetime.now(UTC).date().isoformat()
    region = _region(article, item, title)
    case_type = _case_type(title)

    return {
        "id": f"uspis-{item_id}",
        "title": title,
        "agency": SOURCE_NAME,
        "country": "US",
        "regions": [region] if region else ["Federal"],
        "caseType": case_type,
        "description": case_type,
        "reward": reward,
        "rewardText": reward_text,
        "status": "Information Requested",
        "summary": _shorten(summary, 1400),
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
        "locations": region or "Federal",
        "distinguishingFeatures": None,
        "fieldOffice": region or "Federal",
        "publishedDate": catalog_date or source_updated_date or last_verified,
        "lastVerified": last_verified,
        "sourceUpdatedDate": source_updated_date or None,
        "sourceUrl": source_url,
        "sourceTitle": f"USPIS Wanted Poster: {title}",
        "sourceAuthor": SOURCE_NAME,
        "imageUrl": image_urls[0],
        "imageUrls": image_urls,
    }


def _fetch_first_catalog_pages(
    ajax_url: str,
    nonce: str,
    locations: list[str],
) -> list[tuple[str, dict[str, Any]]]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        pages = executor.map(
            lambda location: _fetch_catalog_page(
                ajax_url,
                nonce,
                location=location,
                page=0,
                featured_post=0,
            ),
            locations,
        )
        return list(zip(locations, pages, strict=True))


def _fetch_remaining_catalog_pages(
    ajax_url: str,
    nonce: str,
    first_pages: list[tuple[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    items = [
        item
        for _, response in first_pages
        for item in response.get("news_list", [])
        if isinstance(item, dict)
    ]
    tasks: list[tuple[str, int, int]] = []
    for location, response in first_pages:
        total_pages = int(response.get("totalpages") or 0)
        featured_post = int(response.get("featured_post_id") or 0)
        tasks.extend(
            (location, page, featured_post)
            for page in range(1, total_pages)
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        responses = executor.map(
            lambda task: _fetch_catalog_page(
                ajax_url,
                nonce,
                location=task[0],
                page=task[1],
                featured_post=task[2],
            ),
            tasks,
        )
        items.extend(
            item
            for response in responses
            for item in response.get("news_list", [])
            if isinstance(item, dict)
        )
    return items


def _fetch_catalog_page(
    ajax_url: str,
    nonce: str,
    *,
    location: str,
    page: int,
    featured_post: int,
) -> dict[str, Any]:
    query = urlencode(
        {
            "security": nonce,
            "action": "loadnews",
            "page": page,
            "featuredpost": featured_post,
            "filters": "wanted",
            "tip_category": 0,
            "show_featured": "true",
            "location": location,
        }
    )
    request = Request(
        f"{ajax_url}?{query}",
        headers={
            "Accept": "application/json,text/plain,*/*",
            "Referer": NEWS_URL,
            "User-Agent": USER_AGENT,
        },
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("news_list"), list):
        raise ValueError("USPIS catalog returned an unexpected response")
    return payload


def _fetch_html(url: str) -> str:
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": USER_AGENT,
        },
    )
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def _fetch_detail_or_empty(url: str) -> str:
    try:
        return _fetch_html(url)
    except Exception:
        return ""


def _image_urls(
    article: Any,
    item: dict[str, Any],
    source_url: str,
) -> list[str]:
    candidates = [clean_text(item.get("image"))]
    if article:
        candidates = [
            clean_text(image.get("src") or image.get("data-src"))
            for image in article.select("section.article .photos img")
        ] + candidates

    urls: list[str] = []
    for candidate in candidates:
        if (
            not candidate
            or candidate.startswith("data:")
            or _is_placeholder_image(candidate)
        ):
            continue
        url = re.sub(
            r"-\d+x\d+(?=\.[A-Za-z0-9]+(?:\?.*)?$)",
            "",
            urljoin(source_url, candidate),
        )
        if url not in urls:
            urls.append(url)
    return urls


def _is_placeholder_image(url: str) -> bool:
    filename = urlsplit(url).path.rsplit("/", 1)[-1].casefold()
    return any(marker in filename for marker in ("no_image", "no-image", "placeholder"))


def _summary(details: Any, catalog_text: str, reward_text: str | None) -> str:
    paragraphs = []
    if details:
        paragraphs = [
            clean_text(element.get_text(" ", strip=True))
            for element in details.find_all(["span", "p"], recursive=True)
        ]
    content = " ".join(dict.fromkeys(value for value in paragraphs if value))
    if not content:
        content = catalog_text
    if reward_text and content.startswith(reward_text):
        content = content[len(reward_text) :].strip()
    return content


def _reward_details(text: str) -> tuple[int, str | None]:
    candidates: list[tuple[int, str]] = []
    patterns = (
        r"(?:reward\s+(?:of\s+)?(?:up\s+to\s+)?|up\s+to\s+)\$\s*([0-9][0-9,]*)",
        r"\$\s*([0-9][0-9,]*)\s+(?:cash\s+)?reward",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            amount = int(match.group(1).replace(",", ""))
            candidates.append((amount, clean_text(match.group(0))))
    if not candidates:
        return 0, None
    amount, phrase = max(candidates, key=lambda candidate: candidate[0])
    return amount, phrase


def _detail_date(article: Any) -> str:
    time = article.select_one("header time[datetime]") if article else None
    return _date_value(clean_text(time.get("datetime")) if time else "")


def _date_value(value: str) -> str:
    match = re.match(r"(\d{2})[./](\d{2})[./](\d{4})", value)
    if match:
        month, day, year = match.groups()
        return f"{year}-{month}-{day}"
    iso_match = re.match(r"(\d{4}-\d{2}-\d{2})", value)
    return iso_match.group(1) if iso_match else ""


def _region(article: Any, item: dict[str, Any], title: str) -> str:
    locale = article.select_one("header .post-locale") if article else None
    value = clean_text(locale.get_text(" ", strip=True)) if locale else ""
    if value and value.lower() != "national":
        return _canonical_region(value)

    location = item.get("location")
    if isinstance(location, dict):
        code = clean_text(location.get("value"))
        if code in US_STATE_ABBREVIATIONS:
            return US_STATE_ABBREVIATIONS[code]
        label = clean_text(location.get("label"))
        if label and label.lower() != "national":
            return _canonical_region(label)

    for abbreviation, region in US_STATE_ABBREVIATIONS.items():
        if re.search(rf"(?:,|\b){re.escape(abbreviation)}(?:\b|:)", title):
            return region
    return ""


def _canonical_region(value: str) -> str:
    for region in US_STATE_ABBREVIATIONS.values():
        if value.casefold() == region.casefold():
            return region
    return value


def _case_type(title: str) -> str:
    if ":" in title:
        value = clean_text(title.split(":", 1)[1])
    else:
        parts = re.split(r"\s+for\s+", title, maxsplit=1, flags=re.I)
        value = clean_text(parts[1]) if len(parts) == 2 else "Postal Crime"
    return value.title() if value.isupper() else value


def _is_closed(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _CLOSED_MARKERS)


def _shorten(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip(" ,.;:-") + "..."
