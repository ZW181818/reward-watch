from __future__ import annotations

import argparse
import concurrent.futures
import json
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "cases.json"
MEDIA_ROOT = DATA_PATH.parent / "media"
USER_AGENT = "RewardWatchMVP0/0.1 (+official-source-research)"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify official case image URLs.")
    parser.add_argument("--data", type=Path, default=DATA_PATH)
    parser.add_argument("--id-prefix", default="")
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()

    cases = json.loads(args.data.read_text(encoding="utf-8"))
    urls = sorted(
        {
            url
            for case in cases
            if str(case.get("id", "")).startswith(args.id_prefix)
            for url in case.get("imageUrls", [])
            if isinstance(url, str) and url
        }
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        results = list(executor.map(probe_image, urls))

    failures = [result for result in results if not result["healthy"]]
    print(f"Checked {len(urls)} unique image URLs")
    print(f"Healthy: {len(urls) - len(failures)}")
    print(f"Failed: {len(failures)}")
    for failure in failures:
        print(f"- {failure['url']}: {failure['error']}")
    return 1 if failures else 0


def probe_image(url: str) -> dict[str, Any]:
    if url.startswith("/media/"):
        return probe_local_image(url)

    request = Request(
        url,
        headers={
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Range": "bytes=0-0",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            response.read(1)
            content_type = response.headers.get("Content-Type", "")
            healthy = response.status in {200, 206} and content_type.lower().startswith(
                "image/"
            )
            return {
                "url": url,
                "healthy": healthy,
                "error": None if healthy else f"HTTP {response.status} {content_type}",
            }
    except Exception as error:
        return {
            "url": url,
            "healthy": False,
            "error": f"{type(error).__name__}: {error}",
        }


def probe_local_image(url: str) -> dict[str, Any]:
    relative_path = url.removeprefix("/media/")
    path = (MEDIA_ROOT / relative_path).resolve()
    try:
        path.relative_to(MEDIA_ROOT.resolve())
        payload = path.read_bytes()
        healthy = len(payload) >= 32 and payload.startswith(
            (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF8", b"RIFF")
        )
        return {
            "url": url,
            "healthy": healthy,
            "error": None if healthy else "local file is not a recognized image",
        }
    except Exception as error:
        return {
            "url": url,
            "healthy": False,
            "error": f"{type(error).__name__}: {error}",
        }


if __name__ == "__main__":
    raise SystemExit(main())
