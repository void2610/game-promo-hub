from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import httpx
from httpx import ASGITransport

import config
from api.app import app
from services import db


def _make_transport() -> ASGITransport:
    return ASGITransport(app=app)  # type: ignore[arg-type]


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=_make_transport(), base_url="http://test")


# ---------------------------------------------------------------------------
# 共通ヘルパー
# ---------------------------------------------------------------------------

_GAME_PAYLOAD = {
    "id": "game-api-test",
    "name_ja": "APIテストゲーム",
    "name_en": "API Test Game",
    "genre": "action",
    "platform": "Steam",
    "status": "development",
    "steam_url": None,
    "elevator_ja": "面白いゲーム",
    "elevator_en": "A great game",
    "hashtags": None,
    "target_audience": None,
    "circle": "test-circle",
}


class HealthEndpointTests(unittest.IsolatedAsyncioTestCase):
    """GET /health のテスト。"""

    async def test_health_returns_ok(self) -> None:
        """GET /health が {"status": "ok"} を返すことを確認する。"""
        async with await _client() as client:
            resp = await client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok"})


# ---------------------------------------------------------------------------
# /v1/games
# ---------------------------------------------------------------------------

class GamesApiTests(unittest.IsolatedAsyncioTestCase):
    """Games CRUD エンドポイントのテスト。"""

    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_db = Path(self.temp_dir.name) / "test.db"
        config.DB_PATH = temp_db
        db.DB_PATH = temp_db
        await db.init_db()
        self.client = await _client()

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        self.temp_dir.cleanup()

    async def test_list_games_empty(self) -> None:
        """ゲームがない場合は空リストが返されることを確認する。"""
        resp = await self.client.get("/v1/games")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    async def test_create_game(self) -> None:
        """POST /v1/games でゲームを作成できることを確認する。"""
        resp = await self.client.post("/v1/games", json=_GAME_PAYLOAD)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["id"], "game-api-test")
        self.assertEqual(data["name_ja"], "APIテストゲーム")

    async def test_list_games_after_create(self) -> None:
        """ゲームを作成後に GET /v1/games で取得できることを確認する。"""
        await self.client.post("/v1/games", json=_GAME_PAYLOAD)
        resp = await self.client.get("/v1/games")
        self.assertEqual(resp.status_code, 200)
        games = resp.json()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["id"], "game-api-test")

    async def test_get_game_by_id(self) -> None:
        """GET /v1/games/{id} でゲームを取得できることを確認する。"""
        await self.client.post("/v1/games", json=_GAME_PAYLOAD)
        resp = await self.client.get("/v1/games/game-api-test")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["name_en"], "API Test Game")

    async def test_get_game_not_found(self) -> None:
        """存在しないゲーム ID に対して 404 が返されることを確認する。"""
        resp = await self.client.get("/v1/games/no-such-game")
        self.assertEqual(resp.status_code, 404)

    async def test_update_game(self) -> None:
        """PATCH /v1/games/{id} でゲーム情報を更新できることを確認する。"""
        await self.client.post("/v1/games", json=_GAME_PAYLOAD)
        resp = await self.client.patch(
            "/v1/games/game-api-test",
            json={"name_ja": "更新済みゲーム", "status": "released"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["name_ja"], "更新済みゲーム")
        self.assertEqual(data["status"], "released")

    async def test_update_game_not_found(self) -> None:
        """存在しないゲームを PATCH すると 404 が返されることを確認する。"""
        resp = await self.client.patch("/v1/games/ghost", json={"status": "released"})
        self.assertEqual(resp.status_code, 404)

    async def test_update_game_no_fields(self) -> None:
        """フィールドなし（全 None）の PATCH はそのままゲーム情報を返すことを確認する。"""
        await self.client.post("/v1/games", json=_GAME_PAYLOAD)
        resp = await self.client.patch("/v1/games/game-api-test", json={})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], "game-api-test")

    async def test_delete_game(self) -> None:
        """DELETE /v1/games/{id} でゲームを削除できることを確認する。"""
        await self.client.post("/v1/games", json=_GAME_PAYLOAD)
        resp = await self.client.delete("/v1/games/game-api-test")
        self.assertEqual(resp.status_code, 204)
        # 削除後は 404
        resp2 = await self.client.get("/v1/games/game-api-test")
        self.assertEqual(resp2.status_code, 404)

    async def test_delete_game_not_found(self) -> None:
        """存在しないゲームを DELETE すると 404 が返されることを確認する。"""
        resp = await self.client.delete("/v1/games/ghost")
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# /v1/progress
# ---------------------------------------------------------------------------

class ProgressApiTests(unittest.IsolatedAsyncioTestCase):
    """Progress CRUD エンドポイントのテスト。"""

    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_db = Path(self.temp_dir.name) / "test.db"
        config.DB_PATH = temp_db
        db.DB_PATH = temp_db
        await db.init_db()
        self.client = await _client()
        # ゲームを事前登録
        await self.client.post("/v1/games", json=_GAME_PAYLOAD)

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        self.temp_dir.cleanup()

    def _progress_payload(self, content: str = "進捗メモ") -> dict:
        return {
            "game_id": "game-api-test",
            "log_date": "2026-04-10",
            "milestone": "alpha",
            "content": content,
            "appeal_note": None,
            "excitement": 3,
            "tweetable": 1,
        }

    async def test_list_progress_empty(self) -> None:
        """進捗ログがない場合に空リストが返されることを確認する。"""
        resp = await self.client.get("/v1/progress")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    async def test_create_progress(self) -> None:
        """POST /v1/progress で進捗ログを作成できることを確認する。"""
        resp = await self.client.post("/v1/progress", json=self._progress_payload())
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["content"], "進捗メモ")
        self.assertEqual(data["game_id"], "game-api-test")

    async def test_get_progress_by_id(self) -> None:
        """GET /v1/progress/{id} で進捗ログを取得できることを確認する。"""
        create_resp = await self.client.post("/v1/progress", json=self._progress_payload())
        progress_id = create_resp.json()["id"]
        resp = await self.client.get(f"/v1/progress/{progress_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], progress_id)

    async def test_get_progress_not_found(self) -> None:
        """存在しない進捗 ID に対して 404 が返されることを確認する。"""
        resp = await self.client.get("/v1/progress/9999")
        self.assertEqual(resp.status_code, 404)

    async def test_list_progress_filter_by_game_id(self) -> None:
        """game_id クエリパラメータでフィルタできることを確認する。"""
        await self.client.post("/v1/progress", json=self._progress_payload("メモ1"))
        resp = await self.client.get("/v1/progress?game_id=game-api-test")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    async def test_update_progress(self) -> None:
        """PATCH /v1/progress/{id} で進捗ログを更新できることを確認する。"""
        create_resp = await self.client.post("/v1/progress", json=self._progress_payload())
        progress_id = create_resp.json()["id"]
        resp = await self.client.patch(
            f"/v1/progress/{progress_id}",
            json={"content": "更新済み内容", "excitement": 5},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["content"], "更新済み内容")
        self.assertEqual(resp.json()["excitement"], 5)

    async def test_update_progress_not_found(self) -> None:
        """存在しない進捗 ID を PATCH すると 404 が返されることを確認する。"""
        resp = await self.client.patch("/v1/progress/9999", json={"content": "x"})
        self.assertEqual(resp.status_code, 404)

    async def test_delete_progress(self) -> None:
        """DELETE /v1/progress/{id} で進捗ログを削除できることを確認する。"""
        create_resp = await self.client.post("/v1/progress", json=self._progress_payload())
        progress_id = create_resp.json()["id"]
        resp = await self.client.delete(f"/v1/progress/{progress_id}")
        self.assertEqual(resp.status_code, 204)
        # 削除後は 404
        resp2 = await self.client.get(f"/v1/progress/{progress_id}")
        self.assertEqual(resp2.status_code, 404)

    async def test_delete_progress_not_found(self) -> None:
        """存在しない進捗 ID を DELETE すると 404 が返されることを確認する。"""
        resp = await self.client.delete("/v1/progress/9999")
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# /v1/appeals
# ---------------------------------------------------------------------------

class AppealsApiTests(unittest.IsolatedAsyncioTestCase):
    """Appeals CRUD エンドポイントのテスト。"""

    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_db = Path(self.temp_dir.name) / "test.db"
        config.DB_PATH = temp_db
        db.DB_PATH = temp_db
        await db.init_db()
        self.client = await _client()
        await self.client.post("/v1/games", json=_GAME_PAYLOAD)

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        self.temp_dir.cleanup()

    def _appeal_payload(self, title: str = "ビジュアルの魅力") -> dict:
        return {
            "game_id": "game-api-test",
            "category": "art",
            "priority": 3,
            "title": title,
            "content": "手描きスプライトが美しい",
            "promo_tips": "GIF を使う",
        }

    async def test_list_appeals_empty(self) -> None:
        """アピールポイントがない場合に空リストが返されることを確認する。"""
        resp = await self.client.get("/v1/appeals")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    async def test_create_appeal(self) -> None:
        """POST /v1/appeals でアピールポイントを作成できることを確認する。"""
        resp = await self.client.post("/v1/appeals", json=self._appeal_payload())
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["title"], "ビジュアルの魅力")
        self.assertEqual(data["category"], "art")

    async def test_get_appeal_by_id(self) -> None:
        """GET /v1/appeals/{id} でアピールポイントを取得できることを確認する。"""
        create_resp = await self.client.post("/v1/appeals", json=self._appeal_payload())
        appeal_id = create_resp.json()["id"]
        resp = await self.client.get(f"/v1/appeals/{appeal_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], appeal_id)

    async def test_get_appeal_not_found(self) -> None:
        """存在しないアピール ID に対して 404 が返されることを確認する。"""
        resp = await self.client.get("/v1/appeals/9999")
        self.assertEqual(resp.status_code, 404)

    async def test_list_appeals_filter_by_game_id(self) -> None:
        """game_id クエリパラメータでフィルタできることを確認する。"""
        await self.client.post("/v1/appeals", json=self._appeal_payload())
        resp = await self.client.get("/v1/appeals?game_id=game-api-test")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    async def test_update_appeal(self) -> None:
        """PATCH /v1/appeals/{id} でアピールポイントを更新できることを確認する。"""
        create_resp = await self.client.post("/v1/appeals", json=self._appeal_payload())
        appeal_id = create_resp.json()["id"]
        resp = await self.client.patch(
            f"/v1/appeals/{appeal_id}",
            json={"title": "更新済みタイトル", "priority": 5},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["title"], "更新済みタイトル")
        self.assertEqual(resp.json()["priority"], 5)

    async def test_update_appeal_not_found(self) -> None:
        """存在しないアピール ID を PATCH すると 404 が返されることを確認する。"""
        resp = await self.client.patch("/v1/appeals/9999", json={"title": "x"})
        self.assertEqual(resp.status_code, 404)

    async def test_delete_appeal(self) -> None:
        """DELETE /v1/appeals/{id} でアピールポイントを削除できることを確認する。"""
        create_resp = await self.client.post("/v1/appeals", json=self._appeal_payload())
        appeal_id = create_resp.json()["id"]
        resp = await self.client.delete(f"/v1/appeals/{appeal_id}")
        self.assertEqual(resp.status_code, 204)
        resp2 = await self.client.get(f"/v1/appeals/{appeal_id}")
        self.assertEqual(resp2.status_code, 404)

    async def test_delete_appeal_not_found(self) -> None:
        """存在しないアピール ID を DELETE すると 404 が返されることを確認する。"""
        resp = await self.client.delete("/v1/appeals/9999")
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# /v1/drafts
# ---------------------------------------------------------------------------

class DraftsApiTests(unittest.IsolatedAsyncioTestCase):
    """Drafts CRUD エンドポイントのテスト。"""

    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_db = Path(self.temp_dir.name) / "test.db"
        config.DB_PATH = temp_db
        db.DB_PATH = temp_db
        await db.init_db()
        self.client = await _client()
        await self.client.post("/v1/games", json=_GAME_PAYLOAD)
        # DB 経由でドラフトを作成（drafts はサービス経由で作られる想定のため）
        self._draft_id = await db.add_draft(
            {
                "draft_group_id": None,
                "game_id": "game-api-test",
                "mode": "random",
                "lang": "ja",
                "content": "テストツイート内容",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "asset_reason": None,
                "source_progress_ids": [],
                "source_appeal_ids": [],
            }
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        self.temp_dir.cleanup()

    async def test_list_drafts(self) -> None:
        """GET /v1/drafts でドラフト一覧を取得できることを確認する。"""
        resp = await self.client.get("/v1/drafts")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    async def test_list_drafts_filter_by_status(self) -> None:
        """status クエリパラメータでフィルタできることを確認する。"""
        resp = await self.client.get("/v1/drafts?status=pending")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    async def test_list_drafts_filter_by_game_id(self) -> None:
        """game_id クエリパラメータでフィルタできることを確認する。"""
        resp = await self.client.get("/v1/drafts?game_id=game-api-test")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    async def test_list_drafts_filter_no_match(self) -> None:
        """一致しないフィルタで空リストが返されることを確認する。"""
        resp = await self.client.get("/v1/drafts?status=approved")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    async def test_get_draft_by_id(self) -> None:
        """GET /v1/drafts/{id} でドラフトを取得できることを確認する。"""
        resp = await self.client.get(f"/v1/drafts/{self._draft_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], self._draft_id)
        self.assertEqual(resp.json()["content"], "テストツイート内容")

    async def test_get_draft_not_found(self) -> None:
        """存在しないドラフト ID に対して 404 が返されることを確認する。"""
        resp = await self.client.get("/v1/drafts/9999")
        self.assertEqual(resp.status_code, 404)

    async def test_update_draft_content(self) -> None:
        """PATCH /v1/drafts/{id} でドラフトの内容を更新できることを確認する。"""
        resp = await self.client.patch(
            f"/v1/drafts/{self._draft_id}",
            json={"content": "更新済みツイート"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["content"], "更新済みツイート")

    async def test_update_draft_status_approved(self) -> None:
        """PATCH でステータスを approved にすると approved_at が設定されることを確認する。"""
        resp = await self.client.patch(
            f"/v1/drafts/{self._draft_id}",
            json={"status": "approved"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "approved")
        self.assertIsNotNone(data.get("approved_at"))

    async def test_update_draft_not_found(self) -> None:
        """存在しないドラフト ID を PATCH すると 404 が返されることを確認する。"""
        resp = await self.client.patch("/v1/drafts/9999", json={"content": "x"})
        self.assertEqual(resp.status_code, 404)

    async def test_update_draft_no_fields(self) -> None:
        """フィールドなしの PATCH はそのままドラフトを返すことを確認する。"""
        resp = await self.client.patch(f"/v1/drafts/{self._draft_id}", json={})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], self._draft_id)

    async def test_delete_draft(self) -> None:
        """DELETE /v1/drafts/{id} でドラフトを削除できることを確認する。"""
        resp = await self.client.delete(f"/v1/drafts/{self._draft_id}")
        self.assertEqual(resp.status_code, 204)
        resp2 = await self.client.get(f"/v1/drafts/{self._draft_id}")
        self.assertEqual(resp2.status_code, 404)

    async def test_delete_draft_not_found(self) -> None:
        """存在しないドラフト ID を DELETE すると 404 が返されることを確認する。"""
        resp = await self.client.delete("/v1/drafts/9999")
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# /v1/schedule
# ---------------------------------------------------------------------------

class ScheduleApiTests(unittest.IsolatedAsyncioTestCase):
    """Schedule スロット CRUD エンドポイントのテスト。"""

    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_db = Path(self.temp_dir.name) / "test.db"
        config.DB_PATH = temp_db
        db.DB_PATH = temp_db
        await db.init_db()
        self.client = await _client()

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        self.temp_dir.cleanup()

    async def test_list_slots_empty(self) -> None:
        """スロットがない場合に空リストが返されることを確認する。"""
        resp = await self.client.get("/v1/schedule/slots")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    async def test_create_slot(self) -> None:
        """POST /v1/schedule/slots でスロットを作成できることを確認する。"""
        resp = await self.client.post(
            "/v1/schedule/slots", json={"slot_time": "09:00"}
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["slot_time"], "09:00")

    async def test_get_slot_by_id(self) -> None:
        """GET /v1/schedule/slots/{id} でスロットを取得できることを確認する。"""
        create_resp = await self.client.post(
            "/v1/schedule/slots", json={"slot_time": "12:00"}
        )
        slot_id = create_resp.json()["id"]
        resp = await self.client.get(f"/v1/schedule/slots/{slot_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["slot_time"], "12:00")

    async def test_get_slot_not_found(self) -> None:
        """存在しないスロット ID に対して 404 が返されることを確認する。"""
        resp = await self.client.get("/v1/schedule/slots/9999")
        self.assertEqual(resp.status_code, 404)

    async def test_update_slot_enabled(self) -> None:
        """PATCH /v1/schedule/slots/{id} でスロットを無効化できることを確認する。"""
        create_resp = await self.client.post(
            "/v1/schedule/slots", json={"slot_time": "21:00"}
        )
        slot_id = create_resp.json()["id"]
        resp = await self.client.patch(
            f"/v1/schedule/slots/{slot_id}", json={"enabled": 0}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["enabled"], 0)

    async def test_update_slot_no_fields(self) -> None:
        """フィールドなしの PATCH はそのままスロットを返すことを確認する。"""
        create_resp = await self.client.post(
            "/v1/schedule/slots", json={"slot_time": "22:00"}
        )
        slot_id = create_resp.json()["id"]
        resp = await self.client.patch(f"/v1/schedule/slots/{slot_id}", json={})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["slot_time"], "22:00")

    async def test_update_slot_not_found(self) -> None:
        """存在しないスロット ID を PATCH すると 404 が返されることを確認する。"""
        resp = await self.client.patch("/v1/schedule/slots/9999", json={"enabled": 1})
        self.assertEqual(resp.status_code, 404)

    async def test_delete_slot(self) -> None:
        """DELETE /v1/schedule/slots/{id} でスロットを削除できることを確認する。"""
        create_resp = await self.client.post(
            "/v1/schedule/slots", json={"slot_time": "23:00"}
        )
        slot_id = create_resp.json()["id"]
        resp = await self.client.delete(f"/v1/schedule/slots/{slot_id}")
        self.assertEqual(resp.status_code, 204)
        resp2 = await self.client.get(f"/v1/schedule/slots/{slot_id}")
        self.assertEqual(resp2.status_code, 404)

    async def test_delete_slot_not_found(self) -> None:
        """存在しないスロット ID を DELETE すると 404 が返されることを確認する。"""
        resp = await self.client.delete("/v1/schedule/slots/9999")
        self.assertEqual(resp.status_code, 404)

    async def test_get_queue_empty(self) -> None:
        """承認済み下書きがない場合に GET /v1/schedule/queue が空リストを返すことを確認する。"""
        resp = await self.client.get("/v1/schedule/queue")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    async def test_get_queue_with_approved_draft(self) -> None:
        """承認済みドラフトが GET /v1/schedule/queue に含まれることを確認する。"""
        await self.client.post("/v1/games", json=_GAME_PAYLOAD)
        draft_id = await db.add_draft(
            {
                "draft_group_id": None,
                "game_id": "game-api-test",
                "mode": "random",
                "lang": "ja",
                "content": "承認済みツイート",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "asset_reason": None,
                "source_progress_ids": [],
                "source_appeal_ids": [],
            }
        )
        await db.approve_draft_group(None, approved_by="u1", draft_id=draft_id)
        resp = await self.client.get("/v1/schedule/queue")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)
        self.assertEqual(resp.json()[0]["status"], "approved")


# ---------------------------------------------------------------------------
# /v1/analytics
# ---------------------------------------------------------------------------

class AnalyticsApiTests(unittest.IsolatedAsyncioTestCase):
    """Analytics read エンドポイントのテスト。"""

    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_db = Path(self.temp_dir.name) / "test.db"
        config.DB_PATH = temp_db
        db.DB_PATH = temp_db
        await db.init_db()
        self.client = await _client()
        await self.client.post("/v1/games", json=_GAME_PAYLOAD)

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        self.temp_dir.cleanup()

    async def test_list_tweets_empty(self) -> None:
        """ツイートがない場合に GET /v1/analytics/tweets が空リストを返すことを確認する。"""
        resp = await self.client.get("/v1/analytics/tweets")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    async def test_list_tweets_with_data(self) -> None:
        """ツイートを登録後に GET /v1/analytics/tweets で取得できることを確認する。"""
        from datetime import datetime

        now_iso = datetime.now(config.JST).isoformat()
        await db.add_tweet(
            {
                "tweet_id": "tw-api-test",
                "game_id": "game-api-test",
                "lang": "ja",
                "content": "テストツイート",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "posted_at": now_iso,
                "tweet_url": "https://x.com/i/web/status/tw-api-test",
                "approved_by": "1",
                "reply_to_tweet_id": None,
            }
        )
        resp = await self.client.get("/v1/analytics/tweets")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)
        self.assertEqual(resp.json()[0]["tweet_id"], "tw-api-test")

    async def test_list_tweets_filter_by_game_id(self) -> None:
        """game_id クエリパラメータでツイートをフィルタできることを確認する。"""
        from datetime import datetime

        now_iso = datetime.now(config.JST).isoformat()
        await db.add_tweet(
            {
                "tweet_id": "tw-filter-test",
                "game_id": "game-api-test",
                "lang": "ja",
                "content": "フィルタテスト",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "posted_at": now_iso,
                "tweet_url": "https://x.com/i/web/status/tw-filter-test",
                "approved_by": "1",
                "reply_to_tweet_id": None,
            }
        )
        resp = await self.client.get("/v1/analytics/tweets?game_id=game-api-test")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    async def test_list_summaries_empty(self) -> None:
        """サマリーがない場合に GET /v1/analytics/summaries が空リストを返すことを確認する。"""
        resp = await self.client.get("/v1/analytics/summaries")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    async def test_list_summaries_with_data(self) -> None:
        """サマリーを登録後に GET /v1/analytics/summaries で取得できることを確認する。"""
        await db.save_analytics_summary(
            "game-api-test",
            "weekly",
            {"top_tweets": [], "advice": "test advice"},
        )
        resp = await self.client.get("/v1/analytics/summaries")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    async def test_list_metrics_history_empty(self) -> None:
        """メトリクス履歴がない場合に空リストが返されることを確認する。"""
        resp = await self.client.get("/v1/analytics/metrics/history")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    async def test_list_metrics_history_filter_by_tweet_id(self) -> None:
        """tweet_id クエリパラメータでメトリクス履歴をフィルタできることを確認する。"""
        from datetime import datetime

        now_iso = datetime.now(config.JST).isoformat()
        await db.add_tweet(
            {
                "tweet_id": "tw-hist",
                "game_id": "game-api-test",
                "lang": "ja",
                "content": "履歴テスト",
                "asset_id": None,
                "tone": "casual",
                "strategy_note": None,
                "posted_at": now_iso,
                "tweet_url": "https://x.com/i/web/status/tw-hist",
                "approved_by": "1",
                "reply_to_tweet_id": None,
            }
        )
        await db.insert_tweet_metrics_snapshot("tw-hist", 100, 10, 2, 1)
        resp = await self.client.get("/v1/analytics/metrics/history?tweet_id=tw-hist")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)
        self.assertEqual(resp.json()[0]["impressions"], 100)


if __name__ == "__main__":
    unittest.main()
