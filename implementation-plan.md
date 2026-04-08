# Game Promo Discord Bot 実装計画

## Summary

- `game-promo-bot-spec.md` を基準に、空リポジトリへ Discord bot を新規構築する。
- 実装対象は Discord slash commands、SQLite 永続化、Claude CLI 連携、X/Twitter 投稿、分析、定期投稿 scheduler、最小限の自動テスト、`main` へのコミット・push まで含む。
- 運用前提は「Discord が唯一の操作 UI」「承認済み下書きをプールし、定期スロットで自動投稿」「複数ゲームは均等ローテーション」。

## Confirmed Decisions

- `lang=both` は 2 連投スレッドで投稿する。
- `/asset_add` は attachment option 方式にする。
- scheduler は予約投稿まで実装する。
- 予約投稿は「既存 draft を承認済みプールに入れ、定刻に自動選出して投稿」方式にする。
- 投稿頻度は既定で 1 日 1 回。
- 投稿対象は `approved` の下書きのみ。
- 定刻の投稿候補選定はゲーム均等ローテーション。
- 投稿スロットは DB 管理にし、Discord コマンドで追加・一覧・削除できるようにする。
- push は `main` へ直接行う前提で進める。

## Key Changes

- 基盤
  - `bot.py` は `setup_hook` で DB 初期化、scheduler 起動、cogs 読み込み、guild sync を実行する。
  - `config.py` は `.env` 読み込み、必須設定検証、パス定義、JST タイムゾーン定義を持つ。
  - `.env.example`、`.gitignore`、`README.md`、`requirements.txt` を整備する。
- DB / schema
  - `schema.sql` に仕様書の全テーブルを実装する。
  - 追加テーブル `schedule_slots`
    - `id`, `slot_time` (`HH:MM`), `enabled`, `created_at`
  - `tweet_drafts` を拡張
    - `draft_group_id`。`lang=both` の JA/EN を束ねる。
    - `source_progress_ids`, `source_appeal_ids`。承認後に元データ消費状態を更新する。
    - `status` は `pending | approved | rejected | posted` を扱う。
    - `approved_at` を追加し、ローテーション選出の補助に使う。
  - `tweets` は thread 投稿に備えて `reply_to_tweet_id` を追加する。
- Discord commands
  - `game_cog.py`
    - `/game_add` modal 登録
    - `/game_list`
  - `progress_cog.py`
    - `/progress_add <game_id>` modal 登録
  - `appeal_cog.py`
    - `/appeal_add <game_id>` modal 登録
  - `asset_cog.py`
    - `/asset_add <game_id> <attachment> [description] [recommended_for]`
  - `promo_cog.py`
    - `/promo_draft <game_id> [mode] [lang] [tone]`
    - 承認 UI で `pending -> approved`
    - 承認時は即投稿しない。承認済みプールに入る。
    - 再生成は旧 draft/group を `rejected` にする。
    - `lang=both` は 2 draft を 1 group として扱う。
  - `analytics_cog.py`
    - `/analytics_fetch`
    - `/analytics_report`
    - `/analytics_top`
  - `schedule_cog.py`
    - `/schedule_slot_add <time_jst>`
    - `/schedule_slot_list`
    - `/schedule_slot_remove <slot_id>`
    - `/schedule_queue_list [limit]`
    - `/schedule_queue_cancel <draft_id_or_group_id>`
- Scheduler / posting
  - `services/scheduler.py` は APScheduler で毎分監視ジョブを持つ。
  - 現在 JST 時刻が有効 slot と一致したら、未投稿の `approved` drafts から 1 件選ぶ。
  - 選定は「最後に投稿したゲーム」と異なるゲームを優先する均等ローテーション。
  - 候補がない場合は何もしない。
  - `lang=both` group は JA を親、EN を返信として連投する。
  - 投稿成功後
    - `tweet_drafts.status = posted`
    - `tweets` へ保存
    - 元 progress を `tweeted=1`
    - 元 appeal を `last_used_at=now`
  - 投稿失敗時は draft を `approved` のまま残し、ログ出力して次回スロットで再試行可能にする。
- LLM / Twitter
  - `services/llm.py`
    - `claude --print --output-format text` 実行
    - JSON 抽出、タイムアウト、非 0 終了、空応答を例外化
  - `services/twitter.py`
    - v1.1 media upload + v2 create tweet
    - `reply_to_tweet_id` 対応
    - metrics fetch を service 化
  - `prompts/`
    - `system_promo.txt`
    - `system_analytics.txt`
    - `brand_voice.txt`
- DB helpers
  - 追加 helper
    - `get_asset_by_id`
    - `get_draft_by_group`
    - `approve_draft_or_group`
    - `list_approved_queue`
    - `mark_draft_posted`
    - `save_analytics_summary`
    - `list_schedule_slots`
    - `add_schedule_slot`
    - `remove_schedule_slot`
    - `pick_next_approved_draft_group`
- Testing / verification
  - `pytest` は追加せず、標準ライブラリ `unittest` で最小自動テストを書く。
  - DB helper と scheduler selection logic を中心に自動テストを書く。
  - Claude/Twitter/Discord はモックで service/unit レベルまで確認する。
  - `python -m compileall .` で静的起動確認を行う。

## Test Plan

- DB
  - schema 初期化で全テーブルが作成される。
  - `lang=both` draft group が 2 行で保存される。
  - approval 後に queue 対象へ入る。
  - posted 後に progress/appeal の消費状態が更新される。
- Scheduler
  - slot 一致時のみ実行される。
  - 複数ゲーム間でローテーション選出される。
  - 候補ゼロ時は安全に no-op。
  - 投稿失敗時に queue が壊れない。
- Promo / LLM
  - JSON 抽出成功・失敗ケース。
  - 無効 asset id を返されても処理継続。
- Analytics
  - metrics 更新が DB に反映される。
  - report 結果が `analytics_summaries` に保存される。
  - `analytics_top` が engagement rate 順になる。
- Verification
  - `python -m unittest`
  - `python -m compileall .`
  - 必要なら `python bot.py` 起動確認
  - 実装完了後、段階的にコミットして `main` へ push

## Assumptions

- `lang=both` の承認は 1 回で group 全体を承認する。
- 手動即時投稿コマンドは追加しない。今回の投稿導線は「生成 → 承認 → 定期スロット投稿」に統一する。
- schedule slot は JST の `HH:MM` 文字列で管理する。
- `schedule_queue_cancel` は対象 draft/group を `rejected` に変更し、投稿対象から外す。
- 画像寸法は必須ではないため、取得不能なら `width` / `height` は `NULL` を許容する。
- `main` への push に必要な git remote と認証は既に利用可能である。

