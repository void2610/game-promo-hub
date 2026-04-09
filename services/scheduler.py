from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import ANALYTICS_FETCH_INTERVAL_HOURS, JST, SCHEDULER_POLL_SECONDS
from services import db, twitter

LOGGER = logging.getLogger(__name__)
# グローバルなスケジューラインスタンス（二重起動を防ぐ）
_scheduler: AsyncIOScheduler | None = None
# 直前に処理したスロットのキー（同一スロットへの二重投稿を防ぐ）
_last_slot_key: str | None = None


def setup_scheduler(bot) -> AsyncIOScheduler:
    """APScheduler を初期化して定期ポーリングジョブを登録し、スケジューラを起動する。

    すでに起動済みの場合は既存のインスタンスを返す。
    """
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    scheduler = AsyncIOScheduler(timezone=JST)
    scheduler.add_job(
        _tick,
        IntervalTrigger(seconds=SCHEDULER_POLL_SECONDS),
        args=[bot],
        id="schedule-tick",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    if ANALYTICS_FETCH_INTERVAL_HOURS > 0:
        scheduler.add_job(
            _analytics_tick,
            IntervalTrigger(hours=ANALYTICS_FETCH_INTERVAL_HOURS),
            args=[bot],
            id="analytics-tick",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
    else:
        LOGGER.warning(
            "ANALYTICS_FETCH_INTERVAL_HOURS=%d は無効な値です（正の整数を指定してください）。"
            "自動アナリティクス取得ジョブを登録しませんでした。",
            ANALYTICS_FETCH_INTERVAL_HOURS,
        )
    scheduler.start()
    _scheduler = scheduler
    return scheduler


async def _tick(bot) -> None:
    """スケジューラから定期的に呼ばれるポーリング処理。例外はログに記録してスキップする。"""
    if not hasattr(bot, "dispatch_scheduled_posts"):
        return
    try:
        await bot.dispatch_scheduled_posts()
    except asyncio.CancelledError:
        raise
    except Exception:
        LOGGER.exception("Scheduled dispatch failed")


async def _analytics_tick(bot) -> None:
    """スケジューラから定期的に呼ばれるアナリティクス自動取得処理。例外はログに記録してスキップする。"""
    if not hasattr(bot, "dispatch_analytics"):
        return
    try:
        await bot.dispatch_analytics()
    except asyncio.CancelledError:
        raise
    except Exception:
        LOGGER.exception("Scheduled analytics failed")


async def dispatch_scheduled_posts(bot) -> bool:
    """現在時刻が有効なスロットに一致する場合、承認済み下書きを Twitter/X に投稿する。

    Returns:
        投稿を実行した場合は True、スロット不一致・キューが空の場合は False。
    """
    global _last_slot_key

    now = datetime.now(JST)
    slot_time = now.strftime("%H:%M")
    # 現在時刻に一致する有効なスロットを取得
    current_slot = await db.get_slot_by_time(slot_time)
    if not current_slot:
        return False

    # 同じスロットへの二重投稿を防ぐ
    slot_key = f"{now.strftime('%Y-%m-%d')}T{slot_time}"
    if _last_slot_key == slot_key:
        return False

    # 次の承認済み下書きグループを取得
    drafts = await db.pick_next_approved_draft_group()
    if not drafts:
        _last_slot_key = slot_key
        return False

    # 複数言語の下書きを順に投稿（ja → en のスレッド形式）
    reply_to_tweet_id: str | None = None
    for draft in drafts:
        asset = await db.get_asset_by_id(draft["asset_id"]) if draft.get("asset_id") else None
        tweet_id, tweet_url = await twitter.post_tweet(
            content=draft["content"],
            media_path=asset["local_path"] if asset else None,
            game_id=draft["game_id"],
            reply_to_tweet_id=reply_to_tweet_id,
        )
        # 投稿済みツイートを DB に記録
        await db.add_tweet(
            {
                "tweet_id": tweet_id,
                "game_id": draft["game_id"],
                "lang": draft.get("lang"),
                "content": draft["content"],
                "asset_id": draft.get("asset_id"),
                "tone": draft.get("tone"),
                "strategy_note": draft.get("strategy_note"),
                "posted_at": now.isoformat(),
                "tweet_url": tweet_url,
                "approved_by": draft.get("approved_by"),
                "reply_to_tweet_id": reply_to_tweet_id,
            }
        )
        # 次の言語はこのツイートへのリプライとして投稿する
        reply_to_tweet_id = tweet_id

    # 下書きのステータスを "posted" に更新し、使用した進捗・アピールポイントを消費済みにする
    await db.mark_drafts_posted([int(draft["id"]) for draft in drafts])
    await db.consume_draft_sources(drafts)
    _last_slot_key = slot_key
    return True


# Twitter API v2 の get_tweets エンドポイントは 1 リクエストあたり最大 100 件
_TWITTER_BATCH_SIZE = 100


async def dispatch_analytics(bot) -> int:
    """すべてのゲームの直近 90 日間のツイートのメトリクスを取得し、結果を蓄積する。

    Twitter API の制限に対応するため、100 件ずつバッチ処理する。
    tweets テーブルを最新値で更新しつつ、tweet_metrics_history にスナップショットを追加する。

    Returns:
        更新したメトリクス件数の合計。
    """
    game_ids = await db.get_all_game_ids()
    if not game_ids:
        return 0

    # 全ゲームの tweet_id を収集する（重複は除去）
    all_tweet_ids: list[str] = []
    seen: set[str] = set()
    for game_id in game_ids:
        tweets = await db.get_recent_tweets_for_analytics(game_id, days=90)
        for tweet in tweets:
            tid = tweet.get("tweet_id")
            if tid and tid not in seen:
                all_tweet_ids.append(tid)
                seen.add(tid)

    if not all_tweet_ids:
        return 0

    # 100 件ずつバッチで Twitter API を呼び出す
    total_updated = 0
    for i in range(0, len(all_tweet_ids), _TWITTER_BATCH_SIZE):
        batch = all_tweet_ids[i : i + _TWITTER_BATCH_SIZE]
        metrics = await twitter.fetch_tweet_metrics(batch)
        await db.batch_update_tweet_analytics(metrics)
        total_updated += len(metrics)

    LOGGER.info("Auto-analytics: updated %d tweet metrics snapshots", total_updated)
    return total_updated
