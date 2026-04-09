from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import aiosqlite

from config import DB_PATH, JST, SCHEMA_PATH


def _json_dumps(values: list[int] | list[str] | None) -> str:
    """リストを JSON 文字列に変換する。None または空の場合は "[]" を返す。"""
    return json.dumps(values or [], ensure_ascii=False)


def _json_loads(raw: str | None) -> list[Any]:
    """JSON 文字列をリストに変換する。None または空文字の場合は空リストを返す。"""
    if not raw:
        return []
    return json.loads(raw)


def _now_iso() -> str:
    """現在の JST 時刻を ISO 8601 形式の文字列で返す。"""
    return datetime.now(JST).isoformat()


@dataclass(slots=True)
class PromoContext:
    """LLM へ渡すプロモ生成コンテキスト。テキストと参照した進捗・アピール ID を保持する。"""

    text: str
    progress_ids: list[int]
    appeal_ids: list[int]


@asynccontextmanager
async def _connect():
    """aiosqlite の非同期接続コンテキストマネージャ。外部キー制約を有効にする。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        yield db


async def init_db() -> None:
    """schema.sql を実行してテーブルとインデックスを作成する（初回起動時）。"""
    async with _connect() as db:
        await db.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        await db.commit()


async def add_game(data: dict[str, Any]) -> None:
    """ゲーム情報を games テーブルに登録する。hashtags と target_audience は JSON 文字列に変換する。"""
    payload = data.copy()
    payload["hashtags"] = _json_dumps(payload.get("hashtags"))
    payload["target_audience"] = _json_dumps(payload.get("target_audience"))
    async with _connect() as db:
        await db.execute(
            """
            INSERT INTO games (
                id, name_ja, name_en, genre, platform, status,
                steam_url, elevator_ja, elevator_en, hashtags,
                target_audience, circle
            )
            VALUES (
                :id, :name_ja, :name_en, :genre, :platform, :status,
                :steam_url, :elevator_ja, :elevator_en, :hashtags,
                :target_audience, :circle
            )
            """,
            payload,
        )
        await db.commit()


def _hydrate_game(row: aiosqlite.Row | None) -> dict[str, Any] | None:
    """DB の Row を辞書に変換し、JSON カラムをリストにデシリアライズする。"""
    if row is None:
        return None
    result = dict(row)
    result["hashtags"] = _json_loads(result.get("hashtags"))
    result["target_audience"] = _json_loads(result.get("target_audience"))
    return result


async def get_game(game_id: str) -> dict[str, Any] | None:
    """指定した ID のゲーム情報を取得する。存在しない場合は None を返す。"""
    async with _connect() as db:
        async with db.execute("SELECT * FROM games WHERE id = ?", (game_id,)) as cursor:
            return _hydrate_game(await cursor.fetchone())


async def list_games() -> list[dict[str, Any]]:
    """登録されているすべてのゲームを作成日時の降順で返す。"""
    async with _connect() as db:
        async with db.execute("SELECT * FROM games ORDER BY created_at DESC") as cursor:
            return [_hydrate_game(row) for row in await cursor.fetchall()]


async def get_all_game_ids() -> list[str]:
    """登録されているすべてのゲーム ID のリストを返す。自動アナリティクス用。"""
    async with _connect() as db:
        async with db.execute("SELECT id FROM games ORDER BY id ASC") as cursor:
            return [row[0] for row in await cursor.fetchall()]


async def add_progress(data: dict[str, Any]) -> int:
    """進捗ログを progress_logs テーブルに追加し、発行された ID を返す。"""
    async with _connect() as db:
        cursor = await db.execute(
            """
            INSERT INTO progress_logs (
                game_id, log_date, milestone, content, appeal_note, excitement, tweetable
            )
            VALUES (
                :game_id, :log_date, :milestone, :content, :appeal_note, :excitement, :tweetable
            )
            """,
            data,
        )
        await db.commit()
        return int(cursor.lastrowid)


async def get_recent_progress(game_id: str, limit: int = 3) -> list[dict[str, Any]]:
    """ツイート候補かつ未ツイートの進捗ログを最新順に最大 limit 件返す。"""
    async with _connect() as db:
        async with db.execute(
            """
            SELECT * FROM progress_logs
            WHERE game_id = ? AND tweetable = 1 AND tweeted = 0
            ORDER BY log_date DESC, created_at DESC
            LIMIT ?
            """,
            (game_id, limit),
        ) as cursor:
            return [dict(row) for row in await cursor.fetchall()]


async def mark_progress_tweeted(progress_ids: list[int]) -> None:
    """指定した進捗ログを「ツイート済み」に更新する。"""
    if not progress_ids:
        return
    placeholders = ",".join("?" for _ in progress_ids)
    async with _connect() as db:
        await db.execute(
            f"UPDATE progress_logs SET tweeted = 1 WHERE id IN ({placeholders})",
            tuple(progress_ids),
        )
        await db.commit()


async def add_appeal(data: dict[str, Any]) -> int:
    """アピールポイントを appeal_points テーブルに追加し、発行された ID を返す。"""
    async with _connect() as db:
        cursor = await db.execute(
            """
            INSERT INTO appeal_points (game_id, category, priority, title, content, promo_tips)
            VALUES (:game_id, :category, :priority, :title, :content, :promo_tips)
            """,
            data,
        )
        await db.commit()
        return int(cursor.lastrowid)


async def get_appeals(
    game_id: str,
    category: str | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """アピールポイントを優先度・使用日時の順で取得する。category を指定するとカテゴリ絞り込みを行う。"""
    query = """
        SELECT * FROM appeal_points
        WHERE game_id = ?
    """
    params: list[Any] = [game_id]
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY priority DESC, last_used_at IS NOT NULL, last_used_at ASC, created_at ASC LIMIT ?"
    params.append(limit)
    async with _connect() as db:
        async with db.execute(query, params) as cursor:
            return [dict(row) for row in await cursor.fetchall()]


async def mark_appeal_used(appeal_ids: list[int]) -> None:
    """指定したアピールポイントの最終使用日時を現在時刻に更新する。"""
    if not appeal_ids:
        return
    placeholders = ",".join("?" for _ in appeal_ids)
    async with _connect() as db:
        await db.execute(
            f"UPDATE appeal_points SET last_used_at = ? WHERE id IN ({placeholders})",
            (_now_iso(), *appeal_ids),
        )
        await db.commit()


async def add_asset(data: dict[str, Any]) -> int:
    """素材ファイルのメタデータを assets テーブルに登録し、発行された ID を返す。"""
    async with _connect() as db:
        cursor = await db.execute(
            """
            INSERT INTO assets (
                game_id, filename, asset_type, description,
                recommended_for, local_path, width, height
            )
            VALUES (
                :game_id, :filename, :asset_type, :description,
                :recommended_for, :local_path, :width, :height
            )
            """,
            data,
        )
        await db.commit()
        return int(cursor.lastrowid)


async def get_assets(game_id: str, recommended_for: str | None = None) -> list[dict[str, Any]]:
    """ゲームに登録された素材を返す。recommended_for を指定すると用途で絞り込む（"any" も含む）。"""
    query = "SELECT * FROM assets WHERE game_id = ?"
    params: list[Any] = [game_id]
    if recommended_for:
        query += " AND (recommended_for = ? OR recommended_for = 'any')"
        params.append(recommended_for)
    query += " ORDER BY created_at DESC"
    async with _connect() as db:
        async with db.execute(query, params) as cursor:
            return [dict(row) for row in await cursor.fetchall()]


async def get_asset_by_id(asset_id: int) -> dict[str, Any] | None:
    """ID で素材を取得する。存在しない場合は None を返す。"""
    async with _connect() as db:
        async with db.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def add_tweet(data: dict[str, Any]) -> int:
    """投稿済みツイートを tweets テーブルに記録し、発行された ID を返す。"""
    async with _connect() as db:
        cursor = await db.execute(
            """
            INSERT INTO tweets (
                tweet_id, game_id, lang, content, asset_id, tone, strategy_note,
                posted_at, tweet_url, approved_by, reply_to_tweet_id
            )
            VALUES (
                :tweet_id, :game_id, :lang, :content, :asset_id, :tone, :strategy_note,
                :posted_at, :tweet_url, :approved_by, :reply_to_tweet_id
            )
            """,
            data,
        )
        await db.commit()
        return int(cursor.lastrowid)


async def get_recent_tweets(game_id: str, days: int = 14) -> list[dict[str, Any]]:
    """指定した日数以内に投稿したツイートを降順で返す（重複投稿防止に使用）。"""
    since = (datetime.now(JST) - timedelta(days=days)).isoformat()
    async with _connect() as db:
        async with db.execute(
            """
            SELECT * FROM tweets
            WHERE game_id = ? AND posted_at > ?
            ORDER BY posted_at DESC
            """,
            (game_id, since),
        ) as cursor:
            return [dict(row) for row in await cursor.fetchall()]


async def get_recent_tweets_for_analytics(game_id: str, days: int = 90) -> list[dict[str, Any]]:
    """アナリティクス用に指定した日数以内のツイートを返す（デフォルト 90 日）。"""
    since = (datetime.now(JST) - timedelta(days=days)).isoformat()
    async with _connect() as db:
        async with db.execute(
            """
            SELECT * FROM tweets
            WHERE game_id = ? AND posted_at > ?
            ORDER BY posted_at DESC
            """,
            (game_id, since),
        ) as cursor:
            return [dict(row) for row in await cursor.fetchall()]


async def update_tweet_analytics(
    tweet_id: str,
    impressions: int,
    likes: int,
    retweets: int,
    replies: int,
) -> None:
    """ツイートのパブリックメトリクスを更新し、取得日時を記録する。
    また tweet_metrics_history にスナップショットを追加して時系列データを蓄積する。
    """
    now = _now_iso()
    async with _connect() as db:
        await db.execute(
            """
            UPDATE tweets
            SET impressions = ?, likes = ?, retweets = ?, replies = ?, analytics_fetched_at = ?
            WHERE tweet_id = ?
            """,
            (impressions, likes, retweets, replies, now, tweet_id),
        )
        await db.execute(
            """
            INSERT INTO tweet_metrics_history (tweet_id, impressions, likes, retweets, replies, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (tweet_id, impressions, likes, retweets, replies, now),
        )
        await db.commit()


async def batch_update_tweet_analytics(metrics: list[dict[str, Any]]) -> None:
    """複数ツイートのメトリクスを1トランザクションで一括更新する。

    tweets テーブルを最新値で上書きし、tweet_metrics_history にスナップショットを追記する。
    1件ずつ呼び出す update_tweet_analytics と異なり、接続・コミットを1回で完結させる。
    """
    if not metrics:
        return
    now = _now_iso()
    tweet_params = [
        (item["impressions"], item["likes"], item["retweets"], item["replies"], now, item["tweet_id"])
        for item in metrics
    ]
    history_params = [
        (item["tweet_id"], item["impressions"], item["likes"], item["retweets"], item["replies"], now)
        for item in metrics
    ]
    async with _connect() as db:
        await db.executemany(
            """
            UPDATE tweets
            SET impressions = ?, likes = ?, retweets = ?, replies = ?, analytics_fetched_at = ?
            WHERE tweet_id = ?
            """,
            tweet_params,
        )
        await db.executemany(
            """
            INSERT INTO tweet_metrics_history (tweet_id, impressions, likes, retweets, replies, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            history_params,
        )
        await db.commit()


async def insert_tweet_metrics_snapshot(
    tweet_id: str,
    impressions: int,
    likes: int,
    retweets: int,
    replies: int,
) -> None:
    """tweet_metrics_history にスナップショットを単独で追加する。
    tweets テーブルは更新しない（履歴の直接挿入のみ）。
    """
    async with _connect() as db:
        await db.execute(
            """
            INSERT INTO tweet_metrics_history (tweet_id, impressions, likes, retweets, replies, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (tweet_id, impressions, likes, retweets, replies, _now_iso()),
        )
        await db.commit()


async def get_tweet_metrics_history(tweet_id: str) -> list[dict[str, Any]]:
    """指定したツイート ID のメトリクス履歴を取得日時の昇順で返す。"""
    async with _connect() as db:
        async with db.execute(
            """
            SELECT tweet_id, impressions, likes, retweets, replies, fetched_at
            FROM tweet_metrics_history
            WHERE tweet_id = ?
            ORDER BY fetched_at ASC
            """,
            (tweet_id,),
        ) as cursor:
            return [dict(row) for row in await cursor.fetchall()]


async def get_top_tweets(game_id: str, limit: int = 5) -> list[dict[str, Any]]:
    """エンゲージメント率（いいね＋RT / インプレッション）の高いツイートを返す。"""
    async with _connect() as db:
        async with db.execute(
            """
            SELECT *,
                CAST(COALESCE(likes, 0) + COALESCE(retweets, 0) AS FLOAT) /
                NULLIF(COALESCE(impressions, 0), 0) AS eng_rate
            FROM tweets
            WHERE game_id = ? AND impressions IS NOT NULL
            ORDER BY eng_rate DESC, impressions DESC
            LIMIT ?
            """,
            (game_id, limit),
        ) as cursor:
            return [dict(row) for row in await cursor.fetchall()]


async def add_draft(data: dict[str, Any]) -> int:
    """ツイート下書きを tweet_drafts テーブルに追加し、発行された ID を返す。
    source_progress_ids / source_appeal_ids は JSON 文字列に変換して保存する。
    """
    payload = data.copy()
    payload["source_progress_ids"] = _json_dumps(payload.get("source_progress_ids"))
    payload["source_appeal_ids"] = _json_dumps(payload.get("source_appeal_ids"))
    async with _connect() as db:
        cursor = await db.execute(
            """
            INSERT INTO tweet_drafts (
                draft_group_id, game_id, mode, lang, content, asset_id, tone, strategy_note,
                asset_reason, source_progress_ids, source_appeal_ids, status,
                discord_msg_id, approved_by, approved_at
            )
            VALUES (
                :draft_group_id, :game_id, :mode, :lang, :content, :asset_id, :tone, :strategy_note,
                :asset_reason, :source_progress_ids, :source_appeal_ids, :status,
                :discord_msg_id, :approved_by, :approved_at
            )
            """,
            {
                "status": "pending",
                "discord_msg_id": None,
                "approved_by": None,
                "approved_at": None,
                **payload,
            },
        )
        await db.commit()
        return int(cursor.lastrowid)


def generate_draft_group_id() -> str:
    """複数言語の下書きをまとめるグループ ID を UUID4 ハッシュで生成する。"""
    return uuid.uuid4().hex


def _hydrate_draft(row: aiosqlite.Row | None) -> dict[str, Any] | None:
    """DB の Row を辞書に変換し、JSON カラム（ソース ID リスト）をデシリアライズする。"""
    if row is None:
        return None
    result = dict(row)
    result["source_progress_ids"] = _json_loads(result.get("source_progress_ids"))
    result["source_appeal_ids"] = _json_loads(result.get("source_appeal_ids"))
    return result


async def get_draft(draft_id: int) -> dict[str, Any] | None:
    """ID で下書きを取得する。存在しない場合は None を返す。"""
    async with _connect() as db:
        async with db.execute("SELECT * FROM tweet_drafts WHERE id = ?", (draft_id,)) as cursor:
            return _hydrate_draft(await cursor.fetchone())


async def get_drafts_by_group(draft_group_id: str) -> list[dict[str, Any]]:
    """グループ ID に属する下書きを ja → en の順で返す。"""
    async with _connect() as db:
        async with db.execute(
            """
            SELECT * FROM tweet_drafts
            WHERE draft_group_id = ?
            ORDER BY CASE lang WHEN 'ja' THEN 0 WHEN 'en' THEN 1 ELSE 2 END, id ASC
            """,
            (draft_group_id,),
        ) as cursor:
            return [_hydrate_draft(row) for row in await cursor.fetchall()]


async def update_draft_message(draft_id: int, discord_msg_id: str) -> None:
    """単一の下書きに Discord メッセージ ID を紐付ける。"""
    async with _connect() as db:
        await db.execute(
            "UPDATE tweet_drafts SET discord_msg_id = ? WHERE id = ?",
            (discord_msg_id, draft_id),
        )
        await db.commit()


async def update_draft_group_message(draft_group_id: str, discord_msg_id: str) -> None:
    """グループに属するすべての下書きに Discord メッセージ ID を紐付ける。"""
    async with _connect() as db:
        await db.execute(
            "UPDATE tweet_drafts SET discord_msg_id = ? WHERE draft_group_id = ?",
            (discord_msg_id, draft_group_id),
        )
        await db.commit()


async def reject_draft_group(draft_group_id: str | None, draft_id: int | None = None) -> None:
    """グループまたは単一の下書きを "rejected" ステータスに更新する。"""
    async with _connect() as db:
        if draft_group_id:
            await db.execute(
                "UPDATE tweet_drafts SET status = 'rejected' WHERE draft_group_id = ?",
                (draft_group_id,),
            )
        elif draft_id is not None:
            await db.execute(
                "UPDATE tweet_drafts SET status = 'rejected' WHERE id = ?",
                (draft_id,),
            )
        await db.commit()


async def approve_draft_group(
    draft_group_id: str | None,
    approved_by: str,
    draft_id: int | None = None,
) -> None:
    """グループまたは単一の下書きを "approved" ステータスに更新し、承認者と承認日時を記録する。"""
    approved_at = _now_iso()
    async with _connect() as db:
        if draft_group_id:
            await db.execute(
                """
                UPDATE tweet_drafts
                SET status = 'approved', approved_at = ?, approved_by = ?
                WHERE draft_group_id = ? AND status = 'pending'
                """,
                (approved_at, approved_by, draft_group_id),
            )
        elif draft_id is not None:
            await db.execute(
                """
                UPDATE tweet_drafts
                SET status = 'approved', approved_at = ?, approved_by = ?
                WHERE id = ? AND status = 'pending'
                """,
                (approved_at, approved_by, draft_id),
            )
        await db.commit()


async def list_approved_queue(limit: int = 10) -> list[dict[str, Any]]:
    """承認済みの下書きグループを承認日時順に返す。draft_ids と langs はリストに変換される。"""
    async with _connect() as db:
        async with db.execute(
            """
            SELECT
                COALESCE(draft_group_id, 'single:' || id) AS queue_id,
                game_id,
                MIN(approved_at) AS approved_at,
                COUNT(*) AS draft_count,
                GROUP_CONCAT(id) AS draft_ids,
                GROUP_CONCAT(lang) AS langs
            FROM tweet_drafts
            WHERE status = 'approved'
            GROUP BY queue_id, game_id
            ORDER BY approved_at ASC
            LIMIT ?
            """,
            (limit,),
        ) as cursor:
            rows = []
            for row in await cursor.fetchall():
                item = dict(row)
                item["draft_ids"] = [int(value) for value in str(item["draft_ids"]).split(",")]
                item["langs"] = str(item["langs"]).split(",")
                rows.append(item)
            return rows


async def list_pending_drafts(game_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """承認待ち（pending）の下書きを作成日時の降順で返す。

    Args:
        game_id: 絞り込むゲーム ID。None の場合はすべてのゲームを対象にする。
        limit: 返す最大件数。

    Returns:
        source_progress_ids / source_appeal_ids を Python リストに変換した下書き辞書のリスト。
    """
    if game_id:
        query = (
            "SELECT * FROM tweet_drafts WHERE status = 'pending' AND game_id = ?"
            " ORDER BY created_at DESC LIMIT ?"
        )
        params: tuple = (game_id, limit)
    else:
        query = "SELECT * FROM tweet_drafts WHERE status = 'pending' ORDER BY created_at DESC LIMIT ?"
        params = (limit,)
    async with _connect() as db:
        async with db.execute(query, params) as cursor:
            return [_hydrate_draft(row) for row in await cursor.fetchall()]


async def mark_drafts_posted(draft_ids: list[int]) -> None:
    """指定した下書き ID を "posted" ステータスに更新する。"""
    if not draft_ids:
        return
    placeholders = ",".join("?" for _ in draft_ids)
    async with _connect() as db:
        await db.execute(
            f"UPDATE tweet_drafts SET status = 'posted' WHERE id IN ({placeholders})",
            tuple(draft_ids),
        )
        await db.commit()


async def get_queue_item(queue_id: str) -> list[dict[str, Any]]:
    """queue_id から下書きリストを取得する。"single:ID" 形式の場合は単一の下書きを返す。"""
    if queue_id.startswith("single:"):
        draft = await get_draft(int(queue_id.split(":", 1)[1]))
        return [draft] if draft else []
    return await get_drafts_by_group(queue_id)


async def consume_draft_sources(drafts: list[dict[str, Any]]) -> None:
    """投稿済み下書きが参照していた進捗ログとアピールポイントを消費済みにする。"""
    progress_ids: list[int] = []
    appeal_ids: list[int] = []
    for draft in drafts:
        progress_ids.extend(int(value) for value in draft.get("source_progress_ids", []))
        appeal_ids.extend(int(value) for value in draft.get("source_appeal_ids", []))
    await mark_progress_tweeted(sorted(set(progress_ids)))
    await mark_appeal_used(sorted(set(appeal_ids)))


async def save_analytics_summary(game_id: str, period: str, result: dict[str, Any]) -> None:
    """アナリティクスレポートを analytics_summaries テーブルに保存する。"""
    async with _connect() as db:
        await db.execute(
            """
            INSERT INTO analytics_summaries (
                game_id, period, best_time_slot, best_tone, best_asset_type, strategy_note, raw_analysis
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                game_id,
                period,
                result.get("best_time_slot"),
                result.get("best_tone"),
                result.get("best_asset_type"),
                result.get("next_strategy"),
                json.dumps(result, ensure_ascii=False),
            ),
        )
        await db.commit()


async def add_schedule_slot(slot_time: str) -> int:
    """定期投稿スロット（HH:MM 形式）を schedule_slots テーブルに追加し、発行された ID を返す。"""
    async with _connect() as db:
        cursor = await db.execute(
            "INSERT INTO schedule_slots (slot_time, enabled) VALUES (?, 1)",
            (slot_time,),
        )
        await db.commit()
        return int(cursor.lastrowid)


async def list_schedule_slots() -> list[dict[str, Any]]:
    """登録されているすべての投稿スロットを時刻の昇順で返す。"""
    async with _connect() as db:
        async with db.execute(
            "SELECT * FROM schedule_slots ORDER BY slot_time ASC"
        ) as cursor:
            return [dict(row) for row in await cursor.fetchall()]


async def remove_schedule_slot(slot_id: int) -> None:
    """指定した ID の投稿スロットを削除する。"""
    async with _connect() as db:
        await db.execute("DELETE FROM schedule_slots WHERE id = ?", (slot_id,))
        await db.commit()


async def get_slot_by_time(slot_time: str) -> dict[str, Any] | None:
    """現在時刻（HH:MM）に一致する有効なスロットを返す。存在しない場合は None を返す。"""
    async with _connect() as db:
        async with db.execute(
            "SELECT * FROM schedule_slots WHERE slot_time = ? AND enabled = 1",
            (slot_time,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def build_promo_context(game_id: str, mode: str) -> PromoContext:
    """LLM へ渡すプロモ生成コンテキストを構築する。

    ゲーム基本情報・未ツイート進捗・アピールポイント・直近ツイート・
    使用可能素材を一つのテキストにまとめた PromoContext を返す。
    """
    game = await get_game(game_id)
    if not game:
        raise ValueError(f"Game not found: {game_id}")

    progress = await get_recent_progress(game_id, limit=3)
    category = None if mode in {"random", "progress", "milestone"} else mode
    appeals = await get_appeals(game_id, category=category, limit=3)
    tweets = await get_recent_tweets(game_id, days=14)
    assets = await get_assets(game_id)

    lines = [
        "### ゲーム基本情報",
        f"- ID: {game['id']}",
        f"- 名前: {game['name_ja']} ({game.get('name_en') or ''})",
        f"- ジャンル: {game.get('genre') or ''}",
        f"- プラットフォーム: {game.get('platform') or ''}",
        f"- ステータス: {game.get('status') or ''}",
        f"- Steam URL: {game.get('steam_url') or '未定'}",
        f"- ハッシュタグ: {' '.join(game.get('hashtags', []))}",
        f"- ターゲット: {', '.join(game.get('target_audience', []))}",
        f"- エレベーターピッチ（日）: {game.get('elevator_ja') or ''}",
        f"- エレベーターピッチ（英）: {game.get('elevator_en') or ''}",
        "",
        "### 最近の進捗（未ツイート優先）",
    ]
    progress_ids: list[int] = []
    for item in progress:
        progress_ids.append(int(item["id"]))
        hint = f" / ヒント: {item['appeal_note']}" if item.get("appeal_note") else ""
        lines.append(
            f"- [{item['log_date']}] {item.get('milestone') or ''} {item['content']} "
            f"(興奮度 {item['excitement']}/3){hint}"
        )

    lines.append("")
    lines.append("### アピールポイント")
    appeal_ids: list[int] = []
    for item in appeals:
        appeal_ids.append(int(item["id"]))
        tip = f" / 宣伝ヒント: {item['promo_tips']}" if item.get("promo_tips") else ""
        lines.append(f"- [{item.get('category') or 'general'}] {item['title']}: {item['content']}{tip}")

    lines.append("")
    lines.append("### 直近14日の投稿")
    for tweet in tweets:
        lines.append(f"- {str(tweet['posted_at'])[:10]} {tweet['content'][:90]}")

    lines.append("")
    lines.append("### 使用可能素材")
    for asset in assets:
        lines.append(
            f"- ID:{asset['id']} [{asset.get('asset_type') or 'unknown'}] "
            f"{asset['filename']}: {asset.get('description') or ''} "
            f"(推奨用途: {asset.get('recommended_for') or 'any'})"
        )

    return PromoContext(text="\n".join(lines), progress_ids=progress_ids, appeal_ids=appeal_ids)


async def pick_next_approved_draft_group() -> list[dict[str, Any]]:
    """次に投稿すべき承認済み下書きグループを選択して返す。

    投稿数の少ないゲームを優先し、同数の場合は最終投稿日時・承認日時の古い順に選ぶ。
    """
    async with _connect() as db:
        async with db.execute(
            """
            WITH approved_groups AS (
                SELECT
                    COALESCE(draft_group_id, 'single:' || id) AS queue_id,
                    game_id,
                    MIN(approved_at) AS approved_at
                FROM tweet_drafts
                WHERE status = 'approved'
                GROUP BY queue_id, game_id
            ),
            game_stats AS (
                SELECT
                    game_id,
                    COUNT(*) AS post_count,
                    MAX(posted_at) AS last_posted_at
                FROM tweets
                GROUP BY game_id
            )
            SELECT
                approved_groups.queue_id,
                approved_groups.game_id,
                approved_groups.approved_at,
                COALESCE(game_stats.post_count, 0) AS post_count,
                game_stats.last_posted_at
            FROM approved_groups
            LEFT JOIN game_stats ON game_stats.game_id = approved_groups.game_id
            ORDER BY
                post_count ASC,
                last_posted_at IS NOT NULL,
                last_posted_at ASC,
                approved_groups.approved_at ASC
            LIMIT 1
            """
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return []
            queue_id = row["queue_id"]
    if str(queue_id).startswith("single:"):
        draft_id = int(str(queue_id).split(":", 1)[1])
        draft = await get_draft(draft_id)
        return [draft] if draft else []
    return await get_drafts_by_group(str(queue_id))
