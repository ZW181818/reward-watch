from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup, Tag


RCMP_NEWS_URL = "https://rcmp.ca/en/saskatchewan/news"
SOURCE_NAME = "Saskatchewan RCMP"
WANTED_RELEASE_TITLE = "Saskatchewan RCMP: Wanted Persons"
SAFETY_WARNING = (
    "Do not attempt to contact, approach or apprehend this person. "
    "Submit information directly to the RCMP."
)


def fetch_rcmp_saskatchewan_cases(limit: int | None = None) -> list[dict[str, Any]]:
    news_html = _fetch_html(RCMP_NEWS_URL)
    release = discover_latest_wanted_release(news_html)
    release_url = release["view_node"]
    release_html = _fetch_html(release_url)

    cases = parse_rcmp_wanted_release(
        release_html,
        source_url=release_url,
        published_date=release.get("field_publish_date"),
    )
    return cases[:limit] if limit else cases


def discover_latest_wanted_release(news_html: str) -> dict[str, str]:
    soup = BeautifulSoup(news_html, "html.parser")
    settings_script = soup.find(
        "script", attrs={"data-drupal-selector": "drupal-settings-json"}
    )
    if not settings_script:
        raise ValueError("RCMP news index did not include Drupal settings data")

    settings = json.loads(settings_script.get_text())
    encoded_news = settings.get("poweb", {}).get("all_news", {}).get(
        "rest_export_all_news"
    )
    if not isinstance(encoded_news, str):
        raise ValueError("RCMP news index did not include its official news feed")

    records = json.loads(encoded_news)
    candidates = [
        record
        for record in records
        if isinstance(record, dict)
        and _clean_text(record.get("title")) == WANTED_RELEASE_TITLE
        and _clean_text(record.get("view_node")).startswith("https://rcmp.ca/")
        and _date_only(record.get("field_publish_date"))
    ]
    if not candidates:
        raise ValueError("No current Saskatchewan RCMP wanted-persons release was found")

    latest = max(candidates, key=lambda record: record["field_publish_date"])
    return {
        "title": _clean_text(latest.get("title")),
        "view_node": _clean_text(latest.get("view_node")),
        "field_publish_date": _date_only(latest.get("field_publish_date")),
    }


def parse_rcmp_wanted_release(
    release_html: str,
    source_url: str,
    published_date: str | None = None,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(release_html, "html.parser")
    content_section = soup.find("section", id="s1")
    if not content_section:
        raise ValueError("RCMP wanted release did not include a content section")

    release_date = _date_only(published_date) or _release_date(content_section)
    source_updated_date = _meta_date(soup, "dcterms.modified") or release_date
    last_verified = datetime.now(UTC).date().isoformat()
    profiles = _extract_profiles(content_section)
    gallery_images = _extract_gallery_images(soup, source_url)
    image_assignments = _assign_images(profiles, gallery_images)
    cases: list[dict[str, Any]] = []

    for profile in profiles:
        name = profile["name"]
        if "arrested" in name.lower():
            continue

        image_urls = image_assignments.get(name, [])
        offences = profile.get("offences")
        if not offences or not image_urls:
            continue

        locations = profile.get("locations")
        summary = (
            f"{name} is listed by Saskatchewan RCMP as wanted on an active warrant. "
            f"Offences listed by the agency: {offences}."
        )
        if locations:
            summary += f" The agency lists possible communities as: {locations}."

        cases.append(
            {
                "id": f"rcmp-sk-{_slugify(name)}",
                "title": name,
                "agency": SOURCE_NAME,
                "country": "Canada",
                "regions": ["Saskatchewan"],
                "caseType": "Wanted Person",
                "description": offences,
                "reward": 0,
                "rewardText": None,
                "status": "Open",
                "summary": summary,
                "warningMessage": SAFETY_WARNING,
                "aliases": _parse_aliases(profile.get("aliases")),
                "age": _optional_value(profile.get("age")),
                "dateOfBirth": None,
                "placeOfBirth": None,
                "sex": _title_value(profile.get("gender")),
                "race": None,
                "nationality": None,
                "hair": _title_value(profile.get("hair")),
                "eyes": _title_value(profile.get("eyes")),
                "height": _optional_value(profile.get("height")),
                "weight": _optional_value(profile.get("weight")),
                "locations": _optional_value(locations),
                "distinguishingFeatures": _optional_value(
                    profile.get("scars_tattoos")
                ),
                "fieldOffice": "Saskatchewan",
                "publishedDate": release_date or last_verified,
                "lastVerified": last_verified,
                "sourceUpdatedDate": source_updated_date or None,
                "sourceUrl": source_url,
                "sourceTitle": WANTED_RELEASE_TITLE,
                "sourceAuthor": SOURCE_NAME,
                "imageUrl": image_urls[0],
                "imageUrls": image_urls,
            }
        )

    return cases


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


def _extract_profiles(content_section: Tag) -> list[dict[str, str]]:
    profiles: list[dict[str, str]] = []
    current_name: str | None = None
    current_nodes: list[Tag] = []

    for child in content_section.children:
        if not isinstance(child, Tag):
            continue

        text = _clean_text(child.get_text(" ", strip=True))
        heading = re.match(r"^(\d+)\.\s*(.+)$", text)
        if heading:
            if current_name:
                profiles.append(_profile_from_nodes(current_name, current_nodes))
            current_name = _clean_text(heading.group(2))
            current_nodes = []
            continue

        if current_name:
            current_nodes.append(child)

    if current_name:
        profiles.append(_profile_from_nodes(current_name, current_nodes))

    return profiles


def _profile_from_nodes(name: str, nodes: list[Tag]) -> dict[str, str]:
    profile = {"name": name}
    texts = [_clean_text(node.get_text(" ", strip=True)) for node in nodes]
    field_labels = {
        "aliases": "aliases",
        "gender": "gender",
        "age": "age",
        "height": "height",
        "weight": "weight",
        "hair": "hair",
        "eyes": "eyes",
        "scars/tattoos": "scars_tattoos",
        "may be in these communities": "locations",
        "offences": "offences",
    }

    for index, text in enumerate(texts):
        match = re.match(r"^([^:]+)\s*:\s*(.*)$", text)
        if not match:
            continue

        label = _clean_text(match.group(1)).lower()
        key = field_labels.get(label)
        if not key:
            continue

        value = _clean_text(match.group(2))
        if not value:
            value = _next_text(texts, index + 1)
        if value:
            profile[key] = value

    return profile


def _extract_gallery_images(soup: BeautifulSoup, source_url: str) -> list[str]:
    gallery = soup.find("section", id="s2")
    if not gallery:
        return []

    image_urls: list[str] = []
    for anchor in gallery.find_all("a", href=True):
        href = _clean_text(anchor.get("href"))
        if "no-photo-available" in href.lower():
            continue

        image_url = urljoin(source_url, href)
        if image_url not in image_urls:
            image_urls.append(image_url)

    return image_urls


def _assign_images(
    profiles: list[dict[str, str]], image_urls: list[str]
) -> dict[str, list[str]]:
    assignments: dict[str, list[str]] = {}
    available = set(image_urls)

    for profile in profiles:
        name = profile["name"]
        best_url = None
        best_score = 0

        for image_url in available:
            score = _image_match_score(name, image_url)
            if score > best_score:
                best_score = score
                best_url = image_url

        if best_url and best_score >= 60:
            assignments[name] = [best_url]
            available.remove(best_url)

    return assignments


def _image_match_score(name: str, image_url: str) -> int:
    full_name = _slugify(name).replace("-", "")
    name_parts = [_slugify(part).replace("-", "") for part in name.split()]
    image_path = urlsplit(image_url).path
    image_stem = PurePosixPath(image_path).stem.lower()
    image_stem = re.sub(r"(?:_\d+|\d+)$", "", image_stem)
    image_key = re.sub(r"[^a-z0-9]", "", image_stem)

    if not image_key:
        return 0
    if image_key == full_name:
        return 100
    if full_name.startswith(image_key) or image_key.startswith(full_name):
        return 80
    if any(
        len(part) >= 4 and (image_key.startswith(part) or part.startswith(image_key))
        for part in name_parts
    ):
        return 60
    return 0


def _release_date(content_section: Tag) -> str:
    for paragraph in content_section.find_all("p", recursive=False):
        value = _date_only(paragraph.get_text(" ", strip=True))
        if value:
            return value
    return ""


def _meta_date(soup: BeautifulSoup, name: str) -> str:
    meta = soup.find("meta", attrs={"name": name})
    return _date_only(meta.get("content")) if meta else ""


def _parse_aliases(value: str | None) -> list[str]:
    cleaned = _optional_value(value)
    if not cleaned:
        return []
    return [alias.strip() for alias in re.split(r"[,;]", cleaned) if alias.strip()]


def _optional_value(value: Any) -> str | None:
    cleaned = _clean_text(value)
    if not cleaned or cleaned.lower() in {"nil", "none", "unknown", "n/a"}:
        return None
    return cleaned


def _title_value(value: Any) -> str | None:
    cleaned = _optional_value(value)
    return cleaned.title() if cleaned else None


def _next_text(texts: list[str], start: int) -> str:
    for text in texts[start:]:
        if text:
            return text
    return ""


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\u00a0", " ")
    text = (
        text.replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )
    return re.sub(r"\s+", " ", text).strip()


def _date_only(value: Any) -> str:
    match = re.search(r"(\d{4}-\d{2}-\d{2})", _clean_text(value))
    return match.group(1) if match else ""


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"
