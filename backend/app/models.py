from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

clip_tag_association = Table(
    "clip_tags",
    Base.metadata,
    Column("clip_id", Integer, ForeignKey("clips.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(4096), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(1024), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    body_text: Mapped[str] = mapped_column(Text, default="")
    # 記事本文（Markdown）。オフライン閲覧・サイト閉鎖後の閲覧用
    body_markdown: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    # 設定時はゴミ箱扱い（NULL = 通常）
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    tags: Mapped[list["Tag"]] = relationship(
        "Tag", secondary=clip_tag_association, back_populates="clips", lazy="selectin"
    )


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("name", name="uq_tag_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), default="manual")

    clips: Mapped[list[Clip]] = relationship(
        "Clip", secondary=clip_tag_association, back_populates="tags", lazy="selectin"
    )
