# Game Promo Hub — アーキテクチャ設計書

> 作成日: 2026-04-10  
> 更新日: 2026-04-10  
> ステータス: 決定済み（Next.js + Cloudflare Tunnel 採用）

---

## 1. 背景・方針転換

### 現状の問題点

| 問題 | 詳細 |
|---|---|
| Discord Modal の制約 | 1 Modal に 5 フィールドまで・テキストのみ |
| データ閲覧性が低い | Embed での表示は 25 件制限・検索・ソート不可 |
| 入力 UX が悪い | スラッシュコマンドは反復作業に向かない |
| 承認フローの見通しが悪い | 複数 pending 下書きをまとめて管理しづらい |
| Discord 依存度が高い | 操作端末が Discord アプリに限定される |

### 新しい方針

```
「操作の主体」を Discord → Web UI に移す。

Discord の役割
  ├── Web UI へのリンク共有
  ├── 定期的なリマインド通知（未ログイン、pending 下書きあり など）
  └── 実行結果報告（ツイート投稿完了、アナリティクス更新 など）

Web UI の役割
  ├── 全テーブルの CRUD 操作（ゲーム・進捗・アピール・素材・下書き・スケジュール）
  ├── 下書きの一覧・承認・却下
  ├── アナリティクスダッシュボード
  └── スケジュール管理
```

---

## 2. 現行アーキテクチャ

```
ユーザー
  │ Discord slash commands
  ▼
Discord Bot (discord.py)
  ├── cogs/game_cog.py       /game_add, /game_list
  ├── cogs/progress_cog.py   /progress_add
  ├── cogs/appeal_cog.py     /appeal_add
  ├── cogs/asset_cog.py      /asset_add
  ├── cogs/promo_cog.py      /promo_draft, /draft_list, 承認ボタン
  ├── cogs/analytics_cog.py  /analytics_fetch, /analytics_report
  └── cogs/schedule_cog.py   /schedule_slot_add など
        │
  ├── services/db.py         (aiosqlite → SQLite)
  ├── services/llm.py        (Claude CLI サブプロセス)
  ├── services/twitter.py    (Playwright スクレイピング)
  └── services/scheduler.py  (APScheduler — 定期投稿・メトリクス収集)
```

---

## 3. 新アーキテクチャ

### 全体像

```
ユーザー（ブラウザ）
  │ HTTPS（Cloudflare Tunnel → void2610.dev）
  ▼
┌──────────────────────────────────┐
│  Next.js 15（App Router / TS）   │  ← 操作の主体（フロントエンド）
│  ポート 3000                      │
└────────────┬─────────────────────┘
             │ REST API (fetch / Server Actions)
             ▼
┌──────────────────────────────────┐
│  FastAPI（Python / async）        │  ← バックエンド API
│  ポート 8080                      │
└────────────┬─────────────────────┘
             │ aiosqlite
             ▼
         SQLite DB
             │
       ┌─────┴────────────────┐
       │                      │
       ▼                      ▼
services/llm.py       services/twitter.py
(Claude CLI)          (Playwright)

Discord Bot（通知専用・同一プロセス内で共存）
  ├── Web URL 共有（void2610.dev）
  ├── 定期リマインド（APScheduler から呼び出し）
  └── 投稿完了・分析結果の通知

Cloudflare Tunnel
  └── void2610.dev → localhost:3000（Next.js）
                  （または /api/* → localhost:8080 を split routing で）
```

### コンポーネント間の関係

```
[APScheduler]
    │
    ├─ 毎分 tick   → Twitter 定期投稿（スロット一致時）
    ├─ 6時間ごと   → メトリクス自動取得
    └─ 毎日朝 9時  → Discord へ「本日の状況」リマインド通知

[FastAPI]
    ├─ /api/*      → REST API エンドポイント（CRUD・JSON）
    └─ 起動時      → DB 初期化・Scheduler 起動・Discord Bot 起動

[Next.js]
    ├─ app/        → App Router ページ・レイアウト
    ├─ app/api/*   → Route Handlers（認証チェック後 FastAPI へ proxy）
    └─ 環境変数    → NEXT_PUBLIC_API_URL, NEXTAUTH_SECRET 等

[Discord Bot]
    ├─ on_ready    → 起動通知（Web UI の URL: https://void2610.dev も掲載）
    └─ スラッシュコマンド（最小限）
         /link    → Web UI の URL を Ephemeral で返す
         /status  → キュー・スロット・ゲーム数のサマリー（詳細は Web へ）
```

---

## 4. 技術スタック

### 採用構成（Next.js フルスタック）

| レイヤー | 技術 | 理由 |
|---|---|---|
| **フロントエンド** | [Next.js 15](https://nextjs.org/)（App Router・TypeScript） | Next.js の採用経験が豊富なため最初から採用。RSC・Server Actions で UX が高い |
| **バックエンド API** | [FastAPI](https://fastapi.tiangolo.com/)（Python） | 既存 services/\* 資産をそのまま流用。async 対応・型安全 |
| **認証** | [NextAuth.js v5](https://authjs.dev/)（Credentials Provider） | Next.js と統合しやすい。個人ツールなので最小限構成 |
| **CSS** | [TailwindCSS v4](https://tailwindcss.com/) | Next.js と相性が良い。ビルド統合済み |
| **グラフ** | [Recharts](https://recharts.org/) | React ネイティブ。アナリティクス画面に使用 |
| **ASGI サーバー** | [Uvicorn](https://www.uvicorn.org/) | FastAPI 標準 |
| **DB** | SQLite ＋ aiosqlite | 変更なし |
| **Discord Bot** | discord.py | 変更なし（役割を縮小） |
| **Scheduler** | APScheduler | 変更なし（FastAPI 起動時に同一プロセスで起動） |
| **LLM** | Claude CLI（サブプロセス） | 変更なし |
| **Twitter/X** | Playwright | 変更なし |
| **パッケージ管理（Python）** | uv | 変更なし |
| **パッケージ管理（JS）** | npm | Next.js 標準 |
| **公開** | Cloudflare Tunnel | void2610.dev ドメイン経由で外部公開。詳細はセクション 9 |

> **判断基準**：Next.js の採用経験が多く、最初からフル機能の SPA として構築する。  
> バックエンドは既存 Python 資産を活かすため FastAPI を維持し、Next.js からは API Route / Server Actions 経由で叩く。

---

## 5. Web UI 機能一覧

### ゲーム管理

| 画面 | 機能 |
|---|---|
| ゲーム一覧 | テーブル表示・ソート・ステータスフィルタ |
| ゲーム詳細 | 全フィールド表示・インライン編集 |
| ゲーム登録 | フォーム（制限なし：エレベーターピッチ・ハッシュタグ等も入力可） |
| ゲーム削除 | 確認ダイアログ付き |

### 進捗ログ

| 画面 | 機能 |
|---|---|
| 進捗一覧 | ゲーム別フィルタ・日付ソート・ツイート済みフィルタ |
| 進捗登録 | テキストエリアで詳細に記述可能 |
| 進捗編集 | 興奮度・tweetable フラグのトグル |

### アピールポイント

| 画面 | 機能 |
|---|---|
| アピール一覧 | カテゴリ・優先度フィルタ・使用日時表示 |
| アピール登録/編集 | 全フィールド・テキストエリア |

### 素材管理

| 画面 | 機能 |
|---|---|
| 素材一覧 | サムネイル付き・ゲーム別フィルタ |
| 素材アップロード | drag & drop 対応フォーム |
| 素材削除 | 確認ダイアログ付き |

### 下書き管理（最重要）

| 画面 | 機能 |
|---|---|
| 下書き一覧 | ステータス別タブ（pending / approved / posted / rejected）|
| 下書き生成 | ゲーム・モード・言語・トーンを選択して LLM 呼び出し |
| 下書き承認/却下 | ボタン 1 クリック（グループ一括対応） |
| 下書き編集 | テキスト内容の修正 |
| キュー確認 | 投稿順・投稿予定時刻の表示 |

### アナリティクス

| 画面 | 機能 |
|---|---|
| ダッシュボード | ゲーム別・期間別のインプレッション推移グラフ |
| ツイート一覧 | エンゲージメント率ソート・フィルタ |
| レポート生成 | LLM による月次分析レポートの表示・保存 |
| メトリクス手動取得 | ボタン 1 クリックで最新メトリクスを取得 |

### スケジュール管理

| 画面 | 機能 |
|---|---|
| スロット一覧 | 有効/無効の切り替え |
| スロット追加/削除 | 時刻入力フォーム |
| キュー管理 | キャンセル・順序確認 |

---

## 6. Discord の新しい役割

Discord はユーザーが見ている可能性が高いチャンネルへの「プッシュ通知」に特化する。

| トリガー | 内容 | 形式 |
|---|---|---|
| Bot 起動時 | `🌐 Web UI 起動 → {WEB_BASE_URL}` | 通知 |
| 毎日朝 9 時 | pending 下書き件数・承認済みキュー件数・本日のスロット一覧 | Embed + Web URL |
| 投稿完了時 | ツイート URL・ゲーム名・内容プレビュー | Embed |
| 投稿失敗時 | エラー内容・対象下書き ID・Web UI リンク | Embed（警告） |
| メトリクス更新時（6h）| 更新件数のサマリー | 通知（省略可） |
| 進捗未入力（週次）| 「今週の進捗が登録されていません」 | Embed + Web URL |

### 残すスラッシュコマンド（最小限）

| コマンド | 説明 |
|---|---|
| `/link` | Web UI の URL を Ephemeral で返す |
| `/status` | キュー・スロット・ゲーム数のサマリー（数値のみ・詳細は Web へ） |

---

## 7. ディレクトリ構成案

```
game-promo-hub/
├── bot.py                    # Discord Bot エントリポイント（通知専用に縮小）
├── main.py                   # FastAPI + Discord Bot 統合起動エントリポイント（新規）
├── config.py                 # 環境変数管理（WEB_BASE_URL など追加）
├── schema.sql                # DB スキーマ（変更なし）
│
├── cogs/                     # Discord Cog（通知用に整理）
│   ├── notify_cog.py         # 新規：通知・リマインド専用 Cog
│   └── (既存 cog は段階的に削除・または /link, /status のみ残す)
│
├── api/                      # FastAPI バックエンド（新規）
│   ├── app.py                # FastAPI アプリ定義
│   └── routes/               # ルーター（リソース単位）
│       ├── games.py
│       ├── progress.py
│       ├── appeals.py
│       ├── assets.py
│       ├── drafts.py
│       ├── analytics.py
│       └── schedule.py
│
├── frontend/                 # Next.js フロントエンド（新規）
│   ├── app/                  # App Router
│   │   ├── layout.tsx
│   │   ├── page.tsx          # ダッシュボード
│   │   ├── games/
│   │   ├── drafts/
│   │   ├── analytics/
│   │   └── schedule/
│   ├── components/           # 共通 React コンポーネント
│   ├── lib/                  # API クライアント・ユーティリティ
│   ├── public/
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   └── package.json
│
├── services/                 # 変更なし
│   ├── db.py
│   ├── llm.py
│   ├── twitter.py
│   ├── scheduler.py
│   └── discord_utils.py
│
├── prompts/                  # 変更なし
├── assets/                   # ゲーム素材（変更なし）
├── tests/                    # 既存テスト（変更なし） + API ルートの追加
│
├── pyproject.toml            # fastapi, uvicorn, python-multipart 追加
├── .env.example              # WEB_BASE_URL, API_PORT, NEXTAUTH_SECRET 等追加
└── ARCHITECTURE.md           # 本ドキュメント
```

---

## 8. 環境変数追加分

```env
# Web UI / API
WEB_BASE_URL=https://void2610.dev          # Discord 通知内のリンクに使用
API_PORT=8080                              # FastAPI ポート
NEXT_PUBLIC_API_URL=http://localhost:8080  # Next.js から FastAPI へのアクセス先（開発時）

# 認証（NextAuth.js）
NEXTAUTH_URL=https://void2610.dev          # 本番 URL
NEXTAUTH_SECRET=your_random_secret        # openssl rand -base64 32 で生成
WEB_PASSWORD=your_login_password          # Credentials Provider のパスワード

# Discord 通知チャンネル（通知送信先）
DISCORD_NOTIFY_CHANNEL_ID=123456789012345678
```

---

## 9. Cloudflare Tunnel（void2610.dev）

### 概要

自宅マシン（またはローカルサーバー）上で動作する Next.js を、Cloudflare Tunnel を使って `void2610.dev` 経由で HTTPS 公開する。  
Cloudflare 側でのポート開放・SSL 証明書管理が不要になり、ファイアウォールの内側から安全に公開できる。

### セットアップ手順

```bash
# 1. cloudflared のインストール（Linux/macOS）
# https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

# macOS
brew install cloudflared

# Linux（Debian/Ubuntu 系）
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb

# 2. Cloudflare アカウントへログイン
cloudflared tunnel login

# 3. トンネルを作成
cloudflared tunnel create game-promo-hub

# 4. 設定ファイルを作成（~/.cloudflared/config.yml）
# 以下の内容を記述する（tunnel ID は手順 3 で発行されたものを使用）
```

```yaml
# ~/.cloudflared/config.yml
tunnel: <YOUR_TUNNEL_ID>
credentials-file: /home/<user>/.cloudflared/<YOUR_TUNNEL_ID>.json

ingress:
  # Next.js フロントエンド（メインドメイン）
  - hostname: void2610.dev
    service: http://localhost:3000
  # FastAPI バックエンド API（サブドメイン or パス分岐）
  - hostname: api.void2610.dev
    service: http://localhost:8080
  # フォールバック（必須）
  - service: http_status:404
```

```bash
# 5. DNS レコードを Cloudflare へ登録
cloudflared tunnel route dns game-promo-hub void2610.dev
cloudflared tunnel route dns game-promo-hub api.void2610.dev

# 6. トンネルをサービスとして登録・起動（Linux systemd）
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared

# 手動起動（開発・確認時）
cloudflared tunnel run game-promo-hub
```

### ルーティング方針

| ホスト | 転送先 | 内容 |
|---|---|---|
| `void2610.dev` | `localhost:3000` | Next.js（フロントエンド） |
| `api.void2610.dev` | `localhost:8080` | FastAPI（バックエンド API） |

> **Next.js から FastAPI への通信**：  
> ブラウザからは `https://api.void2610.dev` へ直接リクエスト、または Next.js の Route Handlers（`/api/proxy/...`）経由で FastAPI へ転送する方式のどちらも可。  
> 開発時は `NEXT_PUBLIC_API_URL=http://localhost:8080` を使うとローカルで動作確認できる。

### セキュリティ考慮

- Cloudflare Zero Trust（Access）を設定すると、ドメイン全体に認証レイヤーを追加できる（推奨）
- NextAuth.js の Credentials Provider でもアプリレベルの認証は行う
- FastAPI 側はローカルネットワーク内からのみ直接アクセス可能（Cloudflare Tunnel 経由を想定）

---

## 10. 起動方法（想定）

```bash
# バックエンド（FastAPI + Discord Bot）を起動
uv run python main.py

# フロントエンド（Next.js）を起動
cd frontend && npm run dev

# Cloudflare Tunnel を起動（別ターミナル、または systemd で自動起動）
cloudflared tunnel run game-promo-hub

# または個別起動（開発時）
uv run uvicorn api.app:app --reload --port 8080
cd frontend && npm run dev   # ポート 3000
```

`main.py` では `asyncio` の同一イベントループ上で FastAPI（Uvicorn）と Discord Bot を並走させる。  
Next.js は独立したプロセスで起動し、Cloudflare Tunnel が `void2610.dev → localhost:3000` へルーティングする。

---

## 11. 移行方針（段階的）

### Phase 1：バックエンド API の構築（優先）
- FastAPI セットアップ・CORS 設定（Next.js からのアクセスを許可）
- DB の読み取り系 API（ゲーム一覧・進捗一覧・下書き一覧）
- ゲーム・進捗・アピールポイントの登録 API

### Phase 2：Next.js フロントエンドの構築
- `create-next-app` でプロジェクト初期化（App Router・TypeScript・TailwindCSS）
- NextAuth.js で Credentials Provider 認証
- ゲーム・進捗・下書き一覧ページ

### Phase 3：下書き管理の Web 化
- 下書き生成 UI（LLM 呼び出し）・承認・却下
- キュー管理画面

### Phase 4：Discord 通知専用化
- 通知 Cog の実装（投稿完了・リマインド）
- 既存データ入力 Cog の削除

### Phase 5：アナリティクス・スケジュール管理
- Recharts でダッシュボード・グラフ
- スロット管理 UI

### Phase 6：Cloudflare Tunnel 本番設定
- `void2610.dev` DNS・Tunnel 設定
- Zero Trust Access の設定（任意）
- 環境変数を本番用に切り替え（`NEXTAUTH_URL=https://void2610.dev` 等）

---

## 12. 未決事項・検討事項

| 項目 | 決定／選択肢 | 備考 |
|---|---|---|
| **フロントエンド** | ✅ **Next.js 15（App Router）** | Next.js 経験が豊富なため最初から採用 |
| **公開方法** | ✅ **Cloudflare Tunnel（void2610.dev）** | ファイアウォール内から HTTPS 公開 |
| **認証方式** | NextAuth.js Credentials Provider | 個人ツール。パスワード 1 つで管理 |
| **API と Next.js の通信** | サブドメイン（api.void2610.dev）vs Route Handlers Proxy | どちらでも可。シンプルさではサブドメイン分離を推奨 |
| **DB のマイグレーション** | SQLite のまま | 個人・単一サーバー運用のため問題なし |
| **グラフ描画** | Recharts | React ネイティブで Next.js と相性が良い |
| **ファイルアップロード** | multipart → ローカル保存 | 現行と同様 |
| **LLM** | Claude CLI（現行） | API 化すればサーバー上でも動作可能 |
| **テスト** | 既存 unittest + FastAPI TestClient | Next.js 側は Playwright E2E も検討 |
