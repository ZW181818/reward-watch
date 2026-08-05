from __future__ import annotations

import html
import json
import re
import warnings
from typing import Any
from urllib.parse import quote, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning


USER_AGENT = "RewardWatchMVP0/0.1 (+official-source-research)"
CLOSED_TITLE_MARKERS = (
    "arrested",
    "back in custody",
    "in custody",
    "located",
    "found",
    "returned to custody",
    "turns himself in",
    "turns herself in",
    "surrenders",
    "extradited",
    "dies",
    "deceased",
)


def fetch_wordpress_posts(api_root: str, search: str) -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    page = 1
    total_pages = 1

    while page <= total_pages:
        query = urlencode(
            {
                "_embed": "wp:featuredmedia",
                "page": page,
                "per_page": 100,
                "search": search,
            }
        )
        request = Request(
            f"{api_root.rstrip('/')}?{query}",
            headers={
                "Accept": "application/json",
                "Accept-Language": "en-CA,en;q=0.9",
                "User-Agent": USER_AGENT,
            },
        )
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
            total_pages = int(response.headers.get("X-WP-TotalPages", "1"))

        if not isinstance(payload, list):
            raise ValueError("WordPress posts endpoint did not return a list")
        posts.extend(item for item in payload if isinstance(item, dict))
        page += 1

    return posts


def post_title(post: dict[str, Any]) -> str:
    title = post.get("title")
    rendered = title.get("rendered") if isinstance(title, dict) else title
    return clean_text(_parse_html(str(rendered or "")).get_text(" "))


def post_text(post: dict[str, Any]) -> str:
    return clean_text(_parse_html(post_html(post)).get_text(" ", strip=True))


def post_html(post: dict[str, Any]) -> str:
    content = post.get("content")
    rendered = content.get("rendered") if isinstance(content, dict) else content
    return str(rendered or "")


def post_images(post: dict[str, Any]) -> list[str]:
    source_url = clean_text(post.get("link"))
    soup = _parse_html(post_html(post))
    image_urls: list[str] = []

    embedded = post.get("_embedded")
    media_items = embedded.get("wp:featuredmedia", []) if isinstance(embedded, dict) else []
    for media in media_items if isinstance(media_items, list) else []:
        if isinstance(media, dict):
            _append_image(image_urls, source_url, media.get("source_url"))

    for anchor in soup.find_all("a", href=True):
        _append_image(image_urls, source_url, anchor.get("href"))
    for image in soup.find_all("img"):
        for attribute in ("data-large-file", "data-orig-file", "data-src", "src"):
            _append_image(image_urls, source_url, image.get(attribute))

    return image_urls


def gallery_subject_images(post: dict[str, Any]) -> dict[str, list[str]]:
    source_url = clean_text(post.get("link"))
    soup = _parse_html(post_html(post))
    assignments: dict[str, list[str]] = {}

    for item in soup.select(".gallery-item, figure.wp-block-image"):
        caption = item.select_one(".gallery-caption, figcaption")
        name = clean_text(caption.get_text(" ", strip=True)) if caption else ""
        if not looks_like_person_name(name):
            continue

        urls: list[str] = []
        anchor = item.find("a", href=True)
        if anchor:
            _append_image(urls, source_url, anchor.get("href"))
        image = item.find("img")
        if image:
            for attribute in ("data-large-file", "data-orig-file", "data-src", "src"):
                _append_image(urls, source_url, image.get(attribute))
        if urls:
            assignments[name] = urls

    return assignments


def subject_has_later_closure(
    subject: str,
    candidate_post: dict[str, Any],
    posts: list[dict[str, Any]],
) -> bool:
    candidate_date = clean_text(candidate_post.get("date"))
    candidate_id = candidate_post.get("id")
    identities = _identity_candidates(subject)

    for post in posts:
        if post.get("id") == candidate_id:
            continue
        if clean_text(post.get("date")) < candidate_date:
            continue

        title = post_title(post).lower()
        if not any(marker in title for marker in CLOSED_TITLE_MARKERS):
            continue

        normalized_text = normalize_identity(f"{title} {post_text(post)}")
        if any(identity in normalized_text for identity in identities):
            return True
    return False


def has_closed_title(value: str) -> bool:
    lowered = clean_text(value).lower()
    return any(marker in lowered for marker in CLOSED_TITLE_MARKERS)


def looks_like_person_name(value: str) -> bool:
    words = re.findall(r"[A-Za-z][A-Za-z'\-]+", clean_text(value))
    if not 2 <= len(words) <= 5:
        return False
    blocked = {"police", "wanted", "photo", "image", "release", "update"}
    return not any(word.lower() in blocked for word in words)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value)).replace("\u00a0", " ")
    text = (
        text.replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2011", "-")
    )
    return re.sub(r"\s+", " ", text).strip()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", normalize_identity(value)).strip("-")
    return slug or "unknown"


def normalize_identity(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", clean_text(value).lower()).strip()


def _parse_html(value: str) -> BeautifulSoup:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        return BeautifulSoup(value, "html.parser")


def _identity_candidates(subject: str) -> list[str]:
    without_nickname = re.sub(r'["\u201c].+?["\u201d]', " ", subject)
    values = {normalize_identity(subject), normalize_identity(without_nickname)}
    return [value for value in values if len(value.split()) >= 2]


def _append_image(image_urls: list[str], source_url: str, value: Any) -> None:
    candidate = html.unescape(str(value)).strip() if value is not None else ""
    if not candidate or candidate.startswith("data:"):
        return
    image_url = urljoin(source_url, candidate)
    parts = urlsplit(image_url)
    image_url = urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            quote(parts.path, safe="/%:@-._~"),
            parts.query,
            parts.fragment,
        )
    )
    path = urlsplit(image_url).path.lower()
    if not path.endswith((".jpg", ".jpeg", ".png", ".webp")):
        return
    if any(token in path for token in ("logo", "favicon", "placeholder", "no-photo")):
        return
    if image_url not in image_urls:
        image_urls.append(image_url)
