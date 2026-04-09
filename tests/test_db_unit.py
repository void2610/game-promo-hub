from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import config
from services import db


class DbHelperTests(unittest.TestCase):
    """DB モジュールの純粋なヘルパー関数のユニットテスト。"""

    def test_generate_draft_group_id_is_unique(self) -> None:
        """draft_group_id が毎回異なる値を返すことを確認する。"""
        ids = {db.generate_draft_group_id() for _ in range(10)}
        self.assertEqual(len(ids), 10)

    def test_generate_draft_group_id_is_string(self) -> None:
        """draft_group_id が文字列であることを確認する。"""
        group_id = db.generate_draft_group_id()
        self.assertIsInstance(group_id, str)
        self.assertTrue(len(group_id) > 0)


class DbOperationTests(unittest.IsolatedAsyncioTestCase):
    """個々の DB 操作の単体テスト。各テストは独立した一時 DB で実行される。"""

    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_db = Path(self.temp_dir.name) / "test.db"
        config.DB_PATH = temp_db
        db.DB_PATH = temp_db
        await db.init_db()

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def _add_game(self, game_id: str = "game-x", name: str = "Game X") -> None:
        await db.add_game(
            {
                "id": game_id,
                "name_ja": name,
                "name_en": "Game X EN",
                "genre": "rpg",
                "platform": "Steam",
                "status": "development",
                "steam_url": None,
                "elevator_ja": "面白いゲーム",
                "elevator_en": "A great game",
                "hashtags": ["#indiegame", "#rpg"],
                "target_audience": ["rpg fans"],
                "circle": "test-circle",
            }
        )

    # ---- games テーブル ----

    async def test_get_game_returns_none_for_missing(self) -> None:
        """存在しないゲーム ID に対して None が返されることを確認する。"""
        result = await db.get_game("no-such-game")
        self.assertIsNone(result)

    async def test_add_and_get_game(self) -> None:
        """ゲームを追加してから ID で取得できることを確認する。"""
        await self._add_game()
        game = await db.get_game("game-x")
        self.assertIsNotNone(game)
        self.assertEqual(game["name_ja"], "Game X")
        self.assertEqual(game["hashtags"], ["#indiegame", "#rpg"])
        self.assertEqual(game["target_audience"], ["rpg fans"])

    async def test_list_games_empty(self) -> None:
        """ゲームが登録されていない場合に空リストが返されることを確認する。"""
        result = await db.list_games()
        self.assertEqual(result, [])

    async def test_list_games_multiple(self) -> None:
        """複数のゲームを登録するとすべて取得できることを確認する。"""
        await self._add_game("game-a", "Alpha")
        await self._add_game("game-b", "Beta")
        result = await db.list_games()
        self.assertEqual(len(result), 2)
        ids = {g["id"] for g in result}
        self.assertIn("game-a", ids)
        self.assertIn("game-b", ids)

    # ---- progress_logs テーブル ----

    async def test_get_recent_progress_empty(self) -> None:
        """進捗ログがない場合に空リストが返されることを確認する。"""
        await self._add_game()
        result = await db.get_recent_progress("game-x")
        self.assertEqual(result, [])

    async def test_add_and_get_recent_progress(self) -> None:
        """進捗ログを追加してから取得できることを確認する。"""
        await self._add_game()
        pid = await db.add_progress(
            {
                "game_id": "game-x",
                "log_date": "2026-04-01",
                "milestone": "alpha",
                "content": "New feature",
                "appeal_note": None,
                "excitement": 2,
                "tweetable": 1,
            }
        )
        result = await db.get_recent_progress("game-x")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], pid)
        self.assertEqual(result[0]["content"], "New feature")

    async def test_non_tweetable_progress_excluded(self) -> None:
        """tweetable=0 の進捗ログが取得対象外になることを確認する。"""
        await self._add_game()
        await db.add_progress(
            {
                "game_id": "game-x",
                "log_date": "2026-04-01",
                "milestone": None,
                "content": "Internal note",
                "appeal_note": None,
                "excitement": 1,
                "tweetable": 0,
            }
        )
        result = await db.get_recent_progress("game-x")
        self.assertEqual(result, [])

    async def test_mark_progress_tweeted(self) -> None:
        """mark_progress_tweeted を呼ぶと該当ログが未ツイートリストから消えることを確認する。"""
        await self._add_game()
        pid = await db.add_progress(
            {
                "game_id": "game-x",
                "log_date": "2026-04-01",
                "milestone": None,
                "content": "Done",
                "appeal_note": None,
                "excitement": 2,
                "tweetable": 1,
            }
        )
        await db.mark_progress_tweeted([pid])
        result = await db.get_recent_progress("game-x")
        self.assertEqual(result, [])

    async def test_mark_progress_tweeted_empty_list(self) -> None:
        """空リストを渡しても例外が発生しないことを確認する。"""
        await db.mark_progress_tweeted([])

    # ---- appeal_points テーブル ----

    async def test_get_appeals_empty(self) -> None:
        """アピールポイントがない場合に空リストが返されることを確認する。"""
        await self._add_game()
        result = await db.get_appeals("game-x")
        self.assertEqual(result, [])

    async def test_add_and_get_appeals(self) -> None:
        """アピールポイントを追加してから取得できることを確認する。"""
        await self._add_game()
        aid = await db.add_appeal(
            {
                "game_id": "game-x",
                "category": "art",
                "priority": 3,
                "title": "Beautiful visuals",
                "content": "Hand-painted sprites",
                "promo_tips": "Show a GIF",
            }
        )
        result = await db.get_appeals("game-x")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], aid)
        self.assertEqual(result[0]["title"], "Beautiful visuals")

    async def test_get_appeals_category_filter(self) -> None:
        """category フィルタが正しく機能することを確認する。"""
        await self._add_game()
        await db.add_appeal(
            {
                "game_id": "game-x",
                "category": "art",
                "priority": 2,
                "title": "Art",
                "content": "Nice art",
                "promo_tips": None,
            }
        )
        await db.add_appeal(
            {
                "game_id": "game-x",
                "category": "technical",
                "priority": 2,
                "title": "Tech",
                "content": "Cool tech",
                "promo_tips": None,
            }
        )
        art_results = await db.get_appeals("game-x", category="art")
        self.assertEqual(len(art_results), 1)
        self.assertEqual(art_results[0]["category"], "art")

    async def test_mark_appeal_used_empty_list(self) -> None:
        """空リストを渡しても例外が発生しないことを確認する。"""
        await db.mark_appeal_used([])

    async def test_mark_appeal_used_updates_timestamp(self) -> None:
        """mark_appeal_used を呼ぶと last_used_at が設定されることを確認する。"""
        await self._add_game()
        aid = await db.add_appeal(
            {
                "game_id": "game-x",
                "category": "story",
                "priority": 1,
                "title": "Story",
                "content": "Epic story",
                "promo_tips": None,
            }
        )
        # 使用前は last_used_at が NULL
        result = await db.get_appeals("game-x")
        self.assertIsNone(result[0]["last_used_at"])

        await db.mark_appeal_used([aid])
        result = await db.get_appeals("game-x")
        self.assertIsNotNone(result[0]["last_used_at"])

    # ---- assets テーブル ----

    async def test_get_assets_empty(self) -> None:
        """素材が登録されていない場合に空リストが返されることを確認する。"""
        await self._add_game()
        result = await db.get_assets("game-x")
        self.assertEqual(result, [])

    async def test_add_and_get_asset_by_id(self) -> None:
        """素材を追加してから ID で取得できることを確認する。"""
        await self._add_game()
        asset_id = await db.add_asset(
            {
                "game_id": "game-x",
                "filename": "cover.png",
                "asset_type": "png",
                "description": "Cover image",
                "recommended_for": "any",
                "local_path": "/assets/game-x/cover.png",
                "width": 1280,
                "height": 720,
            }
        )
        asset = await db.get_asset_by_id(asset_id)
        self.assertIsNotNone(asset)
        self.assertEqual(asset["filename"], "cover.png")
        self.assertEqual(asset["width"], 1280)

    async def test_get_asset_by_id_missing(self) -> None:
        """存在しない素材 ID に対して None が返されることを確認する。"""
        result = await db.get_asset_by_id(99999)
        self.assertIsNone(result)

    async def test_get_assets_recommended_for_filter(self) -> None:
        """recommended_for フィルタが機能し、"any" も含まれることを確認する。"""
        await self._add_game()
        await db.add_asset(
            {
                "game_id": "game-x",
                "filename": "a.png",
                "asset_type": "png",
                "description": "",
                "recommended_for": "any",
                "local_path": "/assets/a.png",
                "width": None,
                "height": None,
            }
        )
        await db.add_asset(
            {
                "game_id": "game-x",
                "filename": "b.gif",
                "asset_type": "gif",
                "description": "",
                "recommended_for": "technical",
                "local_path": "/assets/b.gif",
                "width": None,
                "height": None,
            }
        )
        # "technical" フィルタは "any" と "technical" の両方を返す
        technical = await db.get_assets("game-x", recommended_for="technical")
        self.assertEqual(len(technical), 2)
        # "initial" フィルタは "any" のみを返す
        initial = await db.get_assets("game-x", recommended_for="initial")
        self.assertEqual(len(initial), 1)
        self.assertEqual(initial[0]["filename"], "a.png")

    # ---- tweet_drafts テーブル ----

    async def test_add_and_get_draft(self) -> None:
        """下書きを追加してから ID で取得できることを確認する。"""
        await self._add_game()
        draft_id = await db.add_draft(
            {
                "draft_group_id": None,
                "game_id": "game-x",
                "mode": "progress",
                "lang": "ja",
                "content": "テスト下書き",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": "note",
                "asset_reason": None,
                "source_progress_ids": [1, 2],
                "source_appeal_ids": [3],
            }
        )
        draft = await db.get_draft(draft_id)
        self.assertIsNotNone(draft)
        self.assertEqual(draft["content"], "テスト下書き")
        self.assertEqual(draft["status"], "pending")
        self.assertEqual(draft["source_progress_ids"], [1, 2])
        self.assertEqual(draft["source_appeal_ids"], [3])

    async def test_get_draft_missing(self) -> None:
        """存在しない下書き ID に対して None が返されることを確認する。"""
        result = await db.get_draft(99999)
        self.assertIsNone(result)

    async def test_reject_draft_group_by_id(self) -> None:
        """下書き ID で reject_draft_group を呼ぶとステータスが "rejected" になることを確認する。"""
        await self._add_game()
        draft_id = await db.add_draft(
            {
                "draft_group_id": None,
                "game_id": "game-x",
                "mode": "random",
                "lang": "ja",
                "content": "To be rejected",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "asset_reason": None,
                "source_progress_ids": [],
                "source_appeal_ids": [],
            }
        )
        await db.reject_draft_group(None, draft_id=draft_id)
        draft = await db.get_draft(draft_id)
        self.assertEqual(draft["status"], "rejected")

    async def test_reject_draft_group_by_group_id(self) -> None:
        """グループ ID で reject_draft_group を呼ぶとグループ全体が "rejected" になることを確認する。"""
        await self._add_game()
        group_id = db.generate_draft_group_id()
        draft_ja = await db.add_draft(
            {
                "draft_group_id": group_id,
                "game_id": "game-x",
                "mode": "random",
                "lang": "ja",
                "content": "JA",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "asset_reason": None,
                "source_progress_ids": [],
                "source_appeal_ids": [],
            }
        )
        draft_en = await db.add_draft(
            {
                "draft_group_id": group_id,
                "game_id": "game-x",
                "mode": "random",
                "lang": "en",
                "content": "EN",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "asset_reason": None,
                "source_progress_ids": [],
                "source_appeal_ids": [],
            }
        )
        await db.reject_draft_group(group_id)
        ja = await db.get_draft(draft_ja)
        en = await db.get_draft(draft_en)
        self.assertEqual(ja["status"], "rejected")
        self.assertEqual(en["status"], "rejected")

    async def test_get_drafts_by_group_ordered_ja_first(self) -> None:
        """get_drafts_by_group は ja → en の順で返すことを確認する。"""
        await self._add_game()
        group_id = db.generate_draft_group_id()
        # en を先に追加
        await db.add_draft(
            {
                "draft_group_id": group_id,
                "game_id": "game-x",
                "mode": "random",
                "lang": "en",
                "content": "EN first",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "asset_reason": None,
                "source_progress_ids": [],
                "source_appeal_ids": [],
            }
        )
        await db.add_draft(
            {
                "draft_group_id": group_id,
                "game_id": "game-x",
                "mode": "random",
                "lang": "ja",
                "content": "JA second",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "asset_reason": None,
                "source_progress_ids": [],
                "source_appeal_ids": [],
            }
        )
        drafts = await db.get_drafts_by_group(group_id)
        self.assertEqual(len(drafts), 2)
        self.assertEqual(drafts[0]["lang"], "ja")
        self.assertEqual(drafts[1]["lang"], "en")

    async def test_update_draft_message(self) -> None:
        """update_draft_message で discord_msg_id が正しく設定されることを確認する。"""
        await self._add_game()
        draft_id = await db.add_draft(
            {
                "draft_group_id": None,
                "game_id": "game-x",
                "mode": "random",
                "lang": "ja",
                "content": "Draft",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "asset_reason": None,
                "source_progress_ids": [],
                "source_appeal_ids": [],
            }
        )
        await db.update_draft_message(draft_id, "msg-12345")
        draft = await db.get_draft(draft_id)
        self.assertEqual(draft["discord_msg_id"], "msg-12345")

    async def test_get_queue_item_single(self) -> None:
        """"single:ID" 形式の queue_id から正しい下書きが取得できることを確認する。"""
        await self._add_game()
        draft_id = await db.add_draft(
            {
                "draft_group_id": None,
                "game_id": "game-x",
                "mode": "random",
                "lang": "ja",
                "content": "Queue item",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "asset_reason": None,
                "source_progress_ids": [],
                "source_appeal_ids": [],
            }
        )
        result = await db.get_queue_item(f"single:{draft_id}")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], draft_id)

    async def test_get_queue_item_group(self) -> None:
        """グループ形式の queue_id から複数の下書きが取得できることを確認する。"""
        await self._add_game()
        group_id = db.generate_draft_group_id()
        await db.add_draft(
            {
                "draft_group_id": group_id,
                "game_id": "game-x",
                "mode": "random",
                "lang": "ja",
                "content": "JA",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "asset_reason": None,
                "source_progress_ids": [],
                "source_appeal_ids": [],
            }
        )
        await db.add_draft(
            {
                "draft_group_id": group_id,
                "game_id": "game-x",
                "mode": "random",
                "lang": "en",
                "content": "EN",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "asset_reason": None,
                "source_progress_ids": [],
                "source_appeal_ids": [],
            }
        )
        result = await db.get_queue_item(group_id)
        self.assertEqual(len(result), 2)

    # ---- tweets テーブル ----

    async def test_add_and_get_recent_tweets(self) -> None:
        """ツイートを追加してから get_recent_tweets で取得できることを確認する。"""
        import config as cfg
        from datetime import datetime

        await self._add_game()
        now_iso = datetime.now(cfg.JST).isoformat()
        await db.add_tweet(
            {
                "tweet_id": "tweet-001",
                "game_id": "game-x",
                "lang": "ja",
                "content": "Hello world",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "posted_at": now_iso,
                "tweet_url": "https://twitter.com/i/web/status/tweet-001",
                "approved_by": "42",
                "reply_to_tweet_id": None,
            }
        )
        tweets = await db.get_recent_tweets("game-x", days=1)
        self.assertEqual(len(tweets), 1)
        self.assertEqual(tweets[0]["tweet_id"], "tweet-001")

    async def test_update_tweet_analytics(self) -> None:
        """update_tweet_analytics でメトリクスが正しく更新されることを確認する。"""
        import config as cfg
        from datetime import datetime

        await self._add_game()
        now_iso = datetime.now(cfg.JST).isoformat()
        await db.add_tweet(
            {
                "tweet_id": "tweet-002",
                "game_id": "game-x",
                "lang": "ja",
                "content": "Analytics test",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "posted_at": now_iso,
                "tweet_url": "https://twitter.com/i/web/status/tweet-002",
                "approved_by": "1",
                "reply_to_tweet_id": None,
            }
        )
        await db.update_tweet_analytics("tweet-002", impressions=1000, likes=50, retweets=10, replies=5)
        top = await db.get_top_tweets("game-x", limit=1)
        self.assertEqual(len(top), 1)
        self.assertEqual(top[0]["tweet_id"], "tweet-002")
        self.assertEqual(top[0]["impressions"], 1000)
        self.assertEqual(top[0]["likes"], 50)

    async def test_get_top_tweets_empty(self) -> None:
        """アナリティクス付きツイートがない場合に空リストが返されることを確認する。"""
        await self._add_game()
        result = await db.get_top_tweets("game-x")
        self.assertEqual(result, [])

    async def test_get_recent_tweets_for_analytics(self) -> None:
        """get_recent_tweets_for_analytics で直近のツイートが取得できることを確認する。"""
        import config as cfg
        from datetime import datetime

        await self._add_game()
        now_iso = datetime.now(cfg.JST).isoformat()
        await db.add_tweet(
            {
                "tweet_id": "tweet-003",
                "game_id": "game-x",
                "lang": "en",
                "content": "Analytics tweet",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "posted_at": now_iso,
                "tweet_url": "https://twitter.com/i/web/status/tweet-003",
                "approved_by": "1",
                "reply_to_tweet_id": None,
            }
        )
        result = await db.get_recent_tweets_for_analytics("game-x", days=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["tweet_id"], "tweet-003")

    # ---- analytics_summaries テーブル ----

    async def test_save_analytics_summary(self) -> None:
        """アナリティクスサマリーが正常に保存されることを確認する（例外が発生しないことを確認）。"""
        await self._add_game()
        await db.save_analytics_summary(
            "game-x",
            "2026-04",
            {
                "best_time_slot": "20:00",
                "best_tone": "excited",
                "best_asset_type": "gif",
                "next_strategy": "Post more GIFs",
                "avoid_patterns": ["long text"],
            },
        )

    # ---- schedule_slots テーブル ----

    async def test_add_and_list_schedule_slots(self) -> None:
        """スケジュールスロットを追加してからリストで取得できることを確認する。"""
        await db.add_schedule_slot("09:00")
        await db.add_schedule_slot("21:00")
        slots = await db.list_schedule_slots()
        self.assertEqual(len(slots), 2)
        # 昇順であることを確認
        self.assertEqual(slots[0]["slot_time"], "09:00")
        self.assertEqual(slots[1]["slot_time"], "21:00")

    async def test_remove_schedule_slot(self) -> None:
        """スロットを削除するとリストから消えることを確認する。"""
        slot_id = await db.add_schedule_slot("12:00")
        slots_before = await db.list_schedule_slots()
        self.assertEqual(len(slots_before), 1)

        await db.remove_schedule_slot(slot_id)
        slots_after = await db.list_schedule_slots()
        self.assertEqual(slots_after, [])

    async def test_get_slot_by_time_found(self) -> None:
        """登録済みのスロット時刻で get_slot_by_time が正しいスロットを返すことを確認する。"""
        await db.add_schedule_slot("18:30")
        slot = await db.get_slot_by_time("18:30")
        self.assertIsNotNone(slot)
        self.assertEqual(slot["slot_time"], "18:30")

    async def test_get_slot_by_time_not_found(self) -> None:
        """登録されていない時刻に対して None が返されることを確認する。"""
        result = await db.get_slot_by_time("00:00")
        self.assertIsNone(result)

    # ---- consume_draft_sources ----

    async def test_consume_draft_sources(self) -> None:
        """consume_draft_sources が進捗・アピールを正しく消費済みにすることを確認する。"""
        await self._add_game()
        pid = await db.add_progress(
            {
                "game_id": "game-x",
                "log_date": "2026-04-01",
                "milestone": None,
                "content": "Some work",
                "appeal_note": None,
                "excitement": 2,
                "tweetable": 1,
            }
        )
        aid = await db.add_appeal(
            {
                "game_id": "game-x",
                "category": "art",
                "priority": 2,
                "title": "Test",
                "content": "Content",
                "promo_tips": None,
            }
        )
        drafts = [{"source_progress_ids": [pid], "source_appeal_ids": [aid]}]
        await db.consume_draft_sources(drafts)

        # 進捗が tweeted=1 になり未ツイートリストから消えることを確認
        progress = await db.get_recent_progress("game-x")
        self.assertEqual(progress, [])

        # アピールの last_used_at が設定されることを確認
        appeals = await db.get_appeals("game-x")
        self.assertIsNotNone(appeals[0]["last_used_at"])

    async def test_consume_draft_sources_empty(self) -> None:
        """空の下書きリストを渡しても例外が発生しないことを確認する。"""
        await db.consume_draft_sources([])

    # ---- mark_drafts_posted ----

    async def test_mark_drafts_posted(self) -> None:
        """mark_drafts_posted で下書きのステータスが "posted" になることを確認する。"""
        await self._add_game()
        draft_id = await db.add_draft(
            {
                "draft_group_id": None,
                "game_id": "game-x",
                "mode": "random",
                "lang": "ja",
                "content": "Ready to post",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "asset_reason": None,
                "source_progress_ids": [],
                "source_appeal_ids": [],
            }
        )
        await db.approve_draft_group(None, approved_by="1", draft_id=draft_id)
        await db.mark_drafts_posted([draft_id])
        draft = await db.get_draft(draft_id)
        self.assertEqual(draft["status"], "posted")

    async def test_mark_drafts_posted_empty_list(self) -> None:
        """空リストを渡しても例外が発生しないことを確認する。"""
        await db.mark_drafts_posted([])

    # ---- update_draft_group_message ----

    async def test_update_draft_group_message(self) -> None:
        """update_draft_group_message でグループ全体に discord_msg_id が設定されることを確認する。"""
        await self._add_game()
        group_id = db.generate_draft_group_id()
        draft_ja = await db.add_draft(
            {
                "draft_group_id": group_id,
                "game_id": "game-x",
                "mode": "random",
                "lang": "ja",
                "content": "JA",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "asset_reason": None,
                "source_progress_ids": [],
                "source_appeal_ids": [],
            }
        )
        draft_en = await db.add_draft(
            {
                "draft_group_id": group_id,
                "game_id": "game-x",
                "mode": "random",
                "lang": "en",
                "content": "EN",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "asset_reason": None,
                "source_progress_ids": [],
                "source_appeal_ids": [],
            }
        )
        await db.update_draft_group_message(group_id, "grp-msg-99")
        ja = await db.get_draft(draft_ja)
        en = await db.get_draft(draft_en)
        self.assertEqual(ja["discord_msg_id"], "grp-msg-99")
        self.assertEqual(en["discord_msg_id"], "grp-msg-99")

    # ---- list_pending_drafts ----

    async def test_list_pending_drafts_returns_pending_only(self) -> None:
        """list_pending_drafts が pending 状態の下書きのみを返すことを確認する。"""
        await self._add_game()
        draft_pending = await db.add_draft(
            {
                "draft_group_id": None,
                "game_id": "game-x",
                "mode": "random",
                "lang": "ja",
                "content": "Pending content",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "asset_reason": None,
                "source_progress_ids": [],
                "source_appeal_ids": [],
            }
        )
        draft_approved = await db.add_draft(
            {
                "draft_group_id": None,
                "game_id": "game-x",
                "mode": "random",
                "lang": "en",
                "content": "Approved content",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "asset_reason": None,
                "source_progress_ids": [],
                "source_appeal_ids": [],
            }
        )
        await db.approve_draft_group(None, approved_by="1", draft_id=draft_approved)

        pending = await db.list_pending_drafts(game_id="game-x")
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["id"], draft_pending)
        self.assertEqual(pending[0]["status"], "pending")

    async def test_list_pending_drafts_empty(self) -> None:
        """pending 下書きがない場合は空リストが返ることを確認する。"""
        await self._add_game()
        pending = await db.list_pending_drafts(game_id="game-x")
        self.assertEqual(pending, [])

    async def test_list_pending_drafts_all_games(self) -> None:
        """game_id を指定しない場合は全ゲームの pending 下書きが返ることを確認する。"""
        await self._add_game()
        # 別のゲームを追加して 2 件の pending 下書きを作る
        await db.add_game(
            {
                "id": "game-y",
                "name_ja": "Game Y",
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
        for game_id in ("game-x", "game-y"):
            await db.add_draft(
                {
                    "draft_group_id": None,
                    "game_id": game_id,
                    "mode": "random",
                    "lang": "ja",
                    "content": f"Draft for {game_id}",
                    "asset_id": None,
                    "tone": "casual",
                    "strategy_note": None,
                    "asset_reason": None,
                    "source_progress_ids": [],
                    "source_appeal_ids": [],
                }
            )
        pending = await db.list_pending_drafts()
        self.assertEqual(len(pending), 2)

    async def test_list_pending_drafts_excludes_rejected(self) -> None:
        """rejected 状態の下書きが list_pending_drafts に含まれないことを確認する。"""
        await self._add_game()
        draft_id = await db.add_draft(
            {
                "draft_group_id": None,
                "game_id": "game-x",
                "mode": "random",
                "lang": "ja",
                "content": "Will be rejected",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "asset_reason": None,
                "source_progress_ids": [],
                "source_appeal_ids": [],
            }
        )
        await db.reject_draft_group(None, draft_id=draft_id)
        pending = await db.list_pending_drafts(game_id="game-x")
        self.assertEqual(pending, [])

    # ---- tweet_metrics_history テーブル ----

    async def test_update_tweet_analytics_inserts_history(self) -> None:
        """update_tweet_analytics を呼ぶと tweet_metrics_history に履歴が追記されることを確認する。"""
        import config as cfg
        from datetime import datetime

        await self._add_game()
        now_iso = datetime.now(cfg.JST).isoformat()
        await db.add_tweet(
            {
                "tweet_id": "tweet-hist-01",
                "game_id": "game-x",
                "lang": "ja",
                "content": "History test",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "posted_at": now_iso,
                "tweet_url": "https://twitter.com/i/web/status/tweet-hist-01",
                "approved_by": "1",
                "reply_to_tweet_id": None,
            }
        )
        await db.update_tweet_analytics("tweet-hist-01", impressions=100, likes=5, retweets=2, replies=1)
        await db.update_tweet_analytics("tweet-hist-01", impressions=200, likes=10, retweets=4, replies=2)
        history = await db.get_tweet_metrics_history("tweet-hist-01")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["impressions"], 100)
        self.assertEqual(history[1]["impressions"], 200)

    async def test_get_tweet_metrics_history_empty(self) -> None:
        """メトリクス履歴がない tweet_id に対して空リストが返されることを確認する。"""
        result = await db.get_tweet_metrics_history("no-such-tweet")
        self.assertEqual(result, [])

    async def test_get_tweet_metrics_history_ordered_by_fetched_at(self) -> None:
        """get_tweet_metrics_history が fetched_at の昇順で返されることを確認する。"""
        import config as cfg
        from datetime import datetime

        await self._add_game()
        now_iso = datetime.now(cfg.JST).isoformat()
        await db.add_tweet(
            {
                "tweet_id": "tweet-hist-02",
                "game_id": "game-x",
                "lang": "ja",
                "content": "Order test",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "posted_at": now_iso,
                "tweet_url": "https://twitter.com/i/web/status/tweet-hist-02",
                "approved_by": "1",
                "reply_to_tweet_id": None,
            }
        )
        for imp in [50, 150, 300]:
            await db.update_tweet_analytics("tweet-hist-02", impressions=imp, likes=0, retweets=0, replies=0)
        history = await db.get_tweet_metrics_history("tweet-hist-02")
        impressions = [row["impressions"] for row in history]
        self.assertEqual(impressions, [50, 150, 300])

    async def test_insert_tweet_metrics_snapshot_standalone(self) -> None:
        """insert_tweet_metrics_snapshot が tweets テーブルに依存せず動作することを確認する。"""
        await db.insert_tweet_metrics_snapshot("standalone-id", impressions=42, likes=1, retweets=0, replies=0)
        history = await db.get_tweet_metrics_history("standalone-id")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["impressions"], 42)

    # ---- get_all_game_ids ----

    async def test_get_all_game_ids_empty(self) -> None:
        """ゲームが登録されていない場合に空リストが返されることを確認する。"""
        result = await db.get_all_game_ids()
        self.assertEqual(result, [])

    async def test_get_all_game_ids_returns_all(self) -> None:
        """登録されたすべてのゲーム ID が返されることを確認する。"""
        await self._add_game("game-alpha", "Alpha")
        await self._add_game("game-beta", "Beta")
        ids = await db.get_all_game_ids()
        self.assertIn("game-alpha", ids)
        self.assertIn("game-beta", ids)
        self.assertEqual(len(ids), 2)


if __name__ == "__main__":
    unittest.main()
