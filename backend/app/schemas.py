from datetime import datetime

from pydantic import BaseModel, Field


class ClipCreate(BaseModel):
    url: str = Field(..., max_length=4096)
    title: str = ""
    summary: str = ""
    image_url: str | None = None
    body_text: str = ""
    # 省略時は body_text から自動（サーバの from-url では HTML 由来の Markdown を設定）
    body_markdown: str | None = None


class ClipFromUrl(BaseModel):
    """サーバが URL を取得して HTML を解析する（拡張機能不要）。"""

    url: str = Field(..., max_length=4096)
    # ブックマークレット等で渡す閲覧中タブのタイトル（省略時はサーバ抽出のみ）
    title: str | None = Field(default=None, max_length=1024)


class TagOut(BaseModel):
    id: int
    name: str
    source: str

    model_config = {"from_attributes": True}


class ClipOut(BaseModel):
    id: int
    url: str
    title: str
    summary: str
    image_url: str | None
    body_text: str
    body_markdown: str
    category: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    tags: list[TagOut] = []

    model_config = {"from_attributes": True}


class BulkIds(BaseModel):
    ids: list[int] = Field(..., min_length=1)


class ClipListResponse(BaseModel):
    items: list[ClipOut]
    total: int
    page: int
    page_size: int


class ClipUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None
    category: str | None = None
    tag_names: list[str] | None = None
    body_text: str | None = None
    body_markdown: str | None = None
