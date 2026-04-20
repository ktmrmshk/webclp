"""Download images referenced in Markdown and store them locally."""

import hashlib
import logging
import re
from mimetypes import guess_extension
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx

from app.config import settings
from app.fetch_page import DEFAULT_UA

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": DEFAULT_UA,
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Referer": "",  # リクエスト時にページURLで上書き
    "Sec-Fetch-Dest": "image",
    "Sec-Fetch-Mode": "no-cors",
    "Sec-Fetch-Site": "same-origin",
}

# URL とオプションの title ("..." or '...') を分離してキャプチャ
_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(\s+[\"'][^\"']*[\"'])?\)")
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
_TIMEOUT = httpx.Timeout(15.0, connect=10.0)
_NOIMAGE_ALT = re.compile(r"^no[\s_-]*image$", re.IGNORECASE)

_CT_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
    "image/x-icon": ".ico",
    "image/avif": ".avif",
}


def _ext_from_response(resp: httpx.Response, url: str) -> str:
    ct = resp.headers.get("content-type", "").split(";")[0].strip().lower()
    if ct in _CT_EXT:
        return _CT_EXT[ct]
    path = urlparse(url).path
    suffix = Path(path).suffix.lower()
    if suffix and len(suffix) <= 5:
        return suffix
    ext = guess_extension(ct)
    return ext if ext else ".bin"


def _download_image(url: str, client: httpx.Client) -> tuple[bytes, str] | None:
    """Download image bytes and determine extension. Returns None on failure."""
    try:
        resp = client.get(url, follow_redirects=True)
        resp.raise_for_status()
    except (httpx.HTTPError, httpx.InvalidURL) as e:
        logger.warning("Image download failed (%s): %s", url, e)
        return None

    ct = resp.headers.get("content-type", "")
    if not ct.startswith("image/"):
        logger.info("Skipping non-image content-type (%s): %s", ct, url)
        return None

    data = resp.content
    if len(data) > _MAX_BYTES:
        logger.warning("Image too large (%d bytes), skipping: %s", len(data), url)
        return None

    ext = _ext_from_response(resp, url)
    return data, ext


def _save_image(data: bytes, ext: str) -> str:
    """Save image to disk and return the local URL path (/api/images/...)."""
    images_dir = settings.images_dir
    images_dir.mkdir(parents=True, exist_ok=True)

    sha = hashlib.sha256(data).hexdigest()
    filename = f"{sha}{ext}"
    dest = images_dir / filename

    if not dest.exists():
        dest.write_bytes(data)

    return f"/api/images/{filename}"


def _should_skip(url: str) -> bool:
    return (
        url.startswith("data:")
        or url.startswith("/api/images/")
        or not url.strip()
    )


def archive_images_in_markdown(markdown: str, page_url: str) -> str:
    """Download images in markdown and rewrite URLs to local paths."""
    if not markdown:
        return markdown

    # URL → ローカルパス (or 絶対URL) のマッピングを構築
    url_map: dict[str, str] = {}
    raw_urls: list[str] = []
    for _alt, raw_url, _title in _IMG_RE.findall(markdown):
        if raw_url not in url_map:
            if _should_skip(raw_url):
                continue
            abs_url = urljoin(page_url, raw_url)
            url_map[raw_url] = abs_url  # 仮: 絶対URL（DL成功時に上書き）
            raw_urls.append(raw_url)

    if not url_map:
        return markdown

    headers = {**_HEADERS, "Referer": page_url}
    with httpx.Client(timeout=_TIMEOUT, follow_redirects=True, headers=headers) as client:
        for raw_url in raw_urls:
            abs_url = url_map[raw_url]
            result = _download_image(abs_url, client)
            if result is not None:
                data, ext = result
                url_map[raw_url] = _save_image(data, ext)
            # else: abs_url のまま（DL失敗フォールバック）

    def _replace(m: re.Match) -> str:
        alt = m.group(1)
        raw_url = m.group(2)
        title = m.group(3) or ""
        if _NOIMAGE_ALT.match(alt.strip()):
            return ""
        new_url = url_map.get(raw_url, raw_url)
        return f"![{alt}]({new_url}{title})"

    return _IMG_RE.sub(_replace, markdown)


def archive_single_image(url: str) -> str | None:
    """Download a single image (e.g. OG image) and return local URL, or None."""
    if not url or _should_skip(url):
        return None

    headers = {**_HEADERS, "Referer": url}
    with httpx.Client(timeout=_TIMEOUT, follow_redirects=True, headers=headers) as client:
        result = _download_image(url, client)

    if result is None:
        return None

    data, ext = result
    return _save_image(data, ext)
