# 初期セットアップガイド

このガイドでは、**Discord Bot** と **X/Twitter（Playwright ブラウザ操作）** の初期設定を詳細に説明します。  
`.env` に設定する全項目の取得方法をステップごとに解説します。

> **Twitter/X の連携方式について**  
> このボットは Twitter/X 公式 API（有料）を使用しません。  
> Playwright でブラウザを自動操作し、**X/Twitter アカウントのユーザー名とパスワード**でログインして投稿・メトリクス取得を行います。  
> そのため、API キーや Bearer トークンは不要です。

---

## 目次

1. [Discord Developer Portal の操作](#1-discord-developer-portal-の操作)
   - [1-1. アプリケーションの作成](#1-1-アプリケーションの作成)
   - [1-2. Bot ユーザーの作成とトークン取得](#1-2-bot-ユーザーの作成とトークン取得)
   - [1-3. Privileged Gateway Intents の設定](#1-3-privileged-gateway-intents-の設定)
   - [1-4. Bot をサーバーへ招待する](#1-4-bot-をサーバーへ招待する)
   - [1-5. ギルド ID の取得](#1-5-ギルド-id-の取得)
   - [1-6. ユーザー ID の取得](#1-6-ユーザー-id-の取得)
2. [X/Twitter アカウントの設定](#2-xtwitter-アカウントの設定)
   - [2-1. 専用アカウントの準備](#2-1-専用アカウントの準備)
   - [2-2. Playwright ブラウザドライバのインストール](#2-2-playwright-ブラウザドライバのインストール)
3. [.env ファイルの作成](#3-env-ファイルの作成)
4. [依存ライブラリのインストールと Bot の起動](#4-依存ライブラリのインストールと-bot-の起動)
5. [トラブルシューティング](#5-トラブルシューティング)

---

## 1. Discord Developer Portal の操作

### 1-1. アプリケーションの作成

1. ブラウザで [Discord Developer Portal](https://discord.com/developers/applications) を開き、Discord アカウントでログインします。
2. 右上の **「New Application」** ボタンをクリックします。
3. アプリケーション名（例: `game-promo-bot`）を入力して **「Create」** をクリックします。
4. 作成後、**General Information** ページが表示されます。ここではアプリの名前・説明・アイコンを設定できます（必須ではありません）。

### 1-2. Bot ユーザーの作成とトークン取得

1. 左サイドバーの **「Bot」** をクリックします。
2. **「Add Bot」** ボタンをクリックし、確認ダイアログで **「Yes, do it!」** を選択します。
3. Bot が作成されると **「TOKEN」** セクションが表示されます。
4. **「Reset Token」** ボタンをクリックして新しいトークンを生成し、表示されたトークンを **必ずコピーして安全な場所に保管** してください。  
   > ⚠️ トークンはこの画面を閉じると二度と表示されません。紛失した場合は再生成が必要です。  
   > ⚠️ トークンを GitHub などの公開リポジトリにコミットしないでください。

   このトークンが `.env` の `DISCORD_TOKEN` に設定する値です。

   ```
   DISCORD_TOKEN=ここにコピーしたトークンを貼り付ける
   ```

### 1-3. Privileged Gateway Intents の設定

Bot が正常に動作するには、以下の **Privileged Gateway Intents** を有効にする必要があります。

1. **「Bot」** ページのまま、**「Privileged Gateway Intents」** セクションまでスクロールします。
2. 以下の項目を **オン** にします：
   - **MESSAGE CONTENT INTENT** — ✅ 有効にする
3. **「Save Changes」** ボタンをクリックして保存します。

### 1-4. Bot をサーバーへ招待する

1. 左サイドバーの **「OAuth2」** → **「URL Generator」** をクリックします。
2. **「SCOPES」** セクションで以下にチェックを入れます：
   - ✅ `bot`
   - ✅ `applications.commands`（スラッシュコマンドに必須）
3. **「BOT PERMISSIONS」** セクションで以下にチェックを入れます：
   - ✅ `Send Messages`
   - ✅ `Send Messages in Threads`
   - ✅ `Embed Links`
   - ✅ `Attach Files`
   - ✅ `Read Message History`
   - ✅ `Use Slash Commands`
4. ページ下部に生成された **「GENERATED URL」** をコピーします。
5. コピーした URL をブラウザのアドレスバーに貼り付けてアクセスします。
6. Bot を招待したいサーバーを選択して **「認証」** をクリックします。
7. CAPTCHA を完了すると Bot がサーバーに参加します。

### 1-5. ギルド ID の取得

「ギルド ID」とは Discord サーバーの固有 ID です。スラッシュコマンドを特定のサーバーに限定同期するために使います。

1. Discord アプリを開きます。
2. **設定 → 詳細設定** を開き、**「開発者モード」** を **オン** にします。
3. 設定を閉じ、Bot を招待したサーバーのアイコン（左サイドバー）を **右クリック** します。
4. メニューから **「サーバー ID をコピー」** を選択します。

   コピーした値が `.env` の `DISCORD_GUILD_ID` に設定する値です。

   ```
   DISCORD_GUILD_ID=コピーしたサーバーIDを貼り付ける（例: 123456789012345678）
   ```

### 1-6. ユーザー ID の取得

Bot のコマンドを実行できるユーザーを制限するために、許可するユーザーの ID を設定します。

1. 開発者モードが有効な状態で、Discord アプリ内の自分のアイコンまたは名前を **右クリック** します。
2. **「ユーザー ID をコピー」** を選択します。
3. 複数のユーザーを許可する場合は、同様の手順で各ユーザーの ID を取得します。

   取得した ID を `.env` の `ALLOWED_USER_IDS` にカンマ区切りで設定します。

   ```
   ALLOWED_USER_IDS=自分のユーザーID,他のユーザーID
   # 例: ALLOWED_USER_IDS=123456789012345678,987654321098765432
   ```

---

## 2. X/Twitter アカウントの設定

このボットは X/Twitter の公式 API を使用しません。**Playwright がブラウザを自動操作して**ユーザー名・パスワードでログインし、ツイートの投稿とメトリクスのスクレイピングを行います。

### 2-1. 専用アカウントの準備

投稿用の X/Twitter アカウントを用意します（既存アカウントでも新規アカウントでも構いません）。

| 項目 | 説明 |
|---|---|
| **ユーザー名** | `@` なしのユーザー名、またはアカウントに登録したメールアドレス |
| **パスワード** | そのアカウントのログインパスワード |

> 💡 **推奨**: ボット専用のアカウントを作成すると、個人アカウントへの影響を避けられます。
>
> ⚠️ **2 段階認証（2FA）について**: SMS 認証などの 2FA が有効になっている場合、自動ログインに失敗することがあります。2FA を無効にするか、認証アプリ（TOTP）方式にしてください。

取得した情報を `.env` に設定します。

```
TWITTER_USERNAME=your_x_username_or_email
TWITTER_PASSWORD=your_x_password
```

#### セッションキャッシュについて

初回ログイン成功後、ブラウザのセッション（クッキー等）が `twitter_session.json`（デフォルト）に自動保存されます。  
次回起動時はこのキャッシュを利用するため、毎回ログイン操作は不要です。

セッションファイルのパスを変更する場合は `.env` に追記します（省略時はデフォルト値が使われます）。

```
# 省略可（デフォルト: twitter_session.json）
TWITTER_SESSION_PATH=twitter_session.json
```

> ⚠️ `twitter_session.json` にはログイン情報が含まれます。`.gitignore` に追加して誤ってコミットしないよう注意してください（既にデフォルトで除外されています）。

### 2-2. Playwright ブラウザドライバのインストール

Playwright を使ったブラウザ操作には、Chromium ドライバが必要です。依存ライブラリのインストール後に以下を実行します。

```bash
uv run playwright install chromium
```

> 必要なシステムライブラリが不足している場合は、以下のコマンドで依存関係をインストールできます（Linux 環境）。
>
> ```bash
> uv run playwright install-deps chromium
> ```

---

## 3. .env ファイルの作成

プロジェクトルートで `.env.example` をコピーして `.env` を作成し、取得した値を入力します。

```bash
cp .env.example .env
```

`.env` の記入例（実際の値に置き換えてください）：

```dotenv
# ── Discord ──────────────────────────────────────────────
# Discord Developer Portal > アプリ > Bot > TOKEN
DISCORD_TOKEN=MTxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Discord サーバーを右クリック > サーバー ID をコピー（開発者モード必須）
DISCORD_GUILD_ID=123456789012345678

# 自分のアイコンを右クリック > ユーザー ID をコピー（複数はカンマ区切り）
ALLOWED_USER_IDS=123456789012345678,987654321098765432

# ── Twitter/X （Playwright スクレイピング）────────────────
# 投稿に使用する X/Twitter アカウントの認証情報
TWITTER_USERNAME=your_x_username_or_email
TWITTER_PASSWORD=your_x_password
# セッションキャッシュファイルのパス（省略時は twitter_session.json）
# TWITTER_SESSION_PATH=twitter_session.json

# ── オプション（デフォルト値あり）────────────────────────
PROMO_DB_PATH=promo.db
ASSETS_DIR=assets
PROMPTS_DIR=prompts
CLAUDE_TIMEOUT=120
SCHEDULER_POLL_SECONDS=30
ANALYTICS_FETCH_INTERVAL_HOURS=6
```

---

## 4. 依存ライブラリのインストールと Bot の起動

```bash
# 依存ライブラリをインストール
uv sync

# Playwright の Chromium ドライバをインストール（初回のみ）
uv run playwright install chromium

# Claude CLI の動作確認（AI 機能を使用する場合）
echo "Translate テスト to English. Respond with English only." | claude --print

# Bot を起動
uv run python bot.py
```

起動に成功すると、次のようなメッセージがターミナルに表示されます。

```
Bot ready: game-promo-bot#1234
```

Discord サーバーでスラッシュコマンド（例: `/game_list`）が使えることを確認してください。  
X/Twitter への接続は初回コマンド実行時（`/analytics_fetch` や `/schedule_slot_add` で定期投稿が動くタイミング）に行われます。

---

## 5. トラブルシューティング

| 症状 | 原因と対処 |
|---|---|
| `Missing required environment variable: DISCORD_TOKEN` | `.env` の `DISCORD_TOKEN` が未設定。[1-2](#1-2-bot-ユーザーの作成とトークン取得) を参照してください。 |
| `Missing required environment variable: DISCORD_GUILD_ID` | `DISCORD_GUILD_ID` が未設定。[1-5](#1-5-ギルド-id-の取得) を参照してください。 |
| スラッシュコマンドが Discord に表示されない | Bot をサーバーに招待する際に `applications.commands` スコープが不足している可能性があります。[1-4](#1-4-bot-をサーバーへ招待する) を再確認して Bot を再招待してください。 |
| `discord.errors.Forbidden: 403 Forbidden` | Bot のサーバー権限が不足しています。サーバー設定 → 連携サービス → Bot の権限を確認してください。 |
| `Missing required environment variable: TWITTER_USERNAME` | `.env` に `TWITTER_USERNAME` が設定されていません。[2-1](#2-1-専用アカウントの準備) を参照してください。 |
| ログインに失敗する（`セッションが切れています。再ログインします。` のループ） | パスワードが正しいか確認してください。2FA（2 段階認証）が有効な場合は 2FA を無効化するか TOTP 方式に変更してください。 |
| ツイート投稿時に `CreateTweet レスポンスからツイート ID を取得できませんでした` | X/Twitter の UI が更新された可能性があります。`playwright install chromium` でブラウザを最新版に更新してください。 |
| `playwright: command not found` | `uv run playwright install chromium` が未実行です。[2-2](#2-2-playwright-ブラウザドライバのインストール) を参照してください。 |
| Bot がサーバーのオフラインのまま | `DISCORD_TOKEN` が無効または Bot が停止しています。ターミナルのエラーログを確認してください。 |
