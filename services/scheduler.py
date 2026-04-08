from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import JST, SCHEDULER_POLL_SECONDS
from services import db, twitter

LOGGER = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None
_last_slot_key: str | None = None


def setup_scheduler(bot) -> AsyncIOScheduler:
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
    scheduler.start()
    _scheduler = scheduler
    return scheduler


async def _tick(bot) -> None:
    if not hasattr(bot, "dispatch_scheduled_posts"):
        return
    try:
        await bot.dispatch_scheduled_posts()
    except asyncio.CancelledError:
        raise
    except Exception:
        LOGGER.exception("Scheduled dispatch failed")


async def dispatch_scheduled_posts(bot) -> bool:
    global _last_slot_key

    now = datetime.now(JST)
    slot_time = now.strftime("%H:%M")
    current_slot = await db.get_slot_by_time(slot_time)
    if not current_slot:
        return False

    slot_key = f"{now.strftime('%Y-%m-%d')}T{slot_time}"
    if _last_slot_key == slot_key:
        return False

    drafts = await db.pick_next_approved_draft_group()
    if not drafts:
        _last_slot_key = slot_key
        return False

    reply_to_tweet_id: str | None = None
    for draft in drafts:
        asset = await db.get_asset_by_id(draft["asset_id"]) if draft.get("asset_id") else None
        tweet_id, tweet_url = await twitter.post_tweet(
            content=draft["content"],
            media_path=asset["local_path"] if asset else None,
            game_id=draft["game_id"],
            reply_to_tweet_id=reply_to_tweet_id,
        )
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
        reply_to_tweet_id = tweet_id

    await db.mark_drafts_posted([int(draft["id"]) for draft in drafts])
    await db.consume_draft_sources(drafts)
    _last_slot_key = slot_key
    return True
