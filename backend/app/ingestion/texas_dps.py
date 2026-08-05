from __future__ import annotations

import base64
import concurrent.futures
import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from .reward_amount import extract_cash_amount
from .wordpress import clean_text


INDEX_URLS = (
    "https://www.dps.texas.gov/Texas10MostWanted/MostWanted/fugitives",
    "https://www.dps.texas.gov/Texas10MostWanted/MostWanted/sexOffenders",
    "https://www.dps.texas.gov/Texas10MostWanted/MostWanted/CriminalIllegalImmigrants",
    "https://www.dps.texas.gov/Texas10MostWanted/MostWanted/stillWanted",
)
SOURCE_NAME = "Texas Department of Public Safety"
MEDIA_DIR = Path(__file__).resolve().parents[2] / "data" / "media" / "texas-dps"
MEDIA_URL_PREFIX = "/media/texas-dps"
SAFETY_WARNING = (
    "Do not approach or attempt to apprehend any individual. "
    "Submit information directly to the Texas Department of Public Safety."
)
USER_AGENT = "RewardWatchMVP0/0.1 (+official-source-research)"
_DETAIL_PATH_MARKERS = (
    "fugitivedetails",
    "sexoffenderdetails",
    "criminalillegalimmigrantdetails",
    "stillwanteddetails",
)
_IMAGE_EXTENSIONS = {
    "image/gif": "gif",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
_EMPTY_VALUES = {"", "n/a", "na", "none", "unknown", "not available"}
_CLOSED_MARKERS = (
    "was captured",
    "has been captured",
    "was apprehended",
    "has been apprehended",
    "is no longer wanted",
    "was taken into custody",
)


def fetch_texas_dps_cases(
    limit: int | None = None,
    known_published_dates: dict[str, str] | None = None,
    media_dir: Path = MEDIA_DIR,
) -> list[dict[str, Any]]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        index_documents = list(executor.map(_fetch_html, INDEX_URLS))

    detail_urls: list[str] = []
    seen_ids: set[str] = set()
    for index_url, document in zip(INDEX_URLS, index_documents, strict=True):
        for detail_url in discover_detail_urls(document, index_url):
            source_id = _source_id(detail_url)
            if source_id and source_id not in seen_ids:
                seen_ids.add(source_id)
                detail_urls.append(detail_url)

    if not detail_urls:
        raise ValueError("Texas DPS active directories returned no detail links")

    selected_urls = detail_urls[:limit] if limit else detail_urls
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        detail_documents = list(executor.map(_fetch_html, selected_urls))

    today = datetime.now(UTC).date().isoformat()
    published_dates = known_published_dates or {}
    cases = [
        reward_case
        for detail_url, document in zip(selected_urls, detail_documents, strict=True)
        if (
            reward_case := parse_texas_dps_detail(
                document,
                detail_url,
                published_date=published_dates.get(
                    f"txdps-{_source_id(detail_url)}",
                    today,
                ),
                media_dir=media_dir,
            )
        )
    ]

    if not cases:
        raise ValueError("Texas DPS returned no publishable records with official images")

    if limit is None:
        _remove_stale_media(media_dir, cases)

    cases.sort(key=lambda item: (item["publishedDate"], item["title"]), reverse=True)
    return cases


def discover_detail_urls(index_html: str, index_url: str) -> list[str]:
    soup = BeautifulSoup(index_html, "html.parser")
    urls: list[str] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        candidate = urljoin(index_url, clean_text(anchor.get("href")))
        path = urlsplit(candidate).path.lower()
        if (
            "captured" in path
            or not any(marker in path for marker in _DETAIL_PATH_MARKERS)
            or not _source_id(candidate)
            or candidate in seen
        ):
            continue
        seen.add(candidate)
        urls.append(candidate)
    return urls


def parse_texas_dps_detail(
    detail_html: str,
    source_url: str,
    *,
    published_date: str,
    media_dir: Path = MEDIA_DIR,
    media_url_prefix: str = MEDIA_URL_PREFIX,
) -> dict[str, Any] | None:
    source_id = _source_id(source_url)
    if not source_id:
        return None

    soup = BeautifulSoup(detail_html, "html.parser")
    root = soup.select_one(".myDetailsPages")
    if not root:
        return None

    name_element = root.select_one(".bigNameLabel")
    title = clean_text(name_element.get_text(" ", strip=True)) if name_element else ""
    reward_element = root.select_one(".rewardtext")
    reward_text = (
        clean_text(reward_element.get_text(" ", strip=True))
        if reward_element
        else ""
    )
    reward = _reward_amount(reward_text)
    fields = _detail_fields(root)
    narrative_element = root.select_one(".FinalDetailsText")
    summary = (
        clean_text(narrative_element.get_text(" ", strip=True))
        if narrative_element
        else ""
    )
    if (
        not title
        or not reward
        or len(summary) < 30
        or any(marker in summary.lower() for marker in _CLOSED_MARKERS)
    ):
        return None

    case_id = f"txdps-{source_id}"
    image_urls = _cache_images(
        root,
        case_id=case_id,
        media_dir=media_dir,
        media_url_prefix=media_url_prefix,
    )
    if not image_urls:
        return None

    case_type = _case_type(source_url)
    wanted_for = _value(fields, "WANTED FOR") or case_type
    locations = _value(fields, "LKC") or _value(fields, "LKA") or "Texas"
    last_verified = datetime.now(UTC).date().isoformat()

    return {
        "id": case_id,
        "title": title,
        "agency": SOURCE_NAME,
        "country": "US",
        "regions": ["Texas"],
        "caseType": case_type,
        "description": wanted_for,
        "reward": reward,
        "rewardText": reward_text,
        "status": "Open",
        "summary": _shorten(summary, 1400),
        "warningMessage": SAFETY_WARNING,
        "aliases": _aliases(_value(fields, "AKA")),
        "age": None,
        "dateOfBirth": _value(fields, "DOB"),
        "placeOfBirth": None,
        "sex": _value(fields, "SEX"),
        "race": _value(fields, "RACE"),
        "nationality": None,
        "hair": _value(fields, "HAIR"),
        "eyes": _value(fields, "EYES"),
        "height": _value(fields, "HEIGHT"),
        "weight": _value(fields, "WEIGHT"),
        "locations": locations,
        "distinguishingFeatures": _value(fields, "SMT"),
        "fieldOffice": "Texas",
        "publishedDate": published_date,
        "lastVerified": last_verified,
        "sourceUpdatedDate": None,
        "sourceUrl": source_url,
        "sourceTitle": f"Texas DPS Most Wanted: {title}",
        "sourceAuthor": SOURCE_NAME,
        "imageUrl": image_urls[0],
        "imageUrls": image_urls,
    }


def _detail_fields(root: Any) -> dict[str, str]:
    fields: dict[str, str] = {}
    for row in root.select('[class^="row"]'):
        labels = [
            element
            for element in row.select("[class]")
            if any(name.startswith("labelText") for name in element.get("class", []))
        ]
        values = [
            element
            for element in row.select("[class]")
            if any(name.startswith("detailText") for name in element.get("class", []))
        ]
        for label_element, value_element in zip(labels, values):
            label = clean_text(label_element.get_text(" ", strip=True)).rstrip(":").upper()
            value = clean_text(value_element.get_text(" ", strip=True))
            if label and value:
                fields[label] = value
    return fields


def _cache_images(
    root: Any,
    *,
    case_id: str,
    media_dir: Path,
    media_url_prefix: str,
) -> list[str]:
    unique_images: list[tuple[str, bytes]] = []
    seen_hashes: set[str] = set()
    for image in root.select("img[src]"):
        source = str(image.get("src") or "")
        match = re.fullmatch(
            r"data:(image/[a-zA-Z0-9.+-]+);base64,(.+)",
            source,
            flags=re.DOTALL,
        )
        if not match:
            continue
        mime_type = match.group(1).lower()
        extension = _IMAGE_EXTENSIONS.get(mime_type)
        if not extension:
            continue
        try:
            payload = base64.b64decode(re.sub(r"\s+", "", match.group(2)), validate=True)
        except (ValueError, base64.binascii.Error):
            continue
        if len(payload) < 32:
            continue
        digest = hashlib.sha256(payload).hexdigest()
        if digest in seen_hashes:
            continue
        seen_hashes.add(digest)
        unique_images.append((extension, payload))

    media_dir.mkdir(parents=True, exist_ok=True)
    image_urls: list[str] = []
    for index, (extension, payload) in enumerate(unique_images, start=1):
        filename = f"{case_id}-{index}.{extension}"
        target = media_dir / filename
        if not target.exists() or target.read_bytes() != payload:
            temporary = target.with_suffix(f"{target.suffix}.tmp")
            temporary.write_bytes(payload)
            temporary.replace(target)
        image_urls.append(f"{media_url_prefix.rstrip('/')}/{filename}")
    return image_urls


def _remove_stale_media(media_dir: Path, cases: list[dict[str, Any]]) -> None:
    if not media_dir.exists():
        return
    active_names = {
        Path(urlsplit(url).path).name
        for case in cases
        for url in case.get("imageUrls", [])
        if isinstance(url, str)
    }
    for path in media_dir.iterdir():
        if path.is_file() and path.name not in active_names:
            path.unlink()


def _source_id(source_url: str) -> str:
    source_ids = parse_qs(urlsplit(source_url).query).get("id", [])
    return source_ids[0] if source_ids and source_ids[0].isdigit() else ""


def _reward_amount(reward_text: str) -> int:
    return extract_cash_amount(reward_text)


def _case_type(source_url: str) -> str:
    path = urlsplit(source_url).path.lower()
    if "sexoffender" in path:
        return "Wanted Sex Offender"
    if "criminalillegalimmigrant" in path:
        return "Wanted Person"
    return "Wanted Fugitive"


def _value(fields: dict[str, str], key: str) -> str | None:
    value = clean_text(fields.get(key))
    return None if value.lower() in _EMPTY_VALUES else value


def _aliases(value: str | None) -> list[str]:
    if not value:
        return []
    return [
        alias
        for part in re.split(r"[;,|]", value)
        if (alias := clean_text(part)) and alias.lower() not in _EMPTY_VALUES
    ]


def _shorten(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "..."


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
