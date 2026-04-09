# game-promo-hub

Discord Bot を使ってインディーゲームのプロモーション下書きを管理し、承認済みの投稿をスケジューリングして X/Twitter に自動投稿します。パフォーマンス分析には SQLite と Claude CLI を活用します。

## セットアップ

Discord Developer Portal の操作手順・Twitter/X API キーの取得方法を含む詳細なセットアップ手順は **[SETUP.md](SETUP.md)** を参照してください。

1. `.env.example` を `.env` にコピーし、必要な認証情報を入力します。  
   各項目の取得方法は [SETUP.md](SETUP.md) で詳しく説明しています。
2. `uv` を使って仮想環境を作成し、依存ライブラリをインストールします。
   ```bash
   uv sync
   ```
3. Claude CLI が正常に動作することを確認します。
   ```bash
   echo "Translate テスト to English. Respond with English only." | claude --print
   ```
4. Bot を起動します。
   ```bash
   uv run python bot.py
   ```

## よく使うコマンド

```bash
# 依存ライブラリのインストール・更新
uv sync

# Bot の起動
uv run python bot.py

# テストの実行
uv run python -m unittest discover -s tests -v

# 構文チェック（コンパイル確認）
uv run python -m compileall bot.py cogs services tests
```

## Discord スラッシュコマンド一覧

| コマンド | 説明 |
|---|---|
| `/game_add` | ゲームを登録する |
| `/game_list` | 登録済みゲームの一覧を表示する |
| `/progress_add` | 進捗ログを追加する |
| `/appeal_add` | アピールポイントを追加する |
| `/asset_add` | 添付ファイルを素材として登録する |
| `/promo_draft` | ツイート下書きを AI で生成する |
| `/draft_list` | 既存の下書き（承認待ち・承認済み）を一覧表示する |
| `/analytics_fetch` | X/Twitter のメトリクスを取得する |
| `/analytics_report` | 宣伝分析レポートを生成する |
| `/analytics_top` | エンゲージメント上位投稿を表示する |
| `/schedule_slot_add` | 定期投稿スロットを追加する |
| `/schedule_slot_list` | 定期投稿スロット一覧を表示する |
| `/schedule_slot_remove` | 定期投稿スロットを削除する |
| `/schedule_queue_list` | 承認済みキューを表示する |
| `/schedule_queue_cancel` | 承認済みキューを取り消す |

## システム概要

```
Discord
  └─ スラッシュコマンド
       ├─ /game_add・/progress_add・/appeal_add・/asset_add
       │    ゲーム情報・進捗・アピール・素材を SQLite に登録
       ├─ /promo_draft・/draft_list
       │    Claude CLI でツイート下書きを生成 → 承認ボタンで承認キューへ追加
       │    /draft_list で承認待ち・承認済み下書きを確認
       ├─ /analytics_fetch・/analytics_report・/analytics_top
       │    Twitter/X API でメトリクスを取得 → Claude CLI で分析レポートを生成
       └─ /schedule_slot_add・/schedule_queue_*
            JST の時刻スロットを管理し、スケジューラが自動投稿を実行
```

## 環境変数

| 変数名 | 必須 | 説明 |
|---|---|---|
| `DISCORD_TOKEN` | ✅ | Discord Bot トークン |
| `DISCORD_GUILD_ID` | ✅ | コマンドを同期するギルド ID |
| `ALLOWED_USER_IDS` | ✅ | Bot の操作を許可するユーザー ID（カンマ区切り） |
| `TWITTER_BEARER_TOKEN` | ✅ | Twitter/X Bearer トークン |
| `TWITTER_API_KEY` | ✅ | Twitter/X API キー |
| `TWITTER_API_SECRET` | ✅ | Twitter/X API シークレット |
| `TWITTER_ACCESS_TOKEN` | ✅ | Twitter/X アクセストークン |
| `TWITTER_ACCESS_SECRET` | ✅ | Twitter/X アクセスシークレット |
| `PROMO_DB_PATH` | | SQLite DB のパス（デフォルト: `promo.db`） |
| `ASSETS_DIR` | | 素材ファイルの保存先（デフォルト: `assets/`） |
| `PROMPTS_DIR` | | プロンプトファイルの格納先（デフォルト: `prompts/`） |
| `CLAUDE_TIMEOUT` | | Claude CLI のタイムアウト秒数（デフォルト: `120`） |
| `SCHEDULER_POLL_SECONDS` | | スケジューラのポーリング間隔秒数（デフォルト: `30`） |
