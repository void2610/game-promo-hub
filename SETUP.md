# 初期セットアップガイド

このガイドでは、**Discord Bot** と **Twitter/X API** の初期設定を詳細に説明します。  
`.env` に設定する全項目の取得方法をステップごとに解説します。

---

## 目次

1. [Discord Developer Portal の操作](#1-discord-developer-portal-の操作)
   - [1-1. アプリケーションの作成](#1-1-アプリケーションの作成)
   - [1-2. Bot ユーザーの作成とトークン取得](#1-2-bot-ユーザーの作成とトークン取得)
   - [1-3. Privileged Gateway Intents の設定](#1-3-privileged-gateway-intents-の設定)
   - [1-4. Bot をサーバーへ招待する](#1-4-bot-をサーバーへ招待する)
   - [1-5. ギルド ID の取得](#1-5-ギルド-id-の取得)
   - [1-6. ユーザー ID の取得](#1-6-ユーザー-id-の取得)
2. [Twitter/X Developer Portal の操作](#2-twitterx-developer-portal-の操作)
   - [2-1. 開発者アカウントの申請](#2-1-開発者アカウントの申請)
   - [2-2. プロジェクト・アプリの作成](#2-2-プロジェクトアプリの作成)
   - [2-3. API キーと API シークレットの取得](#2-3-api-キーと-api-シークレットの取得)
   - [2-4. アクセストークンとアクセスシークレットの取得](#2-4-アクセストークンとアクセスシークレットの取得)
   - [2-5. Bearer トークンの取得](#2-5-bearer-トークンの取得)
   - [2-6. アプリの権限設定（Read and Write）](#2-6-アプリの権限設定read-and-write)
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

> 💡 **SERVER MEMBERS INTENT** と **PRESENCE INTENT** はこの Bot では使用しませんが、将来の機能追加時に必要になる場合があります。

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

## 2. Twitter/X Developer Portal の操作

### 2-1. 開発者アカウントの申請

Twitter API を使用するには、開発者アカウントの申請と承認が必要です。

1. [Twitter Developer Portal](https://developer.twitter.com/) にアクセスし、ツイートを投稿したいアカウントでログインします。
2. **「Sign up for Free Account」** をクリックします。
3. API の利用目的を英語で入力します（例: "Building a Discord bot to schedule and post promotional tweets for indie games. The bot reads game information and auto-posts approved tweet drafts."）。
4. 利用規約に同意して申請を完了します。
5. **Free プラン** で申請すると、基本的な読み書き権限（月 1,500 ツイートまで）が即時付与されます。

> 💡 **プランについて**  
> - **Free**: 月 1,500 ツイート投稿、読み取り制限あり。個人利用・小規模には十分です。  
> - **Basic**: 月 $100、月 3,000 ツイート投稿、読み取り 10,000 件/月。  
> - メトリクス取得（インプレッション数など）には **Basic プラン以上** が必要です。Free プランではメトリクス取得が制限される場合があります。

### 2-2. プロジェクト・アプリの作成

1. Developer Portal の **「Dashboard」** を開きます。
2. **「+ Add App」** または **「Create Project」** をクリックします。
3. プロジェクト名（例: `game-promo-hub`）を入力して **「Next」** を選択します。
4. ユースケースを選択します（例: `Making a bot`）。
5. プロジェクトの説明を入力して **「Next」** を選択します。
6. アプリ名（例: `game-promo-bot`）を入力して **「Complete」** をクリックします。

### 2-3. API キーと API シークレットの取得

プロジェクト・アプリ作成完了後、または後から取得する場合：

1. Developer Portal の左サイドバーから作成したアプリを選択します。
2. **「Keys and tokens」** タブをクリックします。
3. **「Consumer Keys」** セクションの **「Regenerate」** をクリックします。
4. **API Key** と **API Key Secret** が表示されます。  
   > ⚠️ この画面を閉じると Secret は二度と表示されません。必ずコピーして保管してください。

   ```
   TWITTER_API_KEY=表示された API Key を貼り付ける
   TWITTER_API_SECRET=表示された API Key Secret を貼り付ける
   ```

### 2-4. アクセストークンとアクセスシークレットの取得

アクセストークンは、ボットが実際にツイートを投稿する際に使用するトークンです。ログインしているアカウントに紐づきます。

1. **「Keys and tokens」** タブの **「Authentication Tokens」** セクションを開きます。
2. **「Access Token and Secret」** の **「Generate」** または **「Regenerate」** をクリックします。
3. **Access Token** と **Access Token Secret** が表示されます。  
   > ⚠️ この画面を閉じると Secret は二度と表示されません。必ずコピーして保管してください。  
   > ✅ 「Created with Read and Write permissions」と表示されていることを確認してください（[2-6](#2-6-アプリの権限設定read-and-write) を先に設定することを推奨）。

   ```
   TWITTER_ACCESS_TOKEN=表示された Access Token を貼り付ける
   TWITTER_ACCESS_SECRET=表示された Access Token Secret を貼り付ける
   ```

### 2-5. Bearer トークンの取得

Bearer トークンはアプリレベルの認証に使用します（ツイートの読み取りやメトリクス取得など）。

1. **「Keys and tokens」** タブの **「Bearer Token」** セクションを開きます。
2. **「Regenerate」** をクリックして Bearer トークンを生成します。
3. 表示された Bearer Token をコピーします。

   ```
   TWITTER_BEARER_TOKEN=表示された Bearer Token を貼り付ける
   ```

### 2-6. アプリの権限設定（Read and Write）

ツイートを投稿するには **Read and Write** 権限が必要です。**アクセストークンを生成する前に** この設定を行ってください。

1. Developer Portal の左サイドバーから作成したアプリを選択します。
2. **「Settings」** タブをクリックします。
3. **「User authentication settings」** セクションの **「Set up」** または **「Edit」** をクリックします。
4. 以下を設定します：
   - **OAuth 1.0a** を有効にする
   - **App permissions**: **「Read and write」** を選択
   - **Callback URI / Redirect URL**: `https://example.com`（実際には使用しませんが入力必須）
   - **Website URL**: `https://example.com`（同上）
5. **「Save」** をクリックして保存します。
6. **⚠️ 重要**: 権限を変更したあとは、**アクセストークンを再生成** してください（古いトークンは Read only のまま残ります）。  
   → [2-4](#2-4-アクセストークンとアクセスシークレットの取得) の手順でアクセストークンを再生成します。

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

# ── Twitter/X ─────────────────────────────────────────────
# Developer Portal > アプリ > Keys and tokens > Bearer Token
TWITTER_BEARER_TOKEN=AAAAAAAAAAAAAAAAAAAAAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Developer Portal > アプリ > Keys and tokens > Consumer Keys
TWITTER_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxx
TWITTER_API_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Developer Portal > アプリ > Keys and tokens > Authentication Tokens
TWITTER_ACCESS_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWITTER_ACCESS_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

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

# Claude CLI の動作確認（AI 機能を使用する場合）
echo "Translate テスト to English. Respond with English only." | claude --print

# Bot を起動
uv run python bot.py
```

起動に成功すると、次のようなメッセージがターミナルに表示されます：

```
Bot ready: game-promo-bot#1234
```

Discord サーバーでスラッシュコマンド（例: `/game_list`）が使えることを確認してください。

---

## 5. トラブルシューティング

| 症状 | 原因と対処 |
|---|---|
| `Missing required environment variable: DISCORD_TOKEN` | `.env` の `DISCORD_TOKEN` が未設定。[1-2](#1-2-bot-ユーザーの作成とトークン取得) を参照してトークンを設定してください。 |
| `Missing required environment variable: DISCORD_GUILD_ID` | `DISCORD_GUILD_ID` が未設定。[1-5](#1-5-ギルド-id-の取得) を参照してください。 |
| スラッシュコマンドが Discord に表示されない | Bot をサーバーに招待する際に `applications.commands` スコープが不足している可能性があります。[1-4](#1-4-bot-をサーバーへ招待する) を再確認して Bot を再招待してください。 |
| `discord.errors.Forbidden: 403 Forbidden` | Bot のサーバー権限が不足しています。サーバー設定 → 連携サービス → Bot の権限を確認してください。 |
| ツイート投稿時に `403 Forbidden` エラー | Twitter アクセストークンが Read only になっています。[2-6](#2-6-アプリの権限設定read-and-write) で権限を変更後、アクセストークンを再生成してください。 |
| `401 Unauthorized` (Twitter) | API Key / Secret またはアクセストークンが正しくありません。`.env` の値を再確認してください。 |
| メトリクスが取得できない | Twitter Free プランではメトリクス API が制限されます。Basic プラン以上へのアップグレードを検討してください。 |
| Bot がサーバーのオフラインのまま | `DISCORD_TOKEN` が無効または Bot が停止しています。ターミナルのエラーログを確認してください。 |
