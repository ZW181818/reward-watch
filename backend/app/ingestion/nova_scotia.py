from __future__ import annotations

import concurrent.futures
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from .wordpress import clean_text, slugify


REWARDS_INDEX_URL = "https://novascotia.ca/just/public_safety/rewards/"
SOURCE_NAME = "Nova Scotia Department of Justice"
SAFETY_WARNING = (
    "Do not approach any individual. Submit information directly to the official agency."
)
USER_AGENT = "RewardWatchMVP0/0.1 (+official-source-research)"


def fetch_nova_scotia_reward_cases(
    limit: int | None = None,
) -> list[dict[str, Any]]:
    index_html, _ = _fetch_html(REWARDS_INDEX_URL)
    source_urls = discover_nova_scotia_case_urls(index_html)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        documents = executor.map(_fetch_case_document, source_urls)
        cases = [
            case
            for source_url, document in zip(source_urls, documents, strict=True)
            if document
            and (
                case := parse_nova_scotia_reward_case(
                    document[0],
                    source_url=source_url,
                    last_modified=document[1],
                )
            )
        ]

    cases.sort(key=lambda item: item["publishedDate"], reverse=True)
    return cases[:limit] if limit else cases


def discover_nova_scotia_case_urls(index_html: str) -> list[str]:
    soup = BeautifulSoup(index_html, "html.parser")
    urls: list[str] = []
    for anchor in soup.select('a[href*="case_detail"]'):
        url = urljoin(REWARDS_INDEX_URL, clean_text(anchor.get("href")))
        if url not in urls:
            urls.append(url)
    return urls


def parse_nova_scotia_reward_case(
    case_html: str,
    source_url: str,
    last_modified: str | None = None,
) -> dict[str, Any] | None:
    soup = BeautifulSoup(case_html, "html.parser")
    main = soup.select_one("#main")
    if not main:
        return None

    heading = main.find("h2")
    title = clean_text(heading.get_text(" ", strip=True)) if heading else ""
    cells = main.find_all("td")
    details = cells[-1] if cells else main
    text = clean_text(details.get_text(" ", strip=True))
    reward, reward_text = _reward_details(text)
    image_urls = _case_images(main, source_url)
    if not title or not reward or not image_urls or len(text) < 50:
        return None

    case_type_node = details.find("strong")
    case_type = (
        clean_text(case_type_node.get_text(" ", strip=True))
        if case_type_node
        else "Major Unsolved Crime"
    )
    last_verified = datetime.now(UTC).date().isoformat()
    updated_date = _http_date(last_modified)

    source_parts = urlsplit(source_url)
    source_identity = f"{source_parts.path.rsplit('/', 1)[-1]}-{source_parts.query}"

    return {
        "id": f"ns-reward-{slugify(source_identity)}",
        "title": title,
        "agency": SOURCE_NAME,
        "country": "Canada",
        "regions": ["Nova Scotia"],
        "caseType": case_type,
        "description": _shorten(_description(details, reward_text), 900),
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
        "locations": "Nova Scotia",
        "distinguishingFeatures": None,
        "fieldOffice": "Nova Scotia",
        "publishedDate": updated_date or last_verified,
        "lastVerified": last_verified,
        "sourceUpdatedDate": updated_date or None,
        "sourceUrl": source_url,
        "sourceTitle": f"Rewards for Major Unsolved Crimes: {title}",
        "sourceAuthor": SOURCE_NAME,
        "imageUrl": image_urls[0],
        "imageUrls": image_urls,
    }


def _fetch_case_document(url: str) -> tuple[str, str | None] | None:
    try:
        return _fetch_html(url)
    except HTTPError as error:
        if error.code == 404:
            return None
        raise


def _fetch_html(url: str) -> tuple[str, str | None]:
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-CA,en;q=0.9",
            "User-Agent": USER_AGENT,
        },
    )
    with urlopen(request, timeout=30) as response:
        return (
            response.read().decode("utf-8"),
            response.headers.get("Last-Modified"),
        )


def _case_images(main: Any, source_url: str) -> list[str]:
    urls: list[str] = []
    for image in main.select("img[src]"):
        candidate = clean_text(image.get("src"))
        if not candidate:
            continue
        raw_url = urljoin(source_url, candidate)
        parts = urlsplit(raw_url)
        url = urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                quote(parts.path, safe="/%:@-._~"),
                parts.query,
                parts.fragment,
            )
        )
        if urlsplit(url).path.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            if url not in urls:
                urls.append(url)
    return urls


def _reward_details(text: str) -> tuple[int, str | None]:
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if "reward" not in sentence.lower() or "$" not in sentence:
            continue
        match = re.search(r"\$\s*([0-9][0-9,]*)", sentence)
        if match:
            return int(match.group(1).replace(",", "")), _shorten(sentence, 500)
    return 0, None


def _description(details: Any, reward_text: str | None) -> str:
    paragraphs = [
        clean_text(paragraph.get_text(" ", strip=True))
        for paragraph in details.find_all("p")
    ]
    candidates = [
        paragraph
        for paragraph in paragraphs
        if paragraph
        and paragraph != reward_text
        and "should call" not in paragraph.lower()
        and "reward is payable" not in paragraph.lower()
        and "police believe" not in paragraph.lower()
    ]
    return " ".join(candidates) or clean_text(details.get_text(" ", strip=True))


def _http_date(value: str | None) -> str:
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError):
        return ""


def _shorten(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip(" ,.;:-") + "..."
