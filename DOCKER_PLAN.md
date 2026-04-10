# Docker 対応計画書

> 作成日: 2026-04-10  
> ステータス: 設計中  
> Claude CLI 戦略: **方法② — コンテナ内インストール ＋ `~/.claude` マウント**

---

## 1. 方針

### Claude CLI の扱い（方法②）

ホストマシンのバイナリをコンテナにマウントする方法（方法①）は、macOS ホスト ↔ Linux コンテナの ABI 非互換により動作しない。そのため以下の方針を採用する。

| 項目 | 方針 |
|---|---|
| **Claude CLI バイナリ** | コンテナイメージ内に `npm install -g @anthropic-ai/claude-code` でインストール |
| **認証情報（`~/.claude`）** | ホストの `~/.claude` をコンテナの `/root/.claude` にバインドマウント |
| **初回ログイン** | ホストで `claude login` を一度実行するだけで OK（コンテナ内で再ログイン不要） |

```
ホスト ~/.claude/  ──────────────────────────────────────────────────────────────────────── bind mount ──▶  コンテナ /root/.claude/
（認証トークンが格納される）                                                                         （コンテナ内の claude コマンドが参照）
```

### Docker Compose 全体構成

```
docker compose up
  ├── api         (FastAPI + Discord Bot + APScheduler + Playwright)
  ├── frontend    (Next.js)
  └── cloudflared (Cloudflare Tunnel — 任意)
```

---

## 2. サービス設計

### 2-1. `api` サービス

| 項目 | 内容 |
|---|---|
| **ベースイメージ** | `mcr.microsoft.com/playwright/python:v1.50.0-jammy` |
| **理由** | Python + Chromium + 必要な Linux ライブラリが同梱済み。`services/twitter.py` が Playwright を使うため自前でブラウザをインストールする手間が省ける |
| **追加インストール** | Node.js（LTS）、`@anthropic-ai/claude-code`（Claude CLI）、uv、Python 依存関係 |
| **起動コマンド** | `uv run python main.py`（FastAPI + Discord Bot を同一プロセスで起動） |
| **ポート** | `8080:8080` |

**永続化ボリューム**

| ホストパス | コンテナパス | 用途 |
|---|---|---|
| `./promo.db` | `/app/promo.db` | SQLite DB |
| `./assets` | `/app/assets` | ゲーム素材ファイル |
| `./twitter_session.json` | `/app/twitter_session.json` | Playwright ログインセッション |
| `~/.claude` | `/root/.claude` | Claude CLI 認証情報（ホストと共有） |

> **注意**：`prompts/` は読み取り専用のソースコード管理下にあるためマウント不要（イメージに COPY する）。

---

### 2-2. `frontend` サービス

| 項目 | 内容 |
|---|---|
| **ベースイメージ** | `node:20-alpine` |
| **起動コマンド** | `npm start`（本番） / `npm run dev`（開発時は `command` をオーバーライド） |
| **ポート** | `3000:3000` |
| **ビルド** | マルチステージビルド（`npm run build` → `node_modules` をコピー） |

---

### 2-3. `cloudflared` サービス

| 項目 | 内容 |
|---|---|
| **イメージ** | `cloudflare/cloudflared:latest` |
| **起動条件** | `TUNNEL_TOKEN` 環境変数が設定されている場合のみ有効（`profiles: [tunnel]`） |
| **コマンド** | `tunnel --no-autoupdate run --token ${TUNNEL_TOKEN}` |

---

## 3. ファイル構成（追加分）

```
game-promo-hub/
├── Dockerfile.api          # api サービス用（新規）
├── frontend/
│   └── Dockerfile          # frontend サービス用（新規）
├── compose.yaml            # Docker Compose 定義（新規）
├── .dockerignore           # Docker ビルド除外設定（新規）
└── .env.example            # TUNNEL_TOKEN 等の追加変数（更新）
```

---

## 4. 各ファイルの設計

### Dockerfile.api（設計案）

```dockerfile
# ---- ベース ----
FROM mcr.microsoft.com/playwright/python:v1.50.0-jammy

WORKDIR /app

# Node.js LTS + Claude CLI のインストール
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# uv のインストール
RUN pip install uv

# Python 依存関係のインストール（キャッシュ効率のため先にロックファイルをコピー）
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev

# アプリケーションコードのコピー
COPY . .

# Playwright ブラウザはベースイメージ同梱のものを使用（追加インストール不要）

CMD ["uv", "run", "python", "main.py"]
```

**ポイント**：
- `playwright install` は不要（ベースイメージに Chromium が同梱済み）
- `twitter.py` の `--no-sandbox` フラグは Docker 環境用に既に設定済み

---

### frontend/Dockerfile（設計案）

```dockerfile
# ---- 依存関係インストールステージ ----
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# ---- ビルドステージ ----
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ---- 本番ランタイムステージ ----
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

**ポイント**：
- Next.js の `output: 'standalone'` を `next.config.ts` に設定する必要がある

---

### compose.yaml（設計案）

```yaml
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    ports:
      - "8080:8080"
    volumes:
      - ./promo.db:/app/promo.db
      - ./assets:/app/assets
      - ./twitter_session.json:/app/twitter_session.json
      - "${CLAUDE_CONFIG_DIR:-~/.claude}:/root/.claude"
    env_file:
      - .env
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    env_file:
      - ./frontend/.env.local
    depends_on:
      - api
    restart: unless-stopped

  cloudflared:
    image: cloudflare/cloudflared:latest
    command: tunnel --no-autoupdate run --token ${TUNNEL_TOKEN}
    profiles:
      - tunnel
    depends_on:
      - api
      - frontend
    restart: unless-stopped
```

**ポイント**：
- `CLAUDE_CONFIG_DIR` 環境変数でマウント元を上書き可能（デフォルト `~/.claude`）
- `cloudflared` は `profiles: [tunnel]` で任意起動（`docker compose --profile tunnel up`）
- `twitter_session.json` は初回起動時に存在しなくてもよい（`touch twitter_session.json` をドキュメントに記載）

---

### .dockerignore（設計案）

```
.git
.env
.env.*
!.env.example
__pycache__
*.pyc
*.pyo
promo.db
twitter_session.json
assets/
node_modules/
frontend/.next/
frontend/node_modules/
```

---

## 5. 環境変数の追加（`.env.example` 更新分）

```env
# Docker / Claude CLI
# Claude CLI 認証ファイルのホスト側パス（デフォルト: ~/.claude）
# macOS の場合は通常 /Users/<username>/.claude
CLAUDE_CONFIG_DIR=~/.claude

# Cloudflare Tunnel（docker compose --profile tunnel up の場合のみ必要）
TUNNEL_TOKEN=your_cloudflare_tunnel_token
```

---

## 6. 前提条件・事前準備

Docker Compose を使う前にホストマシンで一度だけ行う作業。

```bash
# 1. Claude CLI にホストでログイン（~/.claude に認証情報が保存される）
claude login

# 2. twitter_session.json の空ファイル作成（初回起動時にコンテナ内で書き込まれる）
touch twitter_session.json

# 3. assets ディレクトリの作成（存在しない場合）
mkdir -p assets
```

---

## 7. 起動コマンド

```bash
# 通常起動（Next.js + FastAPI）
docker compose up -d

# Cloudflare Tunnel も含めて起動
docker compose --profile tunnel up -d

# ログ確認
docker compose logs -f api
docker compose logs -f frontend

# 再ビルド（Dockerfile を変更した場合）
docker compose build --no-cache api
docker compose up -d
```

---

## 8. 実装フェーズ

| フェーズ | 内容 | 完了条件 |
|---|---|---|
| **Phase 1** | `Dockerfile.api` 作成・動作確認 | `claude --version` がコンテナ内で実行できる。FastAPI / Discord Bot が起動する |
| **Phase 2** | `frontend/Dockerfile` 作成・動作確認 | Next.js の本番ビルドが通る |
| **Phase 3** | `compose.yaml` 作成・結合テスト | `docker compose up` で全サービスが起動し、フロントエンドから API へ疎通する |
| **Phase 4** | `.dockerignore` / `.env.example` 更新 | 不要ファイルがイメージに含まれない |
| **Phase 5** | Cloudflare Tunnel プロファイル追加・本番確認 | `void2610.dev` / `api.void2610.dev` でアクセスできる |

---

## 9. 注意事項・既知の制約

| 項目 | 内容 |
|---|---|
| **Claude CLI バージョン** | `npm install -g @anthropic-ai/claude-code` は最新版がインストールされる。バージョンを固定する場合は `@anthropic-ai/claude-code@x.y.z` と指定する |
| **Claude の認証** | `~/.claude` がホストに存在しない場合、コンテナ起動後に `docker compose exec api claude login` で認証する |
| **Playwright ブラウザ** | ベースイメージ `mcr.microsoft.com/playwright/python` のバージョンを `pyproject.toml` の `playwright>=1.50.0` と揃えること |
| **SQLite のロック** | ホスト側とコンテナで同一の `promo.db` を共有するため、ホスト側で別プロセスが DB を開いているとロックエラーになる |
| **macOS での `~/.claude` パス** | Compose の `~` 展開はシェル依存。`.env` に `CLAUDE_CONFIG_DIR=/Users/<username>/.claude` を明示的に設定することを推奨 |
| **`twitter_session.json` の存在** | バインドマウントは対象ファイルが存在しないと **ディレクトリ** として作成される。必ず `touch twitter_session.json` で空ファイルを作ってからコンテナを起動すること |
