"""Fetch a public URL server-side and extract clip fields (no browser extension)."""

from __future__ import annotations

import re
from urllib.parse import urlparse, urljoin

import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify as html_to_markdown

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Webclip/0.1"
)


def validate_public_http_url(url: str) -> str:
    u = url.strip()
    parsed = urlparse(u)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("URL は http または https である必要があります")
    if not parsed.netloc:
        raise ValueError("URL が不正です")
    return u


def extract_from_html(html: str, page_url: str) -> dict[str, str | None]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    def meta_prop(prop: str) -> str | None:
        el = soup.find("meta", attrs={"property": prop})
        if el and el.get("content"):
            return str(el["content"]).strip()
        return None

    def meta_name(name: str) -> str | None:
        el = soup.find("meta", attrs={"name": name})
        if el and el.get("content"):
            return str(el["content"]).strip()
        return None

    og_title = meta_prop("og:title")
    og_desc = meta_prop("og:description")
    og_image = meta_prop("og:image")
    tw_image = meta_name("twitter:image")
    desc = meta_name("description")

    title = og_title or ""
    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()

    root = (
        soup.find("article")
        or soup.find("main")
        or soup.select_one('[role="main"]')
        or soup.body
    )
    # 相対 URL を絶対 URL に変換（<a href>, <img src>）
    for a in soup.find_all("a", href=True):
        a["href"] = urljoin(page_url, a["href"])
    for img in soup.find_all("img", src=True):
        img["src"] = urljoin(page_url, img["src"])

    text = ""
    body_md = ""
    if root:
        text = re.sub(r"\s+", " ", root.get_text(separator=" ", strip=True))
        if len(text) > 50000:
            text = text[:50000]
        try:
            body_md = html_to_markdown(
                str(root),
                heading_style="ATX",
                bullets="-",
                strip=["script", "style", "noscript"],
            )
            body_md = re.sub(r"\n{3,}", "\n\n", body_md).strip()
            if len(body_md) > 500000:
                body_md = body_md[:500000]
        except Exception:
            body_md = ""

    summary = og_desc or desc or ""
    if not summary and text:
        summary = text[:500]

    image_url: str | None = og_image or tw_image or None
    if image_url:
        image_url = urljoin(page_url, image_url)

    return {
        "url": page_url,
        "title": title,
        "summary": summary,
        "image_url": image_url,
        "body_text": text,
        "body_markdown": body_md or "",
    }


def fetch_and_extract(url: str) -> dict[str, str | None]:
    validate_public_http_url(url)
    headers = {"User-Agent": DEFAULT_UA, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"}
    with httpx.Client(timeout=30.0, follow_redirects=True, headers=headers) as client:
        try:
            resp = client.get(url)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ValueError(f"HTTP {e.response.status_code}: {url}") from e
        except httpx.RequestError as e:
            raise ValueError(f"接続に失敗しました: {e}") from e
        final_url = str(resp.url)
        ctype = resp.headers.get("content-type", "")
        if "html" not in ctype.lower() and "text/plain" not in ctype.lower():
            raise ValueError(f"HTML ではないためスキップしました (Content-Type: {ctype})")
        html = resp.text
    return extract_from_html(html, final_url)
