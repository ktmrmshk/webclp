"""ゴミ箱（ソフト削除）と一括 API のテスト。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app import models
from app.db import SessionLocal, init_db
from app.main import app, purge_expired_trash
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def _create_clip(client: TestClient, url: str = "https://example.com/a") -> int:
    r = client.post(
        "/api/clips",
        json={
            "url": url,
            "title": "t",
            "summary": "s",
            "body_text": "b",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_delete_moves_to_trash_not_listed(client: TestClient):
    cid = _create_clip(client)
    r = client.delete(f"/api/clips/{cid}")
    assert r.status_code == 200

    listed = client.get("/api/clips")
    assert listed.status_code == 200
    ids = [x["id"] for x in listed.json()["items"]]
    assert cid not in ids

    trash = client.get("/api/clips", params={"trash": True})
    assert trash.status_code == 200
    tids = [x["id"] for x in trash.json()["items"]]
    assert cid in tids


def test_restore_and_bulk_trash(client: TestClient):
    a = _create_clip(client, "https://example.com/x")
    b = _create_clip(client, "https://example.com/y")
    client.delete(f"/api/clips/{a}")
    client.delete(f"/api/clips/{b}")

    r = client.post("/api/clips/bulk/restore", json={"ids": [a, b]})
    assert r.status_code == 200
    assert r.json()["updated"] == 2

    listed = client.get("/api/clips")
    ids = {x["id"] for x in listed.json()["items"]}
    assert a in ids and b in ids

    r2 = client.post("/api/clips/bulk/trash", json={"ids": [a]})
    assert r2.status_code == 200
    assert r2.json()["updated"] == 1


def test_purge_removes_old_trash(client: TestClient):
    cid = _create_clip(client)
    client.delete(f"/api/clips/{cid}")

    db = SessionLocal()
    try:
        clip = db.get(models.Clip, cid)
        assert clip is not None
        clip.deleted_at = datetime.utcnow() - timedelta(days=400)
        db.commit()
    finally:
        db.close()

    db_purge = SessionLocal()
    try:
        n = purge_expired_trash(db_purge)
        assert n >= 1
    finally:
        db_purge.close()

    db = SessionLocal()
    try:
        assert db.get(models.Clip, cid) is None
    finally:
        db.close()
