from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import config
from services import db


class ApproveAndQueueTests(unittest.IsolatedAsyncioTestCase):
    """approve_draft_group・list_approved_queue・pick_next_approved_draft_group の追加テスト。"""

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

    def _draft_data(
        self,
        game_id: str = "game-x",
        lang: str = "ja",
        group_id: str | None = None,
        content: str = "Test",
    ) -> dict:
        return {
            "draft_group_id": group_id,
            "game_id": game_id,
            "mode": "random",
            "lang": lang,
            "content": content,
            "asset_id": None,
            "tone": "casual",
            "strategy_note": None,
            "asset_reason": None,
            "source_progress_ids": [],
            "source_appeal_ids": [],
        }

    # ---- approve_draft_group by group_id ----

    async def test_approve_draft_group_by_group_id_sets_approved(self) -> None:
        """グループ ID で承認するとグループ全体が 'approved' になることを確認する。"""
        await self._add_game()
        group_id = db.generate_draft_group_id()
        id_ja = await db.add_draft(self._draft_data(lang="ja", group_id=group_id, content="JA"))
        id_en = await db.add_draft(self._draft_data(lang="en", group_id=group_id, content="EN"))
        await db.approve_draft_group(group_id, approved_by="user1")
        ja = await db.get_draft(id_ja)
        en = await db.get_draft(id_en)
        self.assertEqual(ja["status"], "approved")
        self.assertEqual(en["status"], "approved")
        self.assertEqual(ja["approved_by"], "user1")

    async def test_approve_draft_group_does_not_approve_already_rejected(self) -> None:
        """rejected 状態の下書きは approve_draft_group では approved にならないことを確認する。"""
        await self._add_game()
        group_id = db.generate_draft_group_id()
        draft_id = await db.add_draft(self._draft_data(group_id=group_id))
        # 先に reject する
        await db.reject_draft_group(group_id)
        # その後 approve しても rejected のまま
        await db.approve_draft_group(group_id, approved_by="user1")
        draft = await db.get_draft(draft_id)
        self.assertEqual(draft["status"], "rejected")

    async def test_approve_draft_group_by_draft_id_sets_approved(self) -> None:
        """単一下書き ID で承認するとそのドラフトが 'approved' になることを確認する。"""
        await self._add_game()
        draft_id = await db.add_draft(self._draft_data())
        await db.approve_draft_group(None, approved_by="user2", draft_id=draft_id)
        draft = await db.get_draft(draft_id)
        self.assertEqual(draft["status"], "approved")
        self.assertEqual(draft["approved_by"], "user2")

    # ---- list_approved_queue ----

    async def test_list_approved_queue_empty(self) -> None:
        """承認済み下書きがない場合に空リストが返されることを確認する。"""
        result = await db.list_approved_queue()
        self.assertEqual(result, [])

    async def test_list_approved_queue_single_draft_format(self) -> None:
        """draft_group_id が NULL の下書きは 'single:ID' 形式の queue_id になることを確認する。"""
        await self._add_game()
        draft_id = await db.add_draft(self._draft_data(group_id=None))
        await db.approve_draft_group(None, approved_by="u1", draft_id=draft_id)
        queue = await db.list_approved_queue()
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["queue_id"], f"single:{draft_id}")
        self.assertEqual(queue[0]["game_id"], "game-x")
        self.assertEqual(queue[0]["draft_count"], 1)

    async def test_list_approved_queue_group_draft_format(self) -> None:
        """グループ下書きは draft_group_id が queue_id になることを確認する。"""
        await self._add_game()
        group_id = db.generate_draft_group_id()
        await db.add_draft(self._draft_data(lang="ja", group_id=group_id))
        await db.add_draft(self._draft_data(lang="en", group_id=group_id))
        await db.approve_draft_group(group_id, approved_by="u1")
        queue = await db.list_approved_queue()
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["queue_id"], group_id)
        self.assertEqual(queue[0]["draft_count"], 2)
        self.assertIn("ja", queue[0]["langs"])
        self.assertIn("en", queue[0]["langs"])

    async def test_list_approved_queue_ordered_oldest_first(self) -> None:
        """承認日時が古い順に返されることを確認する。"""
        await self._add_game()
        id_a = await db.add_draft(self._draft_data(content="A"))
        id_b = await db.add_draft(self._draft_data(content="B"))
        # A を先に承認する
        await db.approve_draft_group(None, approved_by="u1", draft_id=id_a)
        await db.approve_draft_group(None, approved_by="u1", draft_id=id_b)
        queue = await db.list_approved_queue()
        self.assertEqual(len(queue), 2)
        # 先に承認した A の queue_id が先頭にくることを確認
        self.assertIn(str(id_a), queue[0]["queue_id"])

    async def test_list_approved_queue_excludes_pending(self) -> None:
        """pending 状態の下書きは list_approved_queue に含まれないことを確認する。"""
        await self._add_game()
        await db.add_draft(self._draft_data(content="pending draft"))
        queue = await db.list_approved_queue()
        self.assertEqual(queue, [])

    # ---- pick_next_approved_draft_group ----

    async def test_pick_next_approved_draft_group_empty(self) -> None:
        """承認済み下書きがない場合に空リストが返されることを確認する。"""
        result = await db.pick_next_approved_draft_group()
        self.assertEqual(result, [])

    async def test_pick_next_approved_draft_group_single(self) -> None:
        """唯一の承認済み下書きが選ばれることを確認する。"""
        await self._add_game()
        draft_id = await db.add_draft(self._draft_data())
        await db.approve_draft_group(None, approved_by="u1", draft_id=draft_id)
        result = await db.pick_next_approved_draft_group()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], draft_id)

    async def test_pick_next_approved_draft_group_prioritizes_fewer_posts(self) -> None:
        """ツイート投稿数の少ないゲームの下書きが優先して選ばれることを確認する。"""
        await self._add_game("game-a", "Game A")
        await self._add_game("game-b", "Game B")

        # game-a に承認済み下書きを追加
        id_a = await db.add_draft(self._draft_data(game_id="game-a", content="A"))
        await db.approve_draft_group(None, approved_by="u1", draft_id=id_a)

        # game-b に承認済み下書きを追加
        id_b = await db.add_draft(self._draft_data(game_id="game-b", content="B"))
        await db.approve_draft_group(None, approved_by="u1", draft_id=id_b)

        # game-b に先に投稿済みツイートを追加しておく（post_count が多くなる）
        now_iso = datetime.now(config.JST).isoformat()
        await db.add_tweet(
            {
                "tweet_id": "t-b-1",
                "game_id": "game-b",
                "lang": "ja",
                "content": "Posted for game-b",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "posted_at": now_iso,
                "tweet_url": "https://x.com/i/web/status/t-b-1",
                "approved_by": "1",
                "reply_to_tweet_id": None,
            }
        )
        # game-a の方がポスト数が少ないので game-a の下書きが選ばれるはず
        result = await db.pick_next_approved_draft_group()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["game_id"], "game-a")

    async def test_pick_next_approved_draft_group_returns_group(self) -> None:
        """グループ下書きが選ばれた場合は複数の下書きがまとめて返されることを確認する。"""
        await self._add_game()
        group_id = db.generate_draft_group_id()
        await db.add_draft(self._draft_data(lang="ja", group_id=group_id, content="JA"))
        await db.add_draft(self._draft_data(lang="en", group_id=group_id, content="EN"))
        await db.approve_draft_group(group_id, approved_by="u1")
        result = await db.pick_next_approved_draft_group()
        self.assertEqual(len(result), 2)
        langs = {d["lang"] for d in result}
        self.assertIn("ja", langs)
        self.assertIn("en", langs)


class GetRecentTweetsFilterTests(unittest.IsolatedAsyncioTestCase):
    """get_recent_tweets の日数フィルタに関する追加テスト。"""

    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_db = Path(self.temp_dir.name) / "test.db"
        config.DB_PATH = temp_db
        db.DB_PATH = temp_db
        await db.init_db()

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def _add_game(self) -> None:
        await db.add_game(
            {
                "id": "game-x",
                "name_ja": "Game X",
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

    async def test_old_tweet_excluded(self) -> None:
        """days の閾値より古いツイートが get_recent_tweets に含まれないことを確認する。"""
        await self._add_game()
        old_posted_at = (datetime.now(config.JST) - timedelta(days=30)).isoformat()
        await db.add_tweet(
            {
                "tweet_id": "old-tweet",
                "game_id": "game-x",
                "lang": "ja",
                "content": "Old tweet",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "posted_at": old_posted_at,
                "tweet_url": "https://x.com/i/web/status/old-tweet",
                "approved_by": "1",
                "reply_to_tweet_id": None,
            }
        )
        # days=14 で取得すると 30 日前のツイートは含まれない
        result = await db.get_recent_tweets("game-x", days=14)
        self.assertEqual(result, [])

    async def test_recent_tweet_included(self) -> None:
        """days の閾値以内のツイートが get_recent_tweets に含まれることを確認する。"""
        await self._add_game()
        now_iso = datetime.now(config.JST).isoformat()
        await db.add_tweet(
            {
                "tweet_id": "new-tweet",
                "game_id": "game-x",
                "lang": "ja",
                "content": "Recent tweet",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "posted_at": now_iso,
                "tweet_url": "https://x.com/i/web/status/new-tweet",
                "approved_by": "1",
                "reply_to_tweet_id": None,
            }
        )
        result = await db.get_recent_tweets("game-x", days=14)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["tweet_id"], "new-tweet")

    async def test_mixed_tweets_only_recent_returned(self) -> None:
        """古いツイートと新しいツイートが混在する場合、新しいものだけが返されることを確認する。"""
        await self._add_game()
        now_iso = datetime.now(config.JST).isoformat()
        old_posted_at = (datetime.now(config.JST) - timedelta(days=60)).isoformat()
        await db.add_tweet(
            {
                "tweet_id": "t-old",
                "game_id": "game-x",
                "lang": "ja",
                "content": "Old",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "posted_at": old_posted_at,
                "tweet_url": "https://x.com/i/web/status/t-old",
                "approved_by": "1",
                "reply_to_tweet_id": None,
            }
        )
        await db.add_tweet(
            {
                "tweet_id": "t-new",
                "game_id": "game-x",
                "lang": "ja",
                "content": "New",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "posted_at": now_iso,
                "tweet_url": "https://x.com/i/web/status/t-new",
                "approved_by": "1",
                "reply_to_tweet_id": None,
            }
        )
        result = await db.get_recent_tweets("game-x", days=14)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["tweet_id"], "t-new")


class BuildPromoContextEdgeCaseTests(unittest.IsolatedAsyncioTestCase):
    """build_promo_context のエッジケーステスト。"""

    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_db = Path(self.temp_dir.name) / "test.db"
        config.DB_PATH = temp_db
        db.DB_PATH = temp_db
        await db.init_db()

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def test_raises_for_missing_game(self) -> None:
        """存在しないゲーム ID に対して ValueError が送出されることを確認する。"""
        with self.assertRaises(ValueError) as ctx:
            await db.build_promo_context("no-such-game", "random")
        self.assertIn("no-such-game", str(ctx.exception))

    async def test_context_with_no_progress_or_appeals(self) -> None:
        """進捗・アピールポイントが未登録の場合でも PromoContext が生成されることを確認する。"""
        await db.add_game(
            {
                "id": "game-empty",
                "name_ja": "Empty Game",
                "name_en": "Empty Game EN",
                "genre": "puzzle",
                "platform": "itch.io",
                "status": "released",
                "steam_url": None,
                "elevator_ja": "シンプルなゲーム",
                "elevator_en": "Simple game",
                "hashtags": ["#puzzle"],
                "target_audience": ["casual"],
                "circle": "test",
            }
        )
        ctx = await db.build_promo_context("game-empty", "random")
        self.assertIn("Empty Game", ctx.text)
        self.assertEqual(ctx.progress_ids, [])
        self.assertEqual(ctx.appeal_ids, [])

    async def test_context_progress_ids_populated(self) -> None:
        """進捗ログがある場合に progress_ids が正しく設定されることを確認する。"""
        await db.add_game(
            {
                "id": "game-prog",
                "name_ja": "Prog Game",
                "name_en": None,
                "genre": "rpg",
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
        pid = await db.add_progress(
            {
                "game_id": "game-prog",
                "log_date": "2026-04-01",
                "milestone": "alpha",
                "content": "New feature added",
                "appeal_note": "Very cool",
                "excitement": 3,
                "tweetable": 1,
            }
        )
        ctx = await db.build_promo_context("game-prog", "random")
        self.assertIn(pid, ctx.progress_ids)
        self.assertIn("New feature added", ctx.text)

    async def test_context_category_filter_applied(self) -> None:
        """mode に対応するカテゴリフィルタがアピールポイントに適用されることを確認する。"""
        await db.add_game(
            {
                "id": "game-cat",
                "name_ja": "Cat Game",
                "name_en": None,
                "genre": "adventure",
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
        aid_art = await db.add_appeal(
            {
                "game_id": "game-cat",
                "category": "art",
                "priority": 2,
                "title": "Art Appeal",
                "content": "Beautiful art",
                "promo_tips": None,
            }
        )
        await db.add_appeal(
            {
                "game_id": "game-cat",
                "category": "technical",
                "priority": 2,
                "title": "Tech Appeal",
                "content": "Cool tech",
                "promo_tips": None,
            }
        )
        # mode="art" の場合、category="art" のアピールのみが含まれるはず
        ctx = await db.build_promo_context("game-cat", "art")
        self.assertIn(aid_art, ctx.appeal_ids)
        # "random" の場合は category フィルタなし → 両方含まれる可能性がある
        ctx_random = await db.build_promo_context("game-cat", "random")
        self.assertTrue(len(ctx_random.appeal_ids) >= 1)


if __name__ == "__main__":
    unittest.main()
