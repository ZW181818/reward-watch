from __future__ import annotations

import concurrent.futures
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from .fbi import US_STATE_ABBREVIATIONS
from .reward_amount import extract_cash_amount
from .wordpress import clean_text, slugify


PROFILED_FUGITIVES_URL = (
    "https://prod.usmarshals.gov/what-we-do/fugitive-apprehension/profiled-fugitives"
)
SOURCE_NAME = "U.S. Marshals Service"
SAFETY_WARNING = (
    "Do not approach or attempt to apprehend any individual. "
    "Submit information directly to the U.S. Marshals Service."
)
USER_AGENT = "RewardWatchMVP0/0.1 (+official-source-research)"
_CLOSED_MARKERS = (
    "apprehended",
    "captured",
    "deceased",
    "surrendered",
    "taken into custody",
)


def fetch_us_marshals_cases(limit: int | None = None) -> list[dict[str, Any]]:
    first_page = _fetch_html(f"{PROFILED_FUGITIVES_URL}?page=0")
    page_count = discover_page_count(first_page)

    index_documents = [first_page]
    if page_count > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            index_documents.extend(
                executor.map(
                    _fetch_html,
                    (
                        f"{PROFILED_FUGITIVES_URL}?page={page}"
                        for page in range(1, page_count)
                    ),
                )
            )

    profile_urls = list(
        dict.fromkeys(
            url
            for document in index_documents
            for url in discover_profile_urls(document)
        )
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        documents = executor.map(_fetch_html, profile_urls)
        cases = [
            case
            for source_url, document in zip(profile_urls, documents, strict=True)
            if (case := parse_us_marshals_profile(document, source_url))
        ]

    cases.sort(key=lambda item: item["publishedDate"], reverse=True)
    return cases[:limit] if limit else cases


def discover_page_count(index_html: str) -> int:
    soup = BeautifulSoup(index_html, "html.parser")
    pages = [0]
    for anchor in soup.select('main a[href*="page="]'):
        query = parse_qs(urlsplit(anchor.get("href", "")).query)
        raw_page = query.get("page", [""])[0]
        if raw_page.isdigit():
            pages.append(int(raw_page))
    return max(pages) + 1


def discover_profile_urls(index_html: str) -> list[str]:
    soup = BeautifulSoup(index_html, "html.parser")
    urls: list[str] = []
    for anchor in soup.select('main a[href*="/what-we-do/fugitive/local/"]'):
        url = urljoin(PROFILED_FUGITIVES_URL, clean_text(anchor.get("href")))
        if url not in urls:
            urls.append(url)
    return urls


def parse_us_marshals_profile(
    profile_html: str,
    source_url: str,
) -> dict[str, Any] | None:
    soup = BeautifulSoup(profile_html, "html.parser")
    heading = soup.select_one("main h1") or soup.find("h1")
    title = clean_text(heading.get_text(" ", strip=True)) if heading else ""
    fields = _profile_fields(soup)
    reward_text = fields.get("Reward", "")
    reward = _reward_amount(reward_text)
    image_urls = _profile_images(soup, source_url)
    case_outline = fields.get("Case outline", "")

    if not title or not reward or not image_urls or len(case_outline) < 30:
        return None

    public_source_url = source_url.replace(
        "https://prod.usmarshals.gov", "https://www.usmarshals.gov"
    ).replace("https://edit.usmarshals.gov", "https://www.usmarshals.gov")
    published_date = _meta_date(soup, "article:published_time")
    modified_date = _meta_date(soup, "article:modified_time")
    last_verified = datetime.now(UTC).date().isoformat()
    wanted_in = fields.get("Wanted In", "")

    return {
        "id": f"usms-{slugify(urlsplit(source_url).path.rsplit('/', 1)[-1])}",
        "title": title,
        "agency": SOURCE_NAME,
        "country": "US",
        "regions": _regions(wanted_in, case_outline),
        "caseType": "Wanted Person",
        "description": fields.get("Wanted For") or None,
        "reward": reward,
        "rewardText": reward_text,
        "status": _status(soup, case_outline),
        "summary": _shorten(case_outline, 1400),
        "warningMessage": SAFETY_WARNING,
        "aliases": _aliases(fields.get("Aliases", "")),
        "age": None,
        "dateOfBirth": fields.get("Date of Birth") or None,
        "placeOfBirth": fields.get("Place of Birth") or None,
        "sex": fields.get("Sex") or None,
        "race": fields.get("Race and Ethnicity") or None,
        "nationality": None,
        "hair": fields.get("Hair") or None,
        "eyes": fields.get("Eyes") or None,
        "height": fields.get("Height") or None,
        "weight": fields.get("Weight") or None,
        "locations": wanted_in or None,
        "distinguishingFeatures": fields.get("Scar/Tattoo") or None,
        "fieldOffice": wanted_in or "Federal",
        "publishedDate": published_date or modified_date or last_verified,
        "lastVerified": last_verified,
        "sourceUpdatedDate": modified_date or None,
        "sourceUrl": public_source_url,
        "sourceTitle": f"U.S. Marshals Profiled Fugitive: {title}",
        "sourceAuthor": SOURCE_NAME,
        "imageUrl": image_urls[0],
        "imageUrls": image_urls,
    }


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
        return response.read().decode("utf-8")


def _profile_fields(soup: BeautifulSoup) -> dict[str, str]:
    fields: dict[str, str] = {}
    for block in soup.select(".fugitivedetails-block"):
        label = block.select_one(".fugitivedetails-label")
        content = block.select_one(".fugitivedetails-content")
        if not label or not content:
            continue
        fields[clean_text(label.get_text(" ", strip=True))] = clean_text(
            content.get_text(" ", strip=True)
        )
    return fields


def _profile_images(soup: BeautifulSoup, source_url: str) -> list[str]:
    urls: list[str] = []
    selector = (
        ".slick--field-fugitive-image-asset-file img, "
        ".block-field-blocknodefugitivefield-fugitive-image-asset-file img"
    )
    for image in soup.select(selector):
        candidate = clean_text(image.get("data-src") or image.get("src"))
        if not candidate or candidate.startswith("data:"):
            continue
        url = urljoin(source_url, candidate).replace(
            "https://edit.usmarshals.gov", "https://prod.usmarshals.gov"
        )
        if url not in urls:
            urls.append(url)
    return urls


def _reward_amount(value: str) -> int:
    return extract_cash_amount(value)


def _status(soup: BeautifulSoup, case_outline: str) -> str:
    image_text = " ".join(
        clean_text(image.get("alt"))
        for image in soup.select(
            ".slick--field-fugitive-image-asset-file img, "
            ".block-field-blocknodefugitivefield-fugitive-image-asset-file img"
        )
    ).lower()
    if any(marker in image_text for marker in _CLOSED_MARKERS):
        return "Closed"

    opening_update = case_outline[:300].lower()
    if ("update" in opening_update or "has been" in opening_update) and any(
        marker in opening_update for marker in _CLOSED_MARKERS
    ):
        return "Closed"
    return "Open"


def _regions(wanted_in: str, case_outline: str) -> list[str]:
    searchable = f"{wanted_in} {case_outline[:500]}"
    regions: list[str] = []
    for abbreviation in re.findall(r"(?:,|\b)([A-Z]{2})(?:\b|$)", searchable):
        region = US_STATE_ABBREVIATIONS.get(abbreviation)
        if region and region not in regions:
            regions.append(region)
    for region in US_STATE_ABBREVIATIONS.values():
        if re.search(rf"\b{re.escape(region)}\b", searchable, re.I):
            if region not in regions:
                regions.append(region)
    return regions or ["Federal"]


def _aliases(value: str) -> list[str]:
    return [
        alias
        for alias in (clean_text(part).strip('"\'') for part in value.split(","))
        if alias
    ]


def _meta_date(soup: BeautifulSoup, property_name: str) -> str:
    meta = soup.find("meta", attrs={"property": property_name})
    value = clean_text(meta.get("content")) if meta else ""
    match = re.match(r"(\d{4}-\d{2}-\d{2})", value)
    return match.group(1) if match else ""


def _shorten(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip(" ,.;:-") + "..."
