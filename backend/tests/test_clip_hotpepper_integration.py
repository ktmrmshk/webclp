"""
指定 URL を from-url で取り込み、一覧 API で取得できることを確認する（ネットワーク必須）。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

HOTPEPPER_URL = "https://www.hotpepper.jp/mesitsu/entry/chimidoro/19-00062"


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_clip_from_url_hotpepper_then_list(client: TestClient) -> None:
    """POST /api/clips/from-url で登録し、GET /api/clips で1件以上含まれること。"""
    create = client.post("/api/clips/from-url", json={"url": HOTPEPPER_URL})
    if create.status_code != 200:
        pytest.skip(
            f"外部サイトの取得に失敗しました（オフライン・ブロック・タイムアウト等）: "
            f"{create.status_code} {create.text[:300]}"
        )

    row = create.json()
    assert row.get("id") is not None
    assert row.get("url")
    assert "hotpepper" in row["url"].lower()

    listed = client.get("/api/clips", params={"page": 1, "page_size": 24})
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert "items" in body
    assert "total" in body
    assert body["total"] >= 1

    urls = [it["url"] for it in body["items"]]
    assert any(HOTPEPPER_URL in u or "19-00062" in u for u in urls), (
        f"一覧に取り込みURLが見つかりません: {urls}"
    )


def test_categories_and_tags_endpoints(client: TestClient) -> None:
    """フィルタ用 API が配列を返す（フロント互換）。"""
    r = client.get("/api/categories")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    r2 = client.get("/api/tags")
    assert r2.status_code == 200
    assert isinstance(r2.json(), list)
