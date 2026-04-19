# Webclip

ブラウザで見ているページをローカルに「クリップ」して保存するツールです。FastAPI バックエンド、SQLite、Chrome 拡張（Manifest V3）で構成されています。

## できること

- **拡張機能**: アクティブタブのタイトル・概要・本文抜粋・URL を API に POST して保存
- **サーバのみ**: `POST /api/clips/from-url` で URL を取得し、HTML からメタ情報と本文を抽出（拡張なしでもクリップ可能）
- **一覧 UI** (`/`): 検索・タグ・カテゴリ・ページネーション・表示モード切り替え
- **ゴミ箱**: 削除はソフト削除。`WEBCLIP_TRASH_RETENTION_DAYS`（既定 30 日）経過後に物理削除。一括移動・復元・完全削除に対応
- **Markdown 本文**: `body_markdown` に保存。`GET /read.html?id=` で GitHub 風レンダリングとソース表示を切り替え

## ディレクトリ構成

```
webclip/
├── backend/           # FastAPI アプリ（作業ディレクトリはここを想定）
│   ├── app/           # main, models, db, fetch_page, schemas, …
│   ├── static/        # index.html, read.html, clip.html, bookmarklet.html
│   ├── tests/
│   └── requirements.txt
├── extension/         # Chrome 拡張（「パッケージ化されていない拡張機能を読み込む」）
└── docs/
    └── AGENT_MEMORY.md  # AI/開発向けのプロジェクトメモ
```

## セットアップ

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 起動

`backend` をカレントにして（`DATABASE_URL` の相対パス `webclip.db` がここにできる）:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 3847
```

ブラウザで `http://127.0.0.1:3847/` を開く。拡張のデフォルト API ベース URL も `http://127.0.0.1:3847` です。

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
| `/read.html?id=<clip_id>` | Markdown 本文の閲覧（表示 / ソース切り替え） |
| `/clip.html` | ブックマークレット用 |
| `/api/clips` | REST API（OpenAPI: `/docs`） |

詳しい設計メモや変更履歴は [docs/AGENT_MEMORY.md](docs/AGENT_MEMORY.md) を参照してください。
