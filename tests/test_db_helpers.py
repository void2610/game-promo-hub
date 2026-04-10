from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import config
from services import db


class JsonHelpersTests(unittest.TestCase):
    """_json_dumps / _json_loads のユニットテスト。"""

    def test_json_dumps_none(self) -> None:
        """None を渡すと '[]' が返されることを確認する。"""
        self.assertEqual(db._json_dumps(None), "[]")

    def test_json_dumps_empty_list(self) -> None:
        """空リストを渡すと '[]' が返されることを確認する。"""
        self.assertEqual(db._json_dumps([]), "[]")

    def test_json_dumps_string_list(self) -> None:
        """文字列リストが JSON 文字列に変換されることを確認する。"""
        import json
        result = db._json_dumps(["#gamedev", "#indiegame"])
        self.assertEqual(json.loads(result), ["#gamedev", "#indiegame"])

    def test_json_dumps_int_list(self) -> None:
        """整数リストが JSON 文字列に変換されることを確認する。"""
        import json
        result = db._json_dumps([1, 2, 3])
        self.assertEqual(json.loads(result), [1, 2, 3])

    def test_json_loads_none(self) -> None:
        """None を渡すと空リストが返されることを確認する。"""
        self.assertEqual(db._json_loads(None), [])

    def test_json_loads_empty_string(self) -> None:
        """空文字列を渡すと空リストが返されることを確認する。"""
        self.assertEqual(db._json_loads(""), [])

    def test_json_loads_valid_json(self) -> None:
        """有効な JSON 文字列がリストに変換されることを確認する。"""
        self.assertEqual(db._json_loads('["a", "b"]'), ["a", "b"])

    def test_json_loads_int_list(self) -> None:
        """整数 JSON 配列がリストに変換されることを確認する。"""
        self.assertEqual(db._json_loads("[1, 2, 3]"), [1, 2, 3])

    def test_json_dumps_and_loads_roundtrip(self) -> None:
        """dumps → loads のラウンドトリップで元のリストが復元されることを確認する。"""
        original = ["#gamedev", "#rpg", "#indiedev"]
        self.assertEqual(db._json_loads(db._json_dumps(original)), original)


class TweetAnalyticsTests(unittest.IsolatedAsyncioTestCase):
    """ツイートアナリティクス関連の db 関数のテスト。"""

    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_db = Path(self.temp_dir.name) / "test.db"
        config.DB_PATH = temp_db
        db.DB_PATH = temp_db
        await db.init_db()
        # ゲームとツイートを追加
        await db.add_game(
            {
                "id": "game-analytics",
                "name_ja": "Analytics Game",
                "name_en": None,
                "genre": "action",
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
                "tweet_id": "tw-analytics-1",
                "game_id": "game-analytics",
                "lang": "ja",
                "content": "テストツイート",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "posted_at": now_iso,
                "tweet_url": "https://x.com/i/web/status/tw-analytics-1",
                "approved_by": "1",
                "reply_to_tweet_id": None,
            }
        )

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def test_update_tweet_analytics(self) -> None:
        """update_tweet_analytics でメトリクスが更新されることを確認する。"""
        await db.update_tweet_analytics("tw-analytics-1", 1000, 50, 10, 5)
        tweets = await db.get_recent_tweets_for_analytics("game-analytics")
        self.assertEqual(len(tweets), 1)
        self.assertEqual(tweets[0]["impressions"], 1000)
        self.assertEqual(tweets[0]["likes"], 50)
        self.assertEqual(tweets[0]["retweets"], 10)
        self.assertEqual(tweets[0]["replies"], 5)
        self.assertIsNotNone(tweets[0]["analytics_fetched_at"])

    async def test_update_tweet_analytics_also_inserts_history(self) -> None:
        """update_tweet_analytics でメトリクス履歴に行が追加されることを確認する。"""
        await db.update_tweet_analytics("tw-analytics-1", 200, 20, 4, 2)
        history = await db.get_tweet_metrics_history("tw-analytics-1")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["impressions"], 200)
        self.assertEqual(history[0]["likes"], 20)

    async def test_batch_update_tweet_analytics_empty(self) -> None:
        """空リストを渡しても例外が発生しないことを確認する。"""
        await db.batch_update_tweet_analytics([])

    async def test_batch_update_tweet_analytics(self) -> None:
        """batch_update_tweet_analytics で複数ツイートをまとめて更新できることを確認する。"""
        now_iso = datetime.now(config.JST).isoformat()
        await db.add_tweet(
            {
                "tweet_id": "tw-batch-2",
                "game_id": "game-analytics",
                "lang": "ja",
                "content": "バッチツイート2",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "posted_at": now_iso,
                "tweet_url": "https://x.com/i/web/status/tw-batch-2",
                "approved_by": "1",
                "reply_to_tweet_id": None,
            }
        )
        metrics = [
            {"tweet_id": "tw-analytics-1", "impressions": 500, "likes": 25, "retweets": 5, "replies": 2},
            {"tweet_id": "tw-batch-2", "impressions": 300, "likes": 10, "retweets": 3, "replies": 1},
        ]
        await db.batch_update_tweet_analytics(metrics)
        tweets = await db.get_recent_tweets_for_analytics("game-analytics")
        by_id = {t["tweet_id"]: t for t in tweets}
        self.assertEqual(by_id["tw-analytics-1"]["impressions"], 500)
        self.assertEqual(by_id["tw-batch-2"]["likes"], 10)

    async def test_batch_update_inserts_history(self) -> None:
        """batch_update_tweet_analytics でメトリクス履歴に行が追加されることを確認する。"""
        metrics = [
            {"tweet_id": "tw-analytics-1", "impressions": 700, "likes": 30, "retweets": 6, "replies": 3},
        ]
        await db.batch_update_tweet_analytics(metrics)
        history = await db.get_tweet_metrics_history("tw-analytics-1")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["impressions"], 700)

    async def test_insert_tweet_metrics_snapshot(self) -> None:
        """insert_tweet_metrics_snapshot で履歴が追加されることを確認する。"""
        await db.insert_tweet_metrics_snapshot("tw-analytics-1", 100, 5, 1, 0)
        history = await db.get_tweet_metrics_history("tw-analytics-1")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["tweet_id"], "tw-analytics-1")
        self.assertEqual(history[0]["replies"], 0)

    async def test_insert_multiple_snapshots_ordered_asc(self) -> None:
        """複数スナップショットが fetched_at 昇順で返されることを確認する。"""
        await db.insert_tweet_metrics_snapshot("tw-analytics-1", 100, 5, 1, 0)
        await db.insert_tweet_metrics_snapshot("tw-analytics-1", 200, 10, 2, 1)
        history = await db.get_tweet_metrics_history("tw-analytics-1")
        self.assertEqual(len(history), 2)
        # 先に挿入した方のインプレッションが小さいはず
        self.assertLessEqual(history[0]["impressions"], history[1]["impressions"])

    async def test_get_tweet_metrics_history_empty(self) -> None:
        """履歴がない場合に空リストが返されることを確認する。"""
        history = await db.get_tweet_metrics_history("tw-analytics-1")
        self.assertEqual(history, [])

    async def test_get_tweet_metrics_history_wrong_id(self) -> None:
        """存在しないツイート ID に対して空リストが返されることを確認する。"""
        await db.insert_tweet_metrics_snapshot("tw-analytics-1", 100, 5, 1, 0)
        history = await db.get_tweet_metrics_history("tw-nonexistent")
        self.assertEqual(history, [])


class GetTopTweetsTests(unittest.IsolatedAsyncioTestCase):
    """get_top_tweets のユニットテスト。"""

    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_db = Path(self.temp_dir.name) / "test.db"
        config.DB_PATH = temp_db
        db.DB_PATH = temp_db
        await db.init_db()
        await db.add_game(
            {
                "id": "game-top",
                "name_ja": "Top Game",
                "name_en": None,
                "genre": "action",
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

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def _add_tweet(self, tweet_id: str) -> None:
        now_iso = datetime.now(config.JST).isoformat()
        await db.add_tweet(
            {
                "tweet_id": tweet_id,
                "game_id": "game-top",
                "lang": "ja",
                "content": f"Tweet {tweet_id}",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "posted_at": now_iso,
                "tweet_url": f"https://x.com/i/web/status/{tweet_id}",
                "approved_by": "1",
                "reply_to_tweet_id": None,
            }
        )

    async def test_get_top_tweets_empty(self) -> None:
        """ツイートがない場合（またはインプレッション未設定）に空リストが返されることを確認する。"""
        result = await db.get_top_tweets("game-top")
        self.assertEqual(result, [])

    async def test_get_top_tweets_ranked_by_engagement(self) -> None:
        """エンゲージメント率でランキングされることを確認する。"""
        await self._add_tweet("tw-top-a")
        await self._add_tweet("tw-top-b")
        # tw-top-a: impressions=1000, likes=100, retweets=10 → eng_rate=(110/1000)=0.11
        await db.update_tweet_analytics("tw-top-a", 1000, 100, 10, 5)
        # tw-top-b: impressions=500, likes=50, retweets=5 → eng_rate=(55/500)=0.11 (同率)
        await db.update_tweet_analytics("tw-top-b", 500, 50, 5, 2)
        result = await db.get_top_tweets("game-top")
        self.assertGreaterEqual(len(result), 1)
        # すべてに impressions が設定されている
        for tweet in result:
            self.assertIsNotNone(tweet["impressions"])

    async def test_get_top_tweets_limit(self) -> None:
        """limit パラメータが反映されることを確認する。"""
        for i in range(5):
            await self._add_tweet(f"tw-lim-{i}")
            await db.update_tweet_analytics(f"tw-lim-{i}", 100 + i * 10, i, 0, 0)
        result = await db.get_top_tweets("game-top", limit=3)
        self.assertLessEqual(len(result), 3)

    async def test_get_top_tweets_excludes_no_impressions(self) -> None:
        """インプレッション未設定のツイートが結果に含まれないことを確認する。"""
        await self._add_tweet("tw-no-imp")
        # analytics を設定しないまま
        result = await db.get_top_tweets("game-top")
        tweet_ids = [t["tweet_id"] for t in result]
        self.assertNotIn("tw-no-imp", tweet_ids)


class PendingDraftsAndPostedTests(unittest.IsolatedAsyncioTestCase):
    """list_pending_drafts / mark_drafts_posted のテスト。"""

    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_db = Path(self.temp_dir.name) / "test.db"
        config.DB_PATH = temp_db
        db.DB_PATH = temp_db
        await db.init_db()
        await db.add_game(
            {
                "id": "game-pending",
                "name_ja": "Pending Game",
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

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    def _draft_data(self, content: str = "test") -> dict:
        return {
            "draft_group_id": None,
            "game_id": "game-pending",
            "mode": "random",
            "lang": "ja",
            "content": content,
            "asset_id": None,
            "tone": "casual",
            "strategy_note": None,
            "asset_reason": None,
            "source_progress_ids": [],
            "source_appeal_ids": [],
        }

    async def test_list_pending_drafts_empty(self) -> None:
        """pending の下書きがない場合に空リストが返されることを確認する。"""
        result = await db.list_pending_drafts()
        self.assertEqual(result, [])

    async def test_list_pending_drafts_returns_pending(self) -> None:
        """pending ステータスの下書きが返されることを確認する。"""
        await db.add_draft(self._draft_data("pending content"))
        result = await db.list_pending_drafts()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["status"], "pending")
        self.assertEqual(result[0]["content"], "pending content")

    async def test_list_pending_drafts_filter_by_game_id(self) -> None:
        """game_id でフィルタできることを確認する。"""
        await db.add_draft(self._draft_data())
        result = await db.list_pending_drafts(game_id="game-pending")
        self.assertEqual(len(result), 1)
        result_no_match = await db.list_pending_drafts(game_id="other-game")
        self.assertEqual(result_no_match, [])

    async def test_list_pending_drafts_excludes_approved(self) -> None:
        """approved ステータスの下書きが含まれないことを確認する。"""
        draft_id = await db.add_draft(self._draft_data())
        await db.approve_draft_group(None, approved_by="u1", draft_id=draft_id)
        result = await db.list_pending_drafts()
        self.assertEqual(result, [])

    async def test_list_pending_drafts_limit(self) -> None:
        """limit パラメータが反映されることを確認する。"""
        for i in range(5):
            await db.add_draft(self._draft_data(f"content {i}"))
        result = await db.list_pending_drafts(limit=3)
        self.assertLessEqual(len(result), 3)

    async def test_mark_drafts_posted_empty(self) -> None:
        """空リストを渡しても例外が発生しないことを確認する。"""
        await db.mark_drafts_posted([])

    async def test_mark_drafts_posted_updates_status(self) -> None:
        """指定した下書きのステータスが 'posted' に更新されることを確認する。"""
        id1 = await db.add_draft(self._draft_data("post me"))
        id2 = await db.add_draft(self._draft_data("keep me"))
        await db.mark_drafts_posted([id1])
        d1 = await db.get_draft(id1)
        d2 = await db.get_draft(id2)
        self.assertEqual(d1["status"], "posted")
        self.assertEqual(d2["status"], "pending")

    async def test_mark_drafts_posted_multiple(self) -> None:
        """複数の下書き ID をまとめて posted に更新できることを確認する。"""
        id1 = await db.add_draft(self._draft_data("A"))
        id2 = await db.add_draft(self._draft_data("B"))
        await db.mark_drafts_posted([id1, id2])
        d1 = await db.get_draft(id1)
        d2 = await db.get_draft(id2)
        self.assertEqual(d1["status"], "posted")
        self.assertEqual(d2["status"], "posted")


class ScheduleSlotDbTests(unittest.IsolatedAsyncioTestCase):
    """add_schedule_slot / list_schedule_slots / get_slot_by_time / remove_schedule_slot のテスト。"""

    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_db = Path(self.temp_dir.name) / "test.db"
        config.DB_PATH = temp_db
        db.DB_PATH = temp_db
        await db.init_db()

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def test_add_schedule_slot_returns_id(self) -> None:
        """add_schedule_slot が整数の ID を返すことを確認する。"""
        slot_id = await db.add_schedule_slot("09:00")
        self.assertIsInstance(slot_id, int)
        self.assertGreater(slot_id, 0)

    async def test_list_schedule_slots_empty(self) -> None:
        """スロットがない場合に空リストが返されることを確認する。"""
        result = await db.list_schedule_slots()
        self.assertEqual(result, [])

    async def test_list_schedule_slots_sorted_asc(self) -> None:
        """スロットが slot_time の昇順で返されることを確認する。"""
        await db.add_schedule_slot("20:00")
        await db.add_schedule_slot("09:00")
        await db.add_schedule_slot("14:30")
        result = await db.list_schedule_slots()
        times = [row["slot_time"] for row in result]
        self.assertEqual(times, sorted(times))

    async def test_get_slot_by_time_found(self) -> None:
        """一致するスロットが返されることを確認する。"""
        await db.add_schedule_slot("08:00")
        slot = await db.get_slot_by_time("08:00")
        self.assertIsNotNone(slot)
        self.assertEqual(slot["slot_time"], "08:00")
        self.assertEqual(slot["enabled"], 1)

    async def test_get_slot_by_time_not_found(self) -> None:
        """一致するスロットがない場合に None が返されることを確認する。"""
        slot = await db.get_slot_by_time("23:59")
        self.assertIsNone(slot)

    async def test_remove_schedule_slot(self) -> None:
        """remove_schedule_slot でスロットを削除できることを確認する。"""
        slot_id = await db.add_schedule_slot("12:00")
        await db.remove_schedule_slot(slot_id)
        slots = await db.list_schedule_slots()
        ids = [s["id"] for s in slots]
        self.assertNotIn(slot_id, ids)

    async def test_remove_nonexistent_slot_no_error(self) -> None:
        """存在しない ID を remove_schedule_slot に渡しても例外が発生しないことを確認する。"""
        await db.remove_schedule_slot(9999)


class SaveAnalyticsSummaryTests(unittest.IsolatedAsyncioTestCase):
    """save_analytics_summary のテスト。"""

    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_db = Path(self.temp_dir.name) / "test.db"
        config.DB_PATH = temp_db
        db.DB_PATH = temp_db
        await db.init_db()
        await db.add_game(
            {
                "id": "game-summary",
                "name_ja": "Summary Game",
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

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def test_save_and_retrieve_summary(self) -> None:
        """サマリーを保存して DB から取得できることを確認する。"""
        import aiosqlite

        result = {
            "best_time_slot": "21:00",
            "best_tone": "excited",
            "best_asset_type": "gif",
            "next_strategy": "動画を増やす",
            "top_tweets": [],
        }
        await db.save_analytics_summary("game-summary", "weekly", result)

        async with aiosqlite.connect(config.DB_PATH) as con:
            con.row_factory = aiosqlite.Row
            async with con.execute(
                "SELECT * FROM analytics_summaries WHERE game_id = ?", ("game-summary",)
            ) as cursor:
                rows = await cursor.fetchall()

        self.assertEqual(len(rows), 1)
        row = dict(rows[0])
        self.assertEqual(row["game_id"], "game-summary")
        self.assertEqual(row["period"], "weekly")
        self.assertEqual(row["best_time_slot"], "21:00")
        self.assertEqual(row["best_tone"], "excited")
        self.assertEqual(row["strategy_note"], "動画を増やす")

    async def test_save_multiple_summaries(self) -> None:
        """複数のサマリーを保存できることを確認する。"""
        import aiosqlite

        await db.save_analytics_summary("game-summary", "weekly", {"advice": "a"})
        await db.save_analytics_summary("game-summary", "monthly", {"advice": "b"})

        async with aiosqlite.connect(config.DB_PATH) as con:
            con.row_factory = aiosqlite.Row
            async with con.execute(
                "SELECT COUNT(*) as cnt FROM analytics_summaries WHERE game_id = ?",
                ("game-summary",),
            ) as cursor:
                row = dict(await cursor.fetchone())

        self.assertEqual(row["cnt"], 2)


class GetQueueItemTests(unittest.IsolatedAsyncioTestCase):
    """get_queue_item のテスト。"""

    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_db = Path(self.temp_dir.name) / "test.db"
        config.DB_PATH = temp_db
        db.DB_PATH = temp_db
        await db.init_db()
        await db.add_game(
            {
                "id": "game-queue",
                "name_ja": "Queue Game",
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

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    def _draft_data(self, group_id: str | None = None) -> dict:
        return {
            "draft_group_id": group_id,
            "game_id": "game-queue",
            "mode": "random",
            "lang": "ja",
            "content": "test",
            "asset_id": None,
            "tone": "casual",
            "strategy_note": None,
            "asset_reason": None,
            "source_progress_ids": [],
            "source_appeal_ids": [],
        }

    async def test_get_queue_item_single(self) -> None:
        """'single:ID' 形式の queue_id から単一下書きが取得できることを確認する。"""
        draft_id = await db.add_draft(self._draft_data())
        result = await db.get_queue_item(f"single:{draft_id}")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], draft_id)

    async def test_get_queue_item_single_missing(self) -> None:
        """存在しない 'single:ID' を渡すと空リストが返されることを確認する。"""
        result = await db.get_queue_item("single:99999")
        self.assertEqual(result, [])

    async def test_get_queue_item_group(self) -> None:
        """グループ ID から複数下書きがまとめて取得できることを確認する。"""
        group_id = db.generate_draft_group_id()
        await db.add_draft(self._draft_data(group_id=group_id))
        await db.add_draft({**self._draft_data(group_id=group_id), "lang": "en"})
        result = await db.get_queue_item(group_id)
        self.assertEqual(len(result), 2)
        langs = {d["lang"] for d in result}
        self.assertIn("ja", langs)
        self.assertIn("en", langs)


class GetAllGameIdsTests(unittest.IsolatedAsyncioTestCase):
    """get_all_game_ids のテスト。"""

    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_db = Path(self.temp_dir.name) / "test.db"
        config.DB_PATH = temp_db
        db.DB_PATH = temp_db
        await db.init_db()

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def test_get_all_game_ids_empty(self) -> None:
        """ゲームが登録されていない場合に空リストが返されることを確認する。"""
        result = await db.get_all_game_ids()
        self.assertEqual(result, [])

    async def test_get_all_game_ids_returns_ids(self) -> None:
        """登録されたゲームの ID がすべて返されることを確認する。"""
        for gid in ["gid-1", "gid-2", "gid-3"]:
            await db.add_game(
                {
                    "id": gid,
                    "name_ja": f"Game {gid}",
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
        result = await db.get_all_game_ids()
        self.assertIn("gid-1", result)
        self.assertIn("gid-2", result)
        self.assertIn("gid-3", result)
        self.assertEqual(len(result), 3)


class GetAssetByIdTests(unittest.IsolatedAsyncioTestCase):
    """get_asset_by_id のテスト。"""

    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_db = Path(self.temp_dir.name) / "test.db"
        config.DB_PATH = temp_db
        db.DB_PATH = temp_db
        await db.init_db()
        await db.add_game(
            {
                "id": "game-asset",
                "name_ja": "Asset Game",
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

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def test_get_asset_by_id_returns_none_for_missing(self) -> None:
        """存在しない素材 ID に対して None が返されることを確認する。"""
        result = await db.get_asset_by_id(9999)
        self.assertIsNone(result)

    async def test_get_asset_by_id_returns_asset(self) -> None:
        """素材を登録してから ID で取得できることを確認する。"""
        asset_id = await db.add_asset(
            {
                "game_id": "game-asset",
                "filename": "screen.png",
                "asset_type": "png",
                "description": "スクリーンショット",
                "recommended_for": "any",
                "local_path": "/tmp/screen.png",
                "width": 1920,
                "height": 1080,
            }
        )
        result = await db.get_asset_by_id(asset_id)
        self.assertIsNotNone(result)
        self.assertEqual(result["filename"], "screen.png")
        self.assertEqual(result["width"], 1920)


class GetAssetsByRecommendedTests(unittest.IsolatedAsyncioTestCase):
    """get_assets の recommended_for フィルタのテスト。"""

    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_db = Path(self.temp_dir.name) / "test.db"
        config.DB_PATH = temp_db
        db.DB_PATH = temp_db
        await db.init_db()
        await db.add_game(
            {
                "id": "game-rec",
                "name_ja": "Rec Game",
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

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def test_filter_by_recommended_for(self) -> None:
        """recommended_for フィルタで絞り込めることを確認する（"any" 素材も含まれる仕様）。"""
        await db.add_asset(
            {
                "game_id": "game-rec",
                "filename": "gif.gif",
                "asset_type": "gif",
                "description": "GIF",
                "recommended_for": "gif_tweet",
                "local_path": "/tmp/gif.gif",
                "width": None,
                "height": None,
            }
        )
        await db.add_asset(
            {
                "game_id": "game-rec",
                "filename": "img.png",
                "asset_type": "png",
                "description": "PNG",
                "recommended_for": "any",
                "local_path": "/tmp/img.png",
                "width": None,
                "height": None,
            }
        )
        await db.add_asset(
            {
                "game_id": "game-rec",
                "filename": "other.jpg",
                "asset_type": "jpg",
                "description": "Other",
                "recommended_for": "image_tweet",
                "local_path": "/tmp/other.jpg",
                "width": None,
                "height": None,
            }
        )
        # recommended_for="gif_tweet" → "gif_tweet" の素材と "any" の素材が返る
        gif_results = await db.get_assets("game-rec", recommended_for="gif_tweet")
        filenames = {r["filename"] for r in gif_results}
        self.assertIn("gif.gif", filenames)       # exact match
        self.assertIn("img.png", filenames)       # "any" は常に含まれる
        self.assertNotIn("other.jpg", filenames)  # "image_tweet" は含まれない


if __name__ == "__main__":
    unittest.main()
