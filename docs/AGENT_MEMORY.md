# Webclip — エージェント / 開発者向けメモ

このファイルは、以降の AI エージェントや開発者が文脈を掴むための **プロジェクト記憶** です。ユーザー向け手順は [README.md](../README.md) を参照。

---

## 1. 目的とスタック

- **目的**: ウェブページをローカルにクリップし、あとから検索・閲覧できるようにする。オリジナルサイトが消えても **Markdown 本文** (`body_markdown`) で読み返せることを重視。
- **バックエンド**: Python 3.10+ / FastAPI / SQLAlchemy 2 / SQLite（既定 `backend/webclip.db`）。
- **フロント**: `backend/static/` の素の HTML + インライン JS（ビルドなし）。
- **拡張**: `extension/` — `background.js` が `chrome.scripting.executeScript` でページからテキスト抽出し `POST /api/clips`。

---

## 2. ディレクトリと責務

| 場所 | 役割 |
|------|------|
| `backend/app/main.py` | ルート定義。`/api/clips/bulk/*` は `/api/clips/{id}` より **先に** 定義（パス衝突回避）。 |
| `backend/app/models.py` | `Clip`（`body_text`, `body_markdown`, `deleted_at`, …）、`Tag`、多対多 `clip_tags`。 |
| `backend/app/db.py` | `init_db()` で `create_all` + SQLite マイグレーション。`get_db()` 先頭で `init_db()` を呼び、**初回 API アクセスでもマイグレーションが確実に走る**ようにしている。 |
| `backend/app/fetch_page.py` | `fetch_and_extract`: httpx で HTML 取得、`BeautifulSoup` + **markdownify** で本文 HTML→Markdown。 |
| `backend/app/markdown_util.py` | プレーンテキスト→段落 Markdown、Markdown→プレーン（検索用）の補助。 |
| `backend/app/schemas.py` | Pydantic。`ClipOut` に `body_markdown` / `deleted_at` など。 |
| `backend/app/bearer_middleware.py` | `/api/*` に Bearer（`WEBCLIP_API_TOKEN` と一致）を要求。 |
| `backend/static/index.html` | 一覧 UI。トークンは `sessionStorage` の `webclip_bearer_token`。 |
| `backend/static/read.html` | `marked` + `DOMPurify` + `github-markdown-dark`（CDN）。`?id=` で `/api/clips/{id}` を取得。 |

---

## 3. 実装済み機能のヒストリ（要約）

### ゴミ箱・一括操作

- **ソフト削除**: `Clip.deleted_at`。`DELETE /api/clips/{id}` は物理削除ではなく `deleted_at` 設定。
- **一覧**: `GET /api/clips?trash=true` でゴミ箱のみ。
- **一括**: `POST /api/clips/bulk/trash`, `bulk/restore`, `DELETE /api/clips/bulk/permanent`（JSON `{"ids":[...]}`）。
- **パージ**: `purge_expired_trash()` — `deleted_at` が `WEBCLIP_TRASH_RETENTION_DAYS` より古い行を物理削除。起動時および一覧取得時に実行。
- **UI**: 「ゴミ箱」トグル、「削除モード」でチェックボックス + 一括操作。編集はゴミ箱中は不可（400）。

### DB マイグレーション（SQLite）

- `deleted_at` 列が無い既存 DB へ `ALTER TABLE ... ADD COLUMN deleted_at`。
- `body_markdown` 列: `ALTER TABLE ... ADD COLUMN body_markdown TEXT NOT NULL DEFAULT ''`。
- **トラブル事例**: `deleted_at` 未適用のまま API が動くと UPDATE が 500 → **`get_db()` で毎リクエスト前に `init_db()`** を挟むよう修正済み。

### Markdown 本文と閲覧ページ

- **保存**: `body_markdown`。from-url は HTML から markdownify。拡張のみのクリップはプレーン `body_text` から段落 Markdown を生成。
- **検索用**: `body_text` は一覧・検索向けにプレーン化（編集で `body_markdown` 更新時に `markdown_to_plain_preview` で同期）。
- **閲覧**: `/read.html?id=` — 「表示」と「Markdown」切り替え。`body_markdown` が空なら `body_text` にフォールバック。

### フロントの互換

- 一覧 API は `{ items, total, page, page_size }`。古い配列形式にもフォールバック処理あり。
- カテゴリは `GET /api/categories`（`Array.isArray` で防御）。

---

## 4. 変更時の注意

- **スキーマ追加**: `models.py` に加え、`db.py` に SQLite `ALTER` マイグレーションを追加し、`init_db()` から呼ぶ。
- **認証**: トークン有効時、ブラウザは `sessionStorage` のトークンを付与。`read.html` も同じキー。
- **拡張**: デフォルト API は `http://127.0.0.1:3847`。サーバのポートと合わせる。
- **テスト**: `tests/conftest.py` が **import 前**に `DATABASE_URL` を tempfile SQLite に固定。`pytest` は `backend` から実行。

---

## 5. Docker

- **`Dockerfile`**: コンテキストは `webclip/` ルート。`backend/` を `/app` にコピーし `uvicorn app.main:app`。
- **DB パス**: 既定 `DATABASE_URL=sqlite:////app/data/webclip.db`（4 スラッシュは絶対パス）。`docker-compose.yml` は `./data:/app/data` をマウント。
- **`docker-entrypoint.sh`**: `/app/data` を作成してから uvicorn 起動。
- **`.dockerignore`**: `backend/pip.conf` を除外（社内 PyPI 依存をビルドに持ち込まない）。`extension/` や `docs/` もイメージに不要なため除外。
- **Compose**: `WEBCLIP_PORT` でホスト側ポートを変更可能。

## 6. よく触るコマンド

```bash
cd backend
pytest tests/ -q
uvicorn app.main:app --reload --host 127.0.0.1 --port 3847
```

```bash
# リポジトリ直下
docker compose up -d --build
```

---

## 7. 未着手 / 任意の拡張アイデア

- 拡張から **HTML 断片**を送り、サーバで markdownify する（現状はプレーンテキスト→Markdown のみ）。
- `WEBCLIP_TRASH_RETENTION_DAYS` をフロントの「30日」表記と API で共有（現状は文言が既定値前提）。
- FastAPI `on_event("startup")` の lifespan への移行（非推奨警告あり）。

---

*最終更新: 会話ベースの開発履歴を反映したスナップショット。大きな変更が入ったらこのファイルも更新すること。*
