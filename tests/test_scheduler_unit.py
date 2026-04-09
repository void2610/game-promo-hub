from __future__ import annotations

import tempfile
import unittest
import unittest.mock
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import config
from services import db, scheduler


class TickTests(unittest.IsolatedAsyncioTestCase):
    """_tick のユニットテスト。"""

    async def test_tick_returns_early_without_dispatch_method(self) -> None:
        """bot に dispatch_scheduled_posts がない場合、何も行わずに返ることを確認する。"""
        bot = object()  # dispatch_scheduled_posts を持たないオブジェクト
        # 例外が発生しないことを確認
        await scheduler._tick(bot)

    async def test_tick_calls_dispatch_scheduled_posts(self) -> None:
        """bot に dispatch_scheduled_posts がある場合、それが呼ばれることを確認する。"""
        bot = MagicMock()
        bot.dispatch_scheduled_posts = AsyncMock(return_value=False)
        await scheduler._tick(bot)
        bot.dispatch_scheduled_posts.assert_awaited_once()

    async def test_tick_suppresses_exception(self) -> None:
        """dispatch_scheduled_posts が例外を送出しても _tick が再送出しないことを確認する。"""
        bot = MagicMock()
        bot.dispatch_scheduled_posts = AsyncMock(side_effect=RuntimeError("boom"))
        # 例外が外に漏れないことを確認
        await scheduler._tick(bot)

    async def test_tick_reraises_cancelled_error(self) -> None:
        """asyncio.CancelledError は _tick から再送出されることを確認する。"""
        import asyncio

        bot = MagicMock()
        bot.dispatch_scheduled_posts = AsyncMock(side_effect=asyncio.CancelledError())
        with self.assertRaises(asyncio.CancelledError):
            await scheduler._tick(bot)


class AnalyticsTickTests(unittest.IsolatedAsyncioTestCase):
    """_analytics_tick のユニットテスト。"""

    async def test_analytics_tick_returns_early_without_dispatch_method(self) -> None:
        """bot に dispatch_analytics がない場合、何も行わずに返ることを確認する。"""
        bot = object()
        await scheduler._analytics_tick(bot)

    async def test_analytics_tick_calls_dispatch_analytics(self) -> None:
        """bot に dispatch_analytics がある場合、それが呼ばれることを確認する。"""
        bot = MagicMock()
        bot.dispatch_analytics = AsyncMock(return_value=0)
        await scheduler._analytics_tick(bot)
        bot.dispatch_analytics.assert_awaited_once()

    async def test_analytics_tick_suppresses_exception(self) -> None:
        """dispatch_analytics が例外を送出しても _analytics_tick が再送出しないことを確認する。"""
        bot = MagicMock()
        bot.dispatch_analytics = AsyncMock(side_effect=ValueError("error"))
        await scheduler._analytics_tick(bot)

    async def test_analytics_tick_reraises_cancelled_error(self) -> None:
        """asyncio.CancelledError は _analytics_tick から再送出されることを確認する。"""
        import asyncio

        bot = MagicMock()
        bot.dispatch_analytics = AsyncMock(side_effect=asyncio.CancelledError())
        with self.assertRaises(asyncio.CancelledError):
            await scheduler._analytics_tick(bot)


class DispatchScheduledPostsTests(unittest.IsolatedAsyncioTestCase):
    """dispatch_scheduled_posts のユニットテスト。"""

    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_db = Path(self.temp_dir.name) / "test.db"
        config.DB_PATH = temp_db
        db.DB_PATH = temp_db
        scheduler._last_slot_key = None
        await db.init_db()

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()
        scheduler._last_slot_key = None

    async def test_returns_false_when_no_matching_slot(self) -> None:
        """現在時刻に一致するスロットが存在しない場合に False が返されることを確認する。"""
        # スロットを一切登録しない
        result = await scheduler.dispatch_scheduled_posts(object())
        self.assertFalse(result)

    async def test_returns_false_for_duplicate_slot_key(self) -> None:
        """同一スロットへの二重投稿を防ぐために 2 回目は False が返されることを確認する。"""
        from datetime import datetime

        now = datetime.now(config.JST)
        slot_time = now.strftime("%H:%M")
        await db.add_schedule_slot(slot_time)
        # _last_slot_key をあらかじめ設定して「処理済み」にする
        slot_key = f"{now.strftime('%Y-%m-%d')}T{slot_time}"
        scheduler._last_slot_key = slot_key

        result = await scheduler.dispatch_scheduled_posts(object())
        self.assertFalse(result)

    async def test_returns_false_and_sets_slot_key_when_queue_empty(self) -> None:
        """スロットが一致しても承認済み下書きがない場合は False を返し、スロットキーを設定することを確認する。"""
        from datetime import datetime

        now = datetime.now(config.JST)
        slot_time = now.strftime("%H:%M")
        await db.add_schedule_slot(slot_time)

        result = await scheduler.dispatch_scheduled_posts(object())
        self.assertFalse(result)
        # スロットキーが設定されていることを確認（次回の二重投稿防止）
        self.assertIsNotNone(scheduler._last_slot_key)

    async def test_posts_tweet_and_returns_true(self) -> None:
        """スロットが一致し承認済み下書きがある場合、ツイートを投稿して True が返されることを確認する。"""
        from datetime import datetime

        await db.add_game(
            {
                "id": "game-sched",
                "name_ja": "Sched Game",
                "name_en": None,
                "genre": "puzzle",
                "platform": "Steam",
                "status": "development",
                "steam_url": None,
                "elevator_ja": None,
                "elevator_en": None,
                "hashtags": [],
                "target_audience": [],
                "circle": None,
            }
        )
        draft_id = await db.add_draft(
            {
                "draft_group_id": None,
                "game_id": "game-sched",
                "mode": "random",
                "lang": "ja",
                "content": "Tweet content",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "asset_reason": None,
                "source_progress_ids": [],
                "source_appeal_ids": [],
            }
        )
        await db.approve_draft_group(None, approved_by="u1", draft_id=draft_id)

        now = datetime.now(config.JST)
        slot_time = now.strftime("%H:%M")
        await db.add_schedule_slot(slot_time)

        with patch("services.scheduler.twitter.post_tweet", new=AsyncMock(return_value=("tweet-id-1", "https://x.com/i/web/status/tweet-id-1"))):
            result = await scheduler.dispatch_scheduled_posts(object())

        self.assertTrue(result)
        # 下書きが "posted" になっていることを確認
        draft = await db.get_draft(draft_id)
        self.assertEqual(draft["status"], "posted")


class DispatchAnalyticsTests(unittest.IsolatedAsyncioTestCase):
    """dispatch_analytics のユニットテスト。"""

    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_db = Path(self.temp_dir.name) / "test.db"
        config.DB_PATH = temp_db
        db.DB_PATH = temp_db
        await db.init_db()

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def test_returns_zero_when_no_games(self) -> None:
        """ゲームが登録されていない場合に 0 が返されることを確認する。"""
        result = await scheduler.dispatch_analytics(object())
        self.assertEqual(result, 0)

    async def test_returns_zero_when_no_tweets(self) -> None:
        """ゲームはあるがツイートがない場合に 0 が返されることを確認する。"""
        await db.add_game(
            {
                "id": "game-notw",
                "name_ja": "No Tweet Game",
                "name_en": None,
                "genre": None,
                "platform": "Steam",
                "status": "development",
                "steam_url": None,
                "elevator_ja": None,
                "elevator_en": None,
                "hashtags": [],
                "target_audience": [],
                "circle": None,
            }
        )
        result = await scheduler.dispatch_analytics(object())
        self.assertEqual(result, 0)

    async def test_fetches_and_updates_metrics(self) -> None:
        """ツイートがある場合に fetch_tweet_metrics が呼ばれ、更新件数が返されることを確認する。"""
        from datetime import datetime

        await db.add_game(
            {
                "id": "game-met",
                "name_ja": "Metrics Game",
                "name_en": None,
                "genre": None,
                "platform": "Steam",
                "status": "development",
                "steam_url": None,
                "elevator_ja": None,
                "elevator_en": None,
                "hashtags": [],
                "target_audience": [],
                "circle": None,
            }
        )
        now_iso = datetime.now(config.JST).isoformat()
        await db.add_tweet(
            {
                "tweet_id": "t-met-01",
                "game_id": "game-met",
                "lang": "ja",
                "content": "Some tweet",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "posted_at": now_iso,
                "tweet_url": "https://x.com/i/web/status/t-met-01",
                "approved_by": "1",
                "reply_to_tweet_id": None,
            }
        )

        fake_metrics = [
            {"tweet_id": "t-met-01", "impressions": 500, "likes": 20, "retweets": 5, "replies": 2}
        ]
        with patch(
            "services.scheduler.twitter.fetch_tweet_metrics",
            new=AsyncMock(return_value=fake_metrics),
        ):
            result = await scheduler.dispatch_analytics(object())

        self.assertEqual(result, 1)
        # tweets テーブルのメトリクスが更新されていることを確認
        tweets = await db.get_recent_tweets_for_analytics("game-met", days=90)
        self.assertEqual(tweets[0]["impressions"], 500)
        self.assertEqual(tweets[0]["likes"], 20)

    async def test_deduplicates_tweet_ids_across_games(self) -> None:
        """同じツイート ID が複数ゲームに存在する場合、重複排除して1件として扱うことを確認する。"""
        from datetime import datetime

        for gid, gname in [("game-dup-1", "Dup Game 1"), ("game-dup-2", "Dup Game 2")]:
            await db.add_game(
                {
                    "id": gid,
                    "name_ja": gname,
                    "name_en": None,
                    "genre": None,
                    "platform": "Steam",
                    "status": "development",
                    "steam_url": None,
                    "elevator_ja": None,
                    "elevator_en": None,
                    "hashtags": [],
                    "target_audience": [],
                    "circle": None,
                }
            )

        now_iso = datetime.now(config.JST).isoformat()
        for gid, tid in [("game-dup-1", "shared-tweet"), ("game-dup-2", "unique-tweet")]:
            await db.add_tweet(
                {
                    "tweet_id": tid,
                    "game_id": gid,
                    "lang": "ja",
                    "content": "Tweet",
                    "asset_id": None,
                    "tone": "casual",
                    "strategy_note": None,
                    "posted_at": now_iso,
                    "tweet_url": f"https://x.com/i/web/status/{tid}",
                    "approved_by": "1",
                    "reply_to_tweet_id": None,
                }
            )

        captured_ids: list[list[str]] = []

        async def fake_fetch(tweet_ids: list[str]) -> list[dict]:
            captured_ids.append(list(tweet_ids))
            return [{"tweet_id": tid, "impressions": 0, "likes": 0, "retweets": 0, "replies": 0} for tid in tweet_ids]

        with patch("services.scheduler.twitter.fetch_tweet_metrics", new=fake_fetch):
            await scheduler.dispatch_analytics(object())

        self.assertEqual(len(captured_ids), 1)
        # "shared-tweet" は1件だけ渡されることを確認
        self.assertEqual(len(captured_ids[0]), 2)


if __name__ == "__main__":
    unittest.main()
