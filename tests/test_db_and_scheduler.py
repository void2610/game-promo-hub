from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import config
from services import db, scheduler


class DatabaseAndSchedulerTests(unittest.IsolatedAsyncioTestCase):
    """DB 操作とスケジューラの統合テスト。各テストは一時 DB を使い独立して実行される。"""

    async def asyncSetUp(self) -> None:
        """テストごとに一時ディレクトリと空の DB を作成する。"""
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_db = Path(self.temp_dir.name) / "test.db"
        config.DB_PATH = temp_db
        db.DB_PATH = temp_db
        # スケジューラのスロット重複防止キーをリセット
        scheduler._last_slot_key = None
        await db.init_db()

    async def asyncTearDown(self) -> None:
        """テスト後に一時ディレクトリを削除する。"""
        self.temp_dir.cleanup()

    async def _add_game(self, game_id: str, name: str) -> None:
        """テスト用ゲームを DB に追加するヘルパー。"""
        await db.add_game(
            {
                "id": game_id,
                "name_ja": name,
                "name_en": None,
                "genre": "action",
                "platform": "Steam",
                "status": "development",
                "steam_url": None,
                "elevator_ja": None,
                "elevator_en": None,
                "hashtags": ["#indiegame"],
                "target_audience": ["indie fans"],
                "circle": "test",
            }
        )

    async def test_build_promo_context_and_draft_queue(self) -> None:
        """プロモコンテキスト生成・下書き追加・承認・キュー確認の一連フローをテストする。"""
        await self._add_game("game-a", "Game A")
        progress_id = await db.add_progress(
            {
                "game_id": "game-a",
                "log_date": "2026-04-09",
                "milestone": "demo",
                "content": "New boss battle implemented",
                "appeal_note": "Focus on combat feel",
                "excitement": 3,
                "tweetable": 1,
            }
        )
        appeal_id = await db.add_appeal(
            {
                "game_id": "game-a",
                "category": "technical",
                "priority": 3,
                "title": "ShaderGraph bloom",
                "content": "Custom glow pass",
                "promo_tips": "Mention the pipeline work",
            }
        )
        # コンテキストにゲーム名・進捗・アピール ID が含まれることを確認
        context = await db.build_promo_context("game-a", "technical")
        self.assertIn("Game A", context.text)
        self.assertEqual(context.progress_ids, [progress_id])
        self.assertEqual(context.appeal_ids, [appeal_id])

        # ja/en ペアの下書きをグループとして追加
        group_id = db.generate_draft_group_id()
        draft_ja = await db.add_draft(
            {
                "draft_group_id": group_id,
                "game_id": "game-a",
                "mode": "technical",
                "lang": "ja",
                "content": "日本語本文",
                "asset_id": None,
                "tone": "technical",
                "strategy_note": "note",
                "asset_reason": None,
                "source_progress_ids": [progress_id],
                "source_appeal_ids": [appeal_id],
            }
        )
        draft_en = await db.add_draft(
            {
                "draft_group_id": group_id,
                "game_id": "game-a",
                "mode": "technical",
                "lang": "en",
                "content": "English body",
                "asset_id": None,
                "tone": "technical",
                "strategy_note": "note",
                "asset_reason": None,
                "source_progress_ids": [progress_id],
                "source_appeal_ids": [appeal_id],
            }
        )

        # 承認後にキューへ正しく追加されることを確認
        await db.approve_draft_group(group_id, approved_by="123")
        queue = await db.list_approved_queue()
        self.assertEqual(queue[0]["queue_id"], group_id)
        self.assertEqual(sorted(queue[0]["draft_ids"]), sorted([draft_ja, draft_en]))

    async def test_pick_next_group_prefers_less_posted_game(self) -> None:
        """投稿数の少ないゲームの下書きが優先して選ばれることを確認する。"""
        await self._add_game("game-a", "Game A")
        await self._add_game("game-b", "Game B")

        draft_a = await db.add_draft(
            {
                "draft_group_id": None,
                "game_id": "game-a",
                "mode": "random",
                "lang": "ja",
                "content": "A",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "asset_reason": None,
                "source_progress_ids": [],
                "source_appeal_ids": [],
            }
        )
        draft_b = await db.add_draft(
            {
                "draft_group_id": None,
                "game_id": "game-b",
                "mode": "random",
                "lang": "ja",
                "content": "B",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "asset_reason": None,
                "source_progress_ids": [],
                "source_appeal_ids": [],
            }
        )
        await db.approve_draft_group(None, approved_by="1", draft_id=draft_a)
        await db.approve_draft_group(None, approved_by="1", draft_id=draft_b)

        # game-a に既存の投稿を追加して投稿数を増やす
        await db.add_tweet(
            {
                "tweet_id": "100",
                "game_id": "game-a",
                "lang": "ja",
                "content": "existing",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "posted_at": datetime.now(config.JST).isoformat(),
                "tweet_url": "https://example.com/100",
                "approved_by": "1",
                "reply_to_tweet_id": None,
            }
        )

        # 投稿数の少ない game-b が選ばれることを確認
        picked = await db.pick_next_approved_draft_group()
        self.assertEqual(picked[0]["game_id"], "game-b")

    async def test_scheduler_dispatch_posts_and_consumes_sources(self) -> None:
        """スケジューラが投稿を実行し、ソースの進捗・アピールを消費済みにすることを確認する。"""
        await self._add_game("game-a", "Game A")
        progress_id = await db.add_progress(
            {
                "game_id": "game-a",
                "log_date": "2026-04-09",
                "milestone": None,
                "content": "Implemented a new room",
                "appeal_note": None,
                "excitement": 2,
                "tweetable": 1,
            }
        )
        appeal_id = await db.add_appeal(
            {
                "game_id": "game-a",
                "category": "art",
                "priority": 2,
                "title": "Palette",
                "content": "Warm color grade",
                "promo_tips": None,
            }
        )
        draft_id = await db.add_draft(
            {
                "draft_group_id": None,
                "game_id": "game-a",
                "mode": "random",
                "lang": "ja",
                "content": "Scheduled post",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": "note",
                "asset_reason": None,
                "source_progress_ids": [progress_id],
                "source_appeal_ids": [appeal_id],
            }
        )
        await db.approve_draft_group(None, approved_by="42", draft_id=draft_id)
        # 現在時刻のスロットを登録してスケジューラが発火するようにする
        await db.add_schedule_slot(datetime.now(config.JST).strftime("%H:%M"))

        async def fake_post_tweet(content, media_path=None, game_id=None, reply_to_tweet_id=None):
            """Twitter への実投稿をスキップするダミー関数。"""
            return "999", "https://twitter.com/i/web/status/999"

        original = scheduler.twitter.post_tweet
        scheduler.twitter.post_tweet = fake_post_tweet
        try:
            posted = await scheduler.dispatch_scheduled_posts(object())
        finally:
            scheduler.twitter.post_tweet = original

        # 投稿後の状態を検証
        self.assertTrue(posted)
        draft = await db.get_draft(draft_id)
        self.assertEqual(draft["status"], "posted")
        recent = await db.get_recent_tweets("game-a", days=1)
        self.assertEqual(len(recent), 1)
        # ソースの進捗ログが tweeted=1 になって未ツイートリストから消えていることを確認
        progress = await db.get_recent_progress("game-a", limit=5)
        self.assertEqual(progress, [])


if __name__ == "__main__":
    unittest.main()
