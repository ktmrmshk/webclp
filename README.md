# Webclip

ブラウザで見ているページをローカルに「クリップ」して保存するツールです。FastAPI バックエンド、SQLite、Chrome 拡張（Manifest V3）で構成されています。

## できること

- **拡張機能**: アクティブタブのタイトル・概要・本文抜粋・URL を API に POST して保存
- **サーバのみ**: `POST /api/clips/from-url` で URL を取得し、HTML からメタ情報と本文を抽出（拡張なしでもクリップ可能）
- **一覧 UI** (`/`): 検索・タグ・カテゴリ・ページネーション・表示モード切り替え
- **ゴミ箱**: 削除はソフト削除。`WEBCLIP_TRASH_RETENTION_DAYS`（既定 30 日）経過後に物理削除。一括移動・復元・完全削除に対応
- **Markdown 本文**: `body_markdown` に保存。閲覧は **`/assets/read.html?id=`**（`StaticFiles` で配信。旧 URL `/read.html` は `/assets/read.html` へリダイレクト）

## ディレクトリ構成

```
webclip/
├── Dockerfile         # イメージ定義（ビルドコンテキストは webclip/ ルート）
├── docker-compose.yml
├── docker-entrypoint.sh
├── backend/           # FastAPI アプリ（作業ディレクトリはここを想定）
│   ├── app/           # main, models, db, fetch_page, schemas, …
│   ├── static/        # index.html, read.html, clip.html, bookmarklet.html
│   ├── tests/
│   └── requirements.txt
├── extension/         # Chrome 拡張（「パッケージ化されていない拡張機能を読み込む」）
└── docs/
    └── AGENT_MEMORY.md  # AI/開発向けのプロジェクトメモ
```

## セットアップ（ローカル Python）

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 起動（ローカル Python）

`backend` をカレントにして（`DATABASE_URL` の相対パス `webclip.db` がここにできる）:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 3847
```

ブラウザで `http://127.0.0.1:3847/` を開く。拡張のデフォルト API ベース URL も `http://127.0.0.1:3847` です。

## Docker

イメージ内の作業ディレクトリは `/app` で、SQLite は既定で **`/app/data/webclip.db`**（永続化用にボリュームをマウントしてください）。

### docker compose（推奨）

リポジトリ直下（`webclip/`）で:

```bash
docker compose up -d --build
```

- UI: `http://127.0.0.1:3847/`（ホストのポートを変える場合は環境変数 `WEBCLIP_PORT`、例: `WEBCLIP_PORT=8080 docker compose up -d`）
- データベース: ホストの `./data/webclip.db` にバインドマウント（`data/` は `.gitignore` 済み）

止める・ログ:

```bash
docker compose down
docker compose logs -f webclip
```

`docker-compose.yml` の `environment` で `WEBCLIP_API_TOKEN` などを有効化できます。

### docker コマンドのみ

```bash
cd /path/to/webclip
docker build -t webclip:latest .
mkdir -p data
docker run -d --name webclip \
  -p 3847:3847 \
  -v "$(pwd)/data:/app/data" \
  -e DATABASE_URL=sqlite:////app/data/webclip.db \
  --restart unless-stopped \
  webclip:latest
```

Windows（PowerShell）のボリューム例:

```powershell
docker run -d --name webclip -p 3847:3847 `
  -v "${PWD}/data:/app/data" `
  -e DATABASE_URL=sqlite:////app/data/webclip.db `
  --restart unless-stopped webclip:latest
```

停止・削除: `docker stop webclip && docker rm webclip`

### Docker 利用時の注意

- ブラウザ拡張から叩く場合、API のベース URL は **`http://127.0.0.1:3847`**（ホストで公開しているポート）に合わせる。
- 本リポジトリの `backend/pip.conf`（社内 PyPI 向け）は **Docker ビルドでは取り込まず**、標準の PyPI で `pip install` します。

## 環境変数（`.env` または環境に設定）

| 変数 | 説明 |
|------|------|
| `DATABASE_URL` | 既定: `sqlite:///./webclip.db` |
| `WEBCLIP_API_TOKEN` | 設定すると Bearer 認証に使うトークン文字列 |
| `WEBCLIP_BEARER_AUTH_ENABLED` | `false` ならトークンがあっても `/api` に認証をかけない（既定 `true`） |
| `WEBCLIP_TRASH_RETENTION_DAYS` | ゴミ箱の保持日数（既定 `30`） |

トークンを有効にした場合は、トップページの入力欄に同じ値を保存するか、`Authorization: Bearer …` を付与してください。

## テスト

```bash
cd backend
pytest tests/ -q
```

## 拡張機能の読み込み

Chrome で `chrome://extensions` → デベロッパーモード → 「パッケージ化されていない拡張機能を読み込む」→ `webclip/extension` を選択。オプションで API のベース URL と Bearer を変更可能です。

## 主要な URL

| パス | 内容 |
|------|------|
| `/` | 一覧・編集・ゴミ箱・削除モード |
| `/assets/read.html?id=<clip_id>` | Markdown 本文の閲覧（表示 / ソース切り替え） |
| `/clip.html` | ブックマークレット用 |
| `/api/clips` | REST API（OpenAPI: `/docs`） |

詳しい設計メモや変更履歴は [docs/AGENT_MEMORY.md](docs/AGENT_MEMORY.md) を参照してください。
