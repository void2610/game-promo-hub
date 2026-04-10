# Game Promo Hub — アーキテクチャ設計書

> 作成日: 2026-04-10  
> ステータス: ドラフト（レビュー待ち）

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
  │ HTTP / WebSocket
  ▼
┌─────────────────────────────┐
│       Web UI + API          │  ← 操作の主体
│  FastAPI + Jinja2 / HTMX   │
│  （または Next.js フロント） │
└──────────┬──────────────────┘
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
  ├── Web URL 共有
  ├── 定期リマインド（APScheduler から呼び出し）
  └── 投稿完了・分析結果の通知
```

### コンポーネント間の関係

```
[APScheduler]
    │
    ├─ 毎分 tick   → Twitter 定期投稿（スロット一致時）
    ├─ 6時間ごと   → メトリクス自動取得
    └─ 毎日朝 9時  → Discord へ「本日の状況」リマインド通知

[FastAPI]
    ├─ /api/*      → REST API エンドポイント（CRUD）
    ├─ /*          → Jinja2 HTML ページ（SSR）
    └─ 起動時      → DB 初期化・Scheduler 起動・Discord Bot 起動

[Discord Bot]
    ├─ on_ready    → 起動通知（Web UI の URL も掲載）
    └─ スラッシュコマンド（最小限）
         /link    → Web UI の URL を Ephemeral で返す
         /status  → 現在のキュー状況サマリー（Web へのリンク付き）
```

---

## 4. 技術スタック

### 推奨構成（Option A：Python 一本化・シンプル優先）

| レイヤー | 技術 | 理由 |
|---|---|---|
| **Web フレームワーク** | [FastAPI](https://fastapi.tiangolo.com/) | 既存 Python 資産をそのまま流用できる。async 対応。型安全 |
| **テンプレート** | [Jinja2](https://jinja.palletsprojects.com/) | FastAPI 組み込み。ビルドステップ不要 |
| **インタラクティブ UI** | [HTMX](https://htmx.org/) | JS フレームワーク不要でリッチな操作感。部分更新・フォーム送信 |
| **CSS** | [TailwindCSS](https://tailwindcss.com/) CDN | ビルド不要の CDN 版で十分 |
| **認証** | Bearer トークン（環境変数）| 個人運用ツールのため最小限。`WEB_SECRET_TOKEN` を設定 |
| **ASGI サーバー** | [Uvicorn](https://www.uvicorn.org/) | FastAPI 標準 |
| **DB** | SQLite ＋ aiosqlite | 変更なし |
| **Discord Bot** | discord.py | 変更なし（役割を縮小） |
| **Scheduler** | APScheduler | 変更なし（FastAPI 起動時に同一プロセスで起動） |
| **LLM** | Claude CLI（サブプロセス） | 変更なし |
| **Twitter/X** | Playwright | 変更なし |
| **パッケージ管理** | uv | 変更なし |

> **判断基準**：既存コードの大部分（services/\*）を再利用でき、移行コストが最小。  
> フロントエンドに本格的な SPA が必要になったら後から Next.js へ切り出す。

---

### 代替構成（Option B：フロントエンドを分離したい場合）

| レイヤー | 技術 |
|---|---|
| **Backend API** | FastAPI（同上） |
| **Frontend** | Next.js 15（App Router、TypeScript） |
| **認証** | NextAuth.js + JWT |
| **CSS** | TailwindCSS |

Option B はフロントエンド開発経験があり、SPA の操作性（クライアントサイドルーティング・楽観的更新など）が必要な場合に選択する。  
移行コストが高いため、MVP では **Option A を推奨**。

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
├── config.py                 # 環境変数管理（WEB_SECRET_TOKEN など追加）
├── schema.sql                # DB スキーマ（変更なし）
│
├── cogs/                     # Discord Cog（通知用に整理）
│   ├── notify_cog.py         # 新規：通知・リマインド専用 Cog
│   └── (既存 cog は段階的に削除・または /link, /status のみ残す)
│
├── web/                      # Web UI（新規）
│   ├── app.py                # FastAPI アプリ定義
│   ├── routes/               # ルーター（ページ単位）
│   │   ├── games.py
│   │   ├── progress.py
│   │   ├── appeals.py
│   │   ├── assets.py
│   │   ├── drafts.py
│   │   ├── analytics.py
│   │   └── schedule.py
│   ├── templates/            # Jinja2 テンプレート
│   │   ├── base.html
│   │   ├── games/
│   │   ├── drafts/
│   │   └── ...
│   └── static/               # CSS・JS（HTMX CDN 参照のみ等）
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
├── tests/                    # 既存テスト（変更なし） + Web ルートの追加
│
├── pyproject.toml            # fastapi, uvicorn, jinja2, python-multipart 追加
├── .env.example              # WEB_SECRET_TOKEN, WEB_BASE_URL, WEB_PORT 追加
└── ARCHITECTURE.md           # 本ドキュメント
```

---

## 8. 環境変数追加分

```env
# Web UI
WEB_BASE_URL=http://localhost:8080          # Discord 通知内のリンクに使用
WEB_PORT=8080
WEB_SECRET_TOKEN=your_random_secret_token  # Bearer トークン認証

# Discord 通知チャンネル（通知送信先）
DISCORD_NOTIFY_CHANNEL_ID=123456789012345678
```

---

## 9. 起動方法（想定）

```bash
# 単一コマンドで FastAPI + Discord Bot を同時起動
uv run python main.py

# または個別起動（開発時）
uv run uvicorn web.app:app --reload --port 8080
uv run python bot.py
```

`main.py` では `asyncio` の同一イベントループ上で FastAPI（Uvicorn）と Discord Bot を並走させる。

---

## 10. 移行方針（段階的）

### Phase 1：Web UI の基盤構築（優先）
- FastAPI セットアップ・認証ミドルウェア
- DB の読み取り専用ページ（ゲーム一覧・進捗一覧・下書き一覧）
- ゲーム・進捗・アピールポイントの登録フォーム

### Phase 2：下書き管理の Web 化
- 下書き生成（LLM 呼び出し）・承認・却下
- キュー管理画面

### Phase 3：Discord 通知専用化
- 通知 Cog の実装（投稿完了・リマインド）
- 既存データ入力 Cog の削除

### Phase 4：アナリティクス・スケジュール管理
- ダッシュボード・グラフ
- スロット管理 UI

---

## 11. 未決事項・検討事項

| 項目 | 選択肢 | 備考 |
|---|---|---|
| 認証方式 | Bearer トークン / HTTP Basic / パスワードページ | 個人ツールなので最小限で良い。VPN 下での利用を前提にするなら認証なしでも可 |
| DB のマイグレーション | aiosqlite のまま / PostgreSQL へ移行 | SQLite で問題なければそのまま。複数人利用・将来のホスティングを考慮するなら Postgres |
| デプロイ先 | ローカルマシン / VPS / Raspberry Pi / Docker | 自宅サーバーなら SQLite のまま。クラウドなら Postgres 化を検討 |
| フロントエンド | Jinja2+HTMX / Next.js | 操作性 vs 開発コスト。MVP は Jinja2+HTMX を推奨 |
| グラフ描画 | Chart.js（CDN）/ Recharts | Jinja2 構成なら Chart.js が最もシンプル |
| ファイルアップロード | multipart → ローカル保存 | 現行と同様。クラウド保存が必要なら S3 等を検討 |
| LLM | Claude CLI（現行）/ Anthropic API | API 化すればサーバー上でも動作可能（CLI は Claude が入った PC が必要） |
| テスト | 既存 unittest / pytest + FastAPI TestClient | Web ルートのテストは TestClient で追加 |
