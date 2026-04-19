"""Markdown 本文と read ページのスモークテスト。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_read_html_static_served() -> None:
    """本文閲覧は StaticFiles の /assets/read.html が正規。/read.html はリダイレクト。"""
    with TestClient(app) as client:
        r = client.get("/assets/read.html")
        assert r.status_code == 200
        assert b"markdown-body" in r.content or b"github-markdown" in r.content

        redir = client.get("/read.html", follow_redirects=False)
        assert redir.status_code == 307
        assert redir.headers.get("location", "").startswith("/assets/read.html")

        r_follow = client.get("/read.html", follow_redirects=True)
        assert r_follow.status_code == 200
        assert b"markdown-body" in r_follow.content or b"github-markdown" in r_follow.content


def test_post_clip_includes_body_markdown() -> None:
    with TestClient(app) as client:
        r = client.post(
            "/api/clips",
            json={
                "url": "https://example.com/md-test",
                "title": "Title",
                "body_text": "Paragraph one.\n\nParagraph two.",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert "body_markdown" in data
        assert "Paragraph" in data["body_markdown"]
