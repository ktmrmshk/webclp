from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app import models
from app.auto_tag import suggest_category, suggest_tags
from app.bearer_middleware import BearerAuthMiddleware
from app.config import settings
from app.db import SessionLocal, get_db, init_db
from app.fetch_page import fetch_and_extract
from app.image_archiver import archive_images_in_markdown, archive_single_image
from app.markdown_util import markdown_to_plain_preview, plain_text_to_markdown
from app.schemas import BulkIds, ClipCreate, ClipFromUrl, ClipListResponse, ClipOut, ClipUpdate

app = FastAPI(title="Webclip Local API", version="0.1.0")

app.add_middleware(
    BearerAuthMiddleware,
    token=settings.api_token if settings.bearer_auth_active else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=getattr(app, "openapi_version", "3.1.0"),
        routes=app.routes,
    )
    if settings.bearer_auth_active:
        components = openapi_schema.setdefault("components", {})
        components.setdefault("securitySchemes", {})["HTTPBearer"] = {
            "type": "http",
            "scheme": "bearer",
            "description": (
                "WEBCLIP_BEARER_AUTH_ENABLED が有効かつ WEBCLIP_API_TOKEN が設定されているときに必要。"
                "同じ値を入力してください。"
            ),
        }
        openapi_schema["security"] = [{"HTTPBearer": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


def purge_expired_trash(db) -> int:
    """deleted_at から trash_retention_days を超えたクリップを物理削除する。"""
    cutoff = datetime.utcnow() - timedelta(days=settings.trash_retention_days)
    n = (
        db.query(models.Clip)
        .filter(models.Clip.deleted_at.isnot(None))
        .filter(models.Clip.deleted_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return n


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    db = SessionLocal()
    try:
        purge_expired_trash(db)
    finally:
        db.close()


def _get_or_create_tags(db: Session, names: list[str], source: str) -> list[models.Tag]:
    tags: list[models.Tag] = []
    for raw in names:
        name = raw.strip()[:128]
        if not name:
            continue
        t = db.query(models.Tag).filter(models.Tag.name == name).first()
        if not t:
            t = models.Tag(name=name, source=source)
            db.add(t)
            db.flush()
        tags.append(t)
    return tags


def _resolve_body_markdown(payload: ClipCreate) -> str:
    if payload.body_markdown is not None and str(payload.body_markdown).strip():
        return str(payload.body_markdown).strip()
    return plain_text_to_markdown(payload.body_text or "")


def _persist_clip(db: Session, payload: ClipCreate) -> models.Clip:
    auto_names = suggest_tags(payload.title, payload.summary)
    cat = suggest_category(payload.title, payload.summary)

    bm = _resolve_body_markdown(payload)
    bm = archive_images_in_markdown(bm, payload.url)
    archived_og = archive_single_image(payload.image_url) if payload.image_url else None

    bt = (payload.body_text or "").strip()
    if not bt and bm:
        bt = markdown_to_plain_preview(bm)

    clip = models.Clip(
        url=payload.url,
        title=payload.title or "",
        summary=payload.summary or "",
        image_url=archived_og or payload.image_url,
        body_text=bt,
        body_markdown=bm,
        category=cat,
    )
    db.add(clip)
    db.flush()

    tags = _get_or_create_tags(db, auto_names, source="auto")
    clip.tags.extend(tags)
    db.commit()
    db.refresh(clip)
    return clip


@app.post("/api/clips", response_model=ClipOut)
def create_clip(payload: ClipCreate, db: Session = Depends(get_db)):
    return _persist_clip(db, payload)


@app.post("/api/clips/from-url", response_model=ClipOut)
def create_clip_from_url(payload: ClipFromUrl, db: Session = Depends(get_db)):
    """ブラウザ拡張なし: サーバが URL を GET して HTML からメタ情報・本文を抽出する。"""
    try:
        extracted = fetch_and_extract(payload.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ページの取得に失敗しました: {e}") from e

    client_title = (payload.title or "").strip()
    resolved_title = client_title if client_title else str(extracted["title"] or "")
    bm_raw = extracted.get("body_markdown")
    clip_payload = ClipCreate(
        url=str(extracted["url"]),
        title=resolved_title,
        summary=str(extracted["summary"] or ""),
        image_url=extracted["image_url"],
        body_text=str(extracted["body_text"] or ""),
        body_markdown=str(bm_raw).strip() if bm_raw else None,
    )
    return _persist_clip(db, clip_payload)


def _clips_filtered_query(
    db: Session,
    q: str | None,
    tag: str | None,
    category: str | None,
    *,
    trash: bool,
    date_from: str | None = None,
    date_to: str | None = None,
):
    query = db.query(models.Clip)
    if trash:
        query = query.filter(models.Clip.deleted_at.isnot(None))
    else:
        query = query.filter(models.Clip.deleted_at.is_(None))
    if q:
        like = f"%{q}%"
        query = query.filter(
            (models.Clip.title.ilike(like))
            | (models.Clip.summary.ilike(like))
            | (models.Clip.url.ilike(like))
        )
    if category:
        query = query.filter(models.Clip.category == category)
    if tag:
        query = query.join(models.Clip.tags).filter(models.Tag.name == tag).distinct()
    if date_from:
        try:
            dt = datetime.fromisoformat(date_from)
            query = query.filter(models.Clip.created_at >= dt)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.fromisoformat(date_to) + timedelta(days=1)
            query = query.filter(models.Clip.created_at < dt)
        except ValueError:
            pass
    return query


def _distinct_clip_categories(db: Session) -> list[str]:
    rows = (
        db.query(models.Clip.category)
        .filter(models.Clip.deleted_at.is_(None))
        .filter(models.Clip.category.isnot(None))
        .filter(models.Clip.category != "")
        .distinct()
        .all()
    )
    return sorted({r[0] for r in rows if r[0]})


# /api/clips/{clip_id} とパスが被らないよう /api/categories に集約（旧URLも互換で残す）
@app.get("/api/categories", response_model=list[str])
def list_categories(db: Session = Depends(get_db)):
    return _distinct_clip_categories(db)


@app.get("/api/clips/categories", response_model=list[str])
def list_clip_categories_legacy(db: Session = Depends(get_db)):
    return _distinct_clip_categories(db)


@app.get("/api/clips", response_model=ClipListResponse)
def list_clips(
    q: str | None = None,
    tag: str | None = None,
    category: str | None = None,
    trash: bool = False,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_db),
):
    purge_expired_trash(db)
    base = _clips_filtered_query(db, q, tag, category, trash=trash, date_from=date_from, date_to=date_to)
    total = base.count()
    ordered = _clips_filtered_query(db, q, tag, category, trash=trash, date_from=date_from, date_to=date_to)
    if trash:
        ordered = ordered.order_by(models.Clip.deleted_at.desc())
    else:
        ordered = ordered.order_by(models.Clip.created_at.desc())
    clips = (
        ordered.offset((page - 1) * page_size).limit(page_size).all()
    )
    return ClipListResponse(items=clips, total=total, page=page, page_size=page_size)


@app.post("/api/clips/bulk/trash")
def bulk_move_to_trash(body: BulkIds, db: Session = Depends(get_db)):
    now = datetime.utcnow()
    n = 0
    for cid in body.ids:
        clip = db.get(models.Clip, cid)
        if clip and clip.deleted_at is None:
            clip.deleted_at = now
            n += 1
    db.commit()
    return {"ok": True, "updated": n}


@app.post("/api/clips/bulk/restore")
def bulk_restore(body: BulkIds, db: Session = Depends(get_db)):
    n = 0
    for cid in body.ids:
        clip = db.get(models.Clip, cid)
        if clip and clip.deleted_at is not None:
            clip.deleted_at = None
            n += 1
    db.commit()
    return {"ok": True, "updated": n}


@app.delete("/api/clips/bulk/permanent")
def bulk_permanent_delete(body: BulkIds, db: Session = Depends(get_db)):
    n = 0
    for cid in body.ids:
        clip = db.get(models.Clip, cid)
        if clip and clip.deleted_at is not None:
            db.delete(clip)
            n += 1
    db.commit()
    return {"ok": True, "deleted": n}


@app.get("/api/clips/{clip_id}", response_model=ClipOut)
def get_clip(clip_id: int, db: Session = Depends(get_db)):
    clip = db.get(models.Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="clip not found")
    return clip


@app.patch("/api/clips/{clip_id}", response_model=ClipOut)
def update_clip(clip_id: int, body: ClipUpdate, db: Session = Depends(get_db)):
    clip = db.get(models.Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="clip not found")
    if clip.deleted_at is not None:
        raise HTTPException(
            status_code=400,
            detail="ゴミ箱のクリップは編集できません。先に復元してください。",
        )
    if body.title is not None:
        clip.title = body.title
    if body.summary is not None:
        clip.summary = body.summary
    if body.category is not None:
        clip.category = body.category or None
    if body.body_markdown is not None:
        clip.body_markdown = body.body_markdown
        clip.body_text = markdown_to_plain_preview(body.body_markdown)
    elif body.body_text is not None:
        clip.body_text = body.body_text
    if body.tag_names is not None:
        tags = _get_or_create_tags(db, body.tag_names, source="manual")
        clip.tags = tags
    db.commit()
    db.refresh(clip)
    return clip


@app.delete("/api/clips/{clip_id}")
def delete_clip(clip_id: int, db: Session = Depends(get_db)):
    clip = db.get(models.Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="clip not found")
    if clip.deleted_at is not None:
        raise HTTPException(status_code=400, detail="すでにゴミ箱にあります")
    clip.deleted_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@app.post("/api/clips/{clip_id}/restore", response_model=ClipOut)
def restore_clip(clip_id: int, db: Session = Depends(get_db)):
    clip = db.get(models.Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="clip not found")
    if clip.deleted_at is None:
        raise HTTPException(status_code=400, detail="ゴミ箱にありません")
    clip.deleted_at = None
    db.commit()
    db.refresh(clip)
    return clip


@app.delete("/api/clips/{clip_id}/permanent")
def permanent_delete_clip(clip_id: int, db: Session = Depends(get_db)):
    clip = db.get(models.Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="clip not found")
    if clip.deleted_at is None:
        raise HTTPException(
            status_code=400,
            detail="完全削除はゴミ箱のクリップのみ可能です",
        )
    db.delete(clip)
    db.commit()
    return {"ok": True}


@app.get("/api/tags", response_model=list[dict])
def list_tags(db: Session = Depends(get_db)):
    rows = db.query(models.Tag).order_by(models.Tag.name).all()
    return [{"id": t.id, "name": t.name, "source": t.source} for t in rows]


images_path = settings.images_dir
images_path.mkdir(parents=True, exist_ok=True)
app.mount("/api/images", StaticFiles(directory=images_path), name="archived-images")

static_path = settings.static_dir
if static_path.is_dir():
    app.mount("/assets", StaticFiles(directory=static_path), name="assets")


def _static_file(name: str) -> FileResponse:
    f = static_path / name
    if not f.is_file():
        raise HTTPException(status_code=404, detail="static file not found")
    return FileResponse(f)


@app.get("/")
def index():
    index_file = static_path / "index.html"
    if not index_file.is_file():
        return {"message": "Run from backend/ with static/index.html present."}
    return FileResponse(index_file)


@app.get("/clip.html")
def clip_landing():
    """ブックマークレット用: ?url= で開き、クライアントが /api/clips/from-url を呼ぶ。"""
    return _static_file("clip.html")


@app.get("/bookmarklet.html")
def bookmarklet_help():
    """ブックマークレットのコピー用ページ。"""
    return _static_file("bookmarklet.html")


@app.get("/read.html")
def read_article_page_redirect(request: Request):
    """正規 URL は /assets/read.html（StaticFiles）。旧ブックマーク互換でリダイレクト。"""
    q = request.url.query
    loc = "/assets/read.html" + ("?" + q if q else "")
    return RedirectResponse(url=loc, status_code=307)


@app.get("/read")
def read_article_short_redirect(request: Request):
    """同上。本文閲覧の正規パスは /assets/read.html 。"""
    q = request.url.query
    loc = "/assets/read.html" + ("?" + q if q else "")
    return RedirectResponse(url=loc, status_code=307)
