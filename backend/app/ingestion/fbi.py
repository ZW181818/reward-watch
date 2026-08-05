from __future__ import annotations

import html
import json
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .reward_amount import extract_cash_amount

FBI_WANTED_API_URL = "https://api.fbi.gov/wanted/v1/list"
SOURCE_NAME = "Federal Bureau of Investigation"
MULTI_WORD_FIELD_OFFICES = {
    "elpaso": "El Paso",
    "kansascity": "Kansas City",
    "lasvegas": "Las Vegas",
    "littlerock": "Little Rock",
    "losangeles": "Los Angeles",
    "newhaven": "New Haven",
    "neworleans": "New Orleans",
    "newyork": "New York",
    "oklahomacity": "Oklahoma City",
    "saltlakecity": "Salt Lake City",
    "sanantonio": "San Antonio",
    "sandiego": "San Diego",
    "sanfrancisco": "San Francisco",
    "sanjuan": "San Juan",
    "stlouis": "St. Louis",
    "washingtondc": "Washington, D.C.",
}
FBI_OFFICE_REGIONS = {
    "albany": "New York",
    "albuquerque": "New Mexico",
    "anchorage": "Alaska",
    "atlanta": "Georgia",
    "baltimore": "Maryland",
    "billings": "Montana",
    "birmingham": "Alabama",
    "boston": "Massachusetts",
    "buffalo": "New York",
    "charlotte": "North Carolina",
    "chicago": "Illinois",
    "cincinnati": "Ohio",
    "cleveland": "Ohio",
    "columbia": "South Carolina",
    "dallas": "Texas",
    "denver": "Colorado",
    "detroit": "Michigan",
    "elpaso": "Texas",
    "honolulu": "Hawaii",
    "houston": "Texas",
    "indianapolis": "Indiana",
    "jackson": "Mississippi",
    "jacksonville": "Florida",
    "kansascity": "Missouri",
    "knoxville": "Tennessee",
    "lasvegas": "Nevada",
    "littlerock": "Arkansas",
    "losangeles": "California",
    "louisville": "Kentucky",
    "memphis": "Tennessee",
    "miami": "Florida",
    "milwaukee": "Wisconsin",
    "minneapolis": "Minnesota",
    "mobile": "Alabama",
    "nashville": "Tennessee",
    "newhaven": "Connecticut",
    "neworleans": "Louisiana",
    "newyork": "New York",
    "newark": "New Jersey",
    "norfolk": "Virginia",
    "oklahomacity": "Oklahoma",
    "omaha": "Nebraska",
    "philadelphia": "Pennsylvania",
    "phoenix": "Arizona",
    "pittsburgh": "Pennsylvania",
    "portland": "Oregon",
    "richmond": "Virginia",
    "sacramento": "California",
    "saltlakecity": "Utah",
    "sanantonio": "Texas",
    "sandiego": "California",
    "sanfrancisco": "California",
    "sanjuan": "Puerto Rico",
    "seattle": "Washington",
    "springfield": "Illinois",
    "stlouis": "Missouri",
    "tampa": "Florida",
    "washingtondc": "District of Columbia",
}
US_STATE_ABBREVIATIONS = {
    "AK": "Alaska",
    "AL": "Alabama",
    "AR": "Arkansas",
    "AZ": "Arizona",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DC": "District of Columbia",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "IA": "Iowa",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "MA": "Massachusetts",
    "MD": "Maryland",
    "ME": "Maine",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MO": "Missouri",
    "MS": "Mississippi",
    "MT": "Montana",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "NE": "Nebraska",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NV": "Nevada",
    "NY": "New York",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "PR": "Puerto Rico",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VA": "Virginia",
    "VT": "Vermont",
    "WA": "Washington",
    "WI": "Wisconsin",
    "WV": "West Virginia",
    "WY": "Wyoming",
}


def fetch_fbi_cases(
    limit: int | None = None,
    excluded_source_urls: set[str] | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page = 1
    page_size = 50
    total = 0
    exclusions = excluded_source_urls or set()

    while True:
        page_items, total = _fetch_page(page=page, page_size=page_size)
        if not page_items:
            break

        for item in page_items:
            normalized = normalize_fbi_item(item, excluded_source_urls=exclusions)
            if normalized:
                items.append(normalized)
                if limit and len(items) >= limit:
                    return items[:limit]

        if page * page_size >= total:
            break
        page += 1

    return items


def normalize_fbi_item(
    item: dict[str, Any],
    excluded_source_urls: set[str] | None = None,
) -> dict[str, Any] | None:
    uid = _clean_text(item.get("uid"))
    title = _clean_text(item.get("title"))
    source_url = _clean_text(item.get("url"))

    if not uid or not title or not source_url:
        return None

    if source_url in (excluded_source_urls or set()):
        return None

    status = _normalize_status(item.get("status"), source_url)
    if status == "Closed":
        return None

    description = _clean_text(item.get("description"))
    summary = (
        _clean_text(item.get("details"))
        or _clean_text(item.get("caution"))
        or _clean_text(item.get("remarks"))
        or description
    )
    image_urls = _extract_image_urls(item)

    if len(summary) < 40 or not image_urls:
        return None

    reward_text = _clean_text(item.get("reward_text"))
    reward = _extract_reward_amount(reward_text)
    published_date = _date_only(item.get("publication")) or _date_only(item.get("modified"))
    last_verified = datetime.now(UTC).date().isoformat()
    image_url = image_urls[0] if image_urls else None
    aliases = _clean_list(item.get("aliases"))
    subjects = _clean_list(item.get("subjects"))

    return {
        "id": f"fbi-{uid}",
        "title": title,
        "agency": SOURCE_NAME,
        "country": "US",
        "regions": _derive_regions(item.get("field_offices"), title),
        "caseType": _derive_case_type(source_url, subjects),
        "description": description or None,
        "reward": reward,
        "rewardText": reward_text or None,
        "status": status,
        "summary": summary,
        "warningMessage": _clean_text(item.get("warning_message")) or None,
        "aliases": aliases,
        "dateOfBirth": _clean_text(item.get("dates_of_birth_used")) or None,
        "placeOfBirth": _clean_text(item.get("place_of_birth")) or None,
        "sex": _title_text(item.get("sex")),
        "race": _title_text(item.get("race")),
        "nationality": _title_text(item.get("nationality")),
        "hair": _title_text(item.get("hair")),
        "eyes": _title_text(item.get("eyes")),
        "height": _format_height(item.get("height_min"), item.get("height_max")),
        "weight": _format_weight(item.get("weight_min"), item.get("weight_max")),
        "fieldOffice": _format_field_offices(item.get("field_offices")),
        "publishedDate": published_date or last_verified,
        "lastVerified": last_verified,
        "sourceUpdatedDate": _date_only(item.get("modified")) or None,
        "sourceUrl": source_url,
        "sourceTitle": f"FBI Wanted: {title}",
        "sourceAuthor": SOURCE_NAME,
        "imageUrl": image_url,
        "imageUrls": image_urls,
    }


def _derive_regions(field_offices: Any, title: str) -> list[str]:
    regions: list[str] = []
    for office in _clean_list(field_offices):
        office_key = re.sub(r"[^a-z0-9]", "", office.lower())
        region = FBI_OFFICE_REGIONS.get(office_key)
        if region and region not in regions:
            regions.append(region)

    if regions:
        return regions

    title_upper = title.upper()
    for abbreviation in re.findall(r",\s*([A-Z]{2})(?:\b|$)", title_upper):
        region = US_STATE_ABBREVIATIONS.get(abbreviation)
        if region and region not in regions:
            regions.append(region)

    if regions:
        return regions

    for region in US_STATE_ABBREVIATIONS.values():
        if re.search(rf"\b{re.escape(region.upper())}\b", title_upper):
            regions.append(region)
    return regions


def _fetch_page(page: int, page_size: int) -> tuple[list[dict[str, Any]], int]:
    params = urlencode({"page": page, "pageSize": page_size})
    request = Request(
        f"{FBI_WANTED_API_URL}?{params}",
        headers={
            "Accept": "application/json",
            "User-Agent": "RewardWatchMVP0/0.1 (+official-source-research)",
        },
    )

    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    items = payload.get("items", [])
    total = payload.get("total", 0)
    return (
        items if isinstance(items, list) else [],
        total if isinstance(total, int) else 0,
    )


def _clean_text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, list):
        value = " ".join(str(item) for item in value if item)

    text = html.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\u00a0", " ").replace("\u00c2", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _clean_list(value: Any) -> list[str]:
    if value is None:
        return []

    values = value if isinstance(value, list) else [value]
    result: list[str] = []

    for item in values:
        text = _clean_text(item)
        if text and text not in result:
            result.append(text)

    return result


def _extract_reward_amount(text: str) -> int:
    return extract_cash_amount(text)


def _normalize_status(value: Any, source_url: str) -> str:
    status = _clean_text(value).lower()

    if any(keyword in status for keyword in ("captured", "deceased", "closed", "located")):
        return "Closed"

    if any(keyword in status for keyword in ("wanted", "open", "active")):
        return "Open"

    information_paths = ("/seeking-info/", "/seeking-information/", "/kidnap/", "/vicap/")
    if any(path in source_url.lower() for path in information_paths):
        return "Information Requested"

    return "Open"


def _derive_case_type(source_url: str, subjects: list[str]) -> str:
    normalized_url = source_url.lower()

    if "/seeking-info/" in normalized_url or "/seeking-information/" in normalized_url:
        return "Seeking Information"
    if "/kidnap/" in normalized_url:
        return "Missing Person / Kidnapping"
    if "/vicap/" in normalized_url:
        return "ViCAP"
    if subjects:
        return subjects[0]

    return "Wanted"


def _title_text(value: Any) -> str | None:
    text = _clean_text(value)
    return text.title() if text else None


def _format_field_offices(value: Any) -> str | None:
    offices = _clean_list(value)
    display_names = []

    for office in offices:
        normalized = re.sub(r"[^a-z]", "", office.lower())
        display_names.append(
            MULTI_WORD_FIELD_OFFICES.get(normalized, office.replace("-", " ").title())
        )

    return ", ".join(display_names) or None


def _format_height(minimum: Any, maximum: Any) -> str | None:
    minimum_inches = _as_integer(minimum)
    maximum_inches = _as_integer(maximum)

    if minimum_inches is None and maximum_inches is None:
        return None
    if minimum_inches is None:
        minimum_inches = maximum_inches
    if maximum_inches is None:
        maximum_inches = minimum_inches

    assert minimum_inches is not None and maximum_inches is not None
    if minimum_inches == maximum_inches:
        return _inches_to_height(minimum_inches)

    return f"{_inches_to_height(minimum_inches)} to {_inches_to_height(maximum_inches)}"


def _format_weight(minimum: Any, maximum: Any) -> str | None:
    minimum_pounds = _as_integer(minimum)
    maximum_pounds = _as_integer(maximum)

    if minimum_pounds is None and maximum_pounds is None:
        return None
    if minimum_pounds is None:
        minimum_pounds = maximum_pounds
    if maximum_pounds is None:
        maximum_pounds = minimum_pounds

    assert minimum_pounds is not None and maximum_pounds is not None
    if minimum_pounds == maximum_pounds:
        return f"{minimum_pounds} pounds"

    return f"{minimum_pounds} to {maximum_pounds} pounds"


def _as_integer(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _inches_to_height(value: int) -> str:
    return f"{value // 12}'{value % 12}\""


def _date_only(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        return ""

    match = re.match(r"(\d{4}-\d{2}-\d{2})", text)
    if match:
        return match.group(1)

    return ""


def _extract_image_urls(item: dict[str, Any]) -> list[str]:
    images = item.get("images")
    if not isinstance(images, list):
        return []

    image_urls: list[str] = []

    for image in images:
        if not isinstance(image, dict):
            continue
        for key in ("original", "large", "thumb"):
            value = _clean_text(image.get(key))
            if value.startswith("http") and value not in image_urls:
                image_urls.append(value)
                break

    return image_urls
