from __future__ import annotations

import html
import json
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


OPP_DATA_URL = "https://www.opp.ca/tms/sitedata.php"
OPP_DETAIL_URL = "https://www.opp.ca/index.php?id=115&entryid="
OPP_IMAGE_URL = "https://www.opp.ca/tms/entrydata.php?fnc=3&_id="
SOURCE_NAME = "Ontario Provincial Police"
SAFETY_WARNING = (
    "Do not approach or attempt to detain any individual. "
    "Submit information directly to the Ontario Provincial Police."
)
PUBLISHABLE_TYPES = {
    "reward": "Public Reward",
    "mostwanted": "Most Wanted",
    "ropewanted": "ROPE Wanted",
}


def fetch_opp_cases(limit: int | None = None) -> list[dict[str, Any]]:
    cases = [
        normalized
        for record in _fetch_records()
        if (normalized := normalize_opp_record(record)) is not None
    ]
    cases.sort(key=lambda item: str(item.get("publishedDate", "")), reverse=True)
    return cases[:limit] if limit else cases


def normalize_opp_record(record: dict[str, Any]) -> dict[str, Any] | None:
    record_id = _object_id(record.get("_id"))
    title = _clean_text(record.get("circularname"))
    circular_type = _clean_text(record.get("circulartype")).lower()
    state = str(record.get("state", "1"))

    if not record_id or not title or circular_type not in PUBLISHABLE_TYPES:
        return None
    if state not in {"1", "True", "true"}:
        return None

    description_html = str(record.get("engdescription") or "")
    full_description = _clean_html(description_html)
    heading = _clean_text(record.get("engsummary"))
    image_urls = _extract_image_urls(record)
    description = _first_paragraph(description_html) or heading
    summary = _summary_from_html(description_html) or full_description

    if len(summary) < 40 or not image_urls:
        return None

    source_updated_date = _timestamp_date(record.get("timestamp"))
    last_verified = datetime.now(UTC).date().isoformat()
    published_date = _published_date(description_html) or source_updated_date
    reward = _extract_reward_amount(f"{heading} {full_description}")
    details_text = _structured_text(description_html)

    return {
        "id": f"opp-{record_id}",
        "title": title,
        "agency": SOURCE_NAME,
        "country": "Canada",
        "regions": ["Ontario"],
        "caseType": PUBLISHABLE_TYPES[circular_type],
        "description": description or heading or None,
        "reward": reward,
        "rewardText": (
            f"The official source lists a reward of up to ${reward:,}."
            if reward > 0
            else None
        ),
        "status": "Open" if circular_type != "reward" else "Information Requested",
        "summary": summary,
        "warningMessage": SAFETY_WARNING,
        "aliases": _split_aliases(
            _field_value(details_text, "aliases", "aliase(s)", "alias(es)")
        ),
        "age": _field_value(details_text, "age") or _described_age(full_description),
        "dateOfBirth": _field_value(details_text, "dob", "d.o.b."),
        "placeOfBirth": _field_value(details_text, "place of birth"),
        "sex": _described_sex(full_description),
        "race": _described_race(full_description),
        "nationality": _field_value(details_text, "citizenship"),
        "hair": _field_value(details_text, "hair"),
        "eyes": _field_value(details_text, "eyes"),
        "height": _field_value(details_text, "height"),
        "weight": _field_value(details_text, "weight"),
        "locations": _field_value(details_text, "residence"),
        "distinguishingFeatures": _field_value(
            details_text,
            "scars & marks",
            "scars and marks",
            "scars & tattoos",
        ),
        "fieldOffice": "Ontario",
        "publishedDate": published_date or last_verified,
        "lastVerified": last_verified,
        "sourceUpdatedDate": source_updated_date or None,
        "sourceUrl": f"{OPP_DETAIL_URL}{record_id}",
        "sourceTitle": f"OPP {PUBLISHABLE_TYPES[circular_type]}: {title}",
        "sourceAuthor": SOURCE_NAME,
        "imageUrl": image_urls[0],
        "imageUrls": image_urls,
    }


def _fetch_records() -> list[dict[str, Any]]:
    body = urlencode(
        {
            "fnc": "1",
            "apifnc": "sitedata",
            "findData": json.dumps({"template": "circular"}),
            "returnCriteria": json.dumps({}),
            "returnFiles": "1",
        }
    ).encode("utf-8")
    request = Request(
        OPP_DATA_URL,
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "RewardWatchMVP0/0.1 (+official-source-research)",
        },
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []


def _extract_image_urls(record: dict[str, Any]) -> list[str]:
    files = record.get("files")
    if not isinstance(files, list):
        return []

    images_by_asset: dict[str, tuple[int, str]] = {}
    priorities = {"resized": 0, "original": 1, "thumbnail": 2}

    for wrapper in files:
        file_data = wrapper.get("file") if isinstance(wrapper, dict) else None
        if not isinstance(file_data, dict):
            continue
        if _clean_text(file_data.get("fileinputid")).lower() != "primaryfile":
            continue
        if not _clean_text(file_data.get("filetype")).lower().startswith("image/"):
            continue

        file_id = _object_id(file_data.get("_id"))
        if not file_id:
            continue

        asset_key = _clean_text(file_data.get("guid")) or _clean_text(
            file_data.get("filename")
        )
        image_type = _clean_text(file_data.get("imagetype")).lower()
        priority = priorities.get(image_type, 3)
        current = images_by_asset.get(asset_key)
        if current is None or priority < current[0]:
            images_by_asset[asset_key] = (priority, f"{OPP_IMAGE_URL}{file_id}")

    return [entry[1] for entry in images_by_asset.values()]


def _summary_from_html(value: str) -> str:
    soup = BeautifulSoup(value, "html.parser")
    paragraphs: list[str] = []

    for node in soup.find_all(["h2", "p"]):
        text = _clean_text(node.get_text(" ", strip=True))
        if node.name == "h2" and text.lower() == "details":
            break
        if node.name == "p" and text:
            paragraphs.append(text)
        if len(paragraphs) >= 2:
            break

    return " ".join(paragraphs)


def _first_paragraph(value: str) -> str:
    soup = BeautifulSoup(value, "html.parser")
    paragraph = soup.find("p")
    return _clean_text(paragraph.get_text(" ", strip=True)) if paragraph else ""


def _structured_text(value: str) -> str:
    soup = BeautifulSoup(value, "html.parser")
    for line_break in soup.find_all("br"):
        line_break.replace_with("\n")
    for block in soup.find_all(["p", "h2"]):
        block.append("\n")

    text = html.unescape(soup.get_text(" ", strip=False))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


def _clean_html(value: str) -> str:
    soup = BeautifulSoup(value, "html.parser")
    return _clean_text(soup.get_text(" ", strip=True))


def _field_value(text: str, *labels: str) -> str | None:
    for label in labels:
        pattern = rf"(?im)^\s*{re.escape(label)}\s*:\s*([^\n]+)"
        match = re.search(pattern, text)
        if match:
            value = _clean_text(match.group(1))
            return value or None
    return None


def _split_aliases(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in re.split(r"[,;]", value) if part.strip()]


def _described_age(text: str) -> str | None:
    match = re.search(r"\b(?:aged?|a)\s+(\d{1,3})(?:-|\s+)years?[- ]old\b", text, re.I)
    return match.group(1) if match else None


def _described_sex(text: str) -> str | None:
    match = re.search(r"\b(male|female)\b", text, re.I)
    return match.group(1).title() if match else None


def _described_race(text: str) -> str | None:
    match = re.search(r"\b(black|white|asian|indigenous)\s+(?:male|female)\b", text, re.I)
    return match.group(1).title() if match else None


def _extract_reward_amount(text: str) -> int:
    amounts = []
    patterns = (
        r"\breward\b.{0,180}?\$\s*([0-9][0-9,]*)",
        r"\$\s*([0-9][0-9,]*)\s+(?:cash\s+)?\breward\b",
    )
    matches = [match for pattern in patterns for match in re.findall(pattern, text, re.I)]

    for match in matches:
        try:
            amounts.append(int(match.replace(",", "")))
        except ValueError:
            continue
    return max(amounts) if amounts else 0


def _published_date(value: str) -> str:
    text = _structured_text(value)
    match = re.search(
        r"\bDate\s*:\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4}|[A-Za-z]+\s+\d{1,2},?\s+\d{4})",
        text,
        re.I,
    )
    if not match:
        return ""

    candidate = re.sub(r"\s+", " ", match.group(1)).strip()
    for date_format in ("%d %b %Y", "%d %B %Y", "%B %d, %Y", "%B %d %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(candidate, date_format).date().isoformat()
        except ValueError:
            continue
    return ""


def _timestamp_date(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    date_wrapper = value.get("$date")
    milliseconds = date_wrapper.get("$numberLong") if isinstance(date_wrapper, dict) else None
    try:
        return datetime.fromtimestamp(int(milliseconds) / 1000, tz=UTC).date().isoformat()
    except (TypeError, ValueError, OSError):
        return ""


def _object_id(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return _clean_text(value.get("$id") or value.get("$oid"))


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value)).replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()
