from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import config

router = APIRouter()


class GameCreate(BaseModel):
    id: str
    name_ja: str
    name_en: str | None = None
    genre: str | None = None
    platform: str = "Steam"
    status: str = "development"
    steam_url: str | None = None
    elevator_ja: str | None = None
    elevator_en: str | None = None
    hashtags: str | None = None
    target_audience: str | None = None
    circle: str | None = None


class GameUpdate(BaseModel):
    name_ja: str | None = None
    name_en: str | None = None
    genre: str | None = None
    platform: str | None = None
    status: str | None = None
    steam_url: str | None = None
    elevator_ja: str | None = None
    elevator_en: str | None = None
    hashtags: str | None = None
    target_audience: str | None = None
    circle: str | None = None


_GAME_UPDATE_COLUMNS = frozenset(GameUpdate.model_fields.keys())


@router.get("")
async def list_games() -> list[dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM games ORDER BY created_at DESC"
        ) as cur:
            rows = await cur.fetchall()
    return [dict(row) for row in rows]


@router.get("/{game_id}")
async def get_game(game_id: str) -> dict:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM games WHERE id = ?", (game_id,)) as cur:
            row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return dict(row)


@router.post("", status_code=201)
async def create_game(game: GameCreate) -> dict:
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO games (id, name_ja, name_en, genre, platform, status,
                               steam_url, elevator_ja, elevator_en, hashtags,
                               target_audience, circle)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                game.id, game.name_ja, game.name_en, game.genre, game.platform,
                game.status, game.steam_url, game.elevator_ja, game.elevator_en,
                game.hashtags, game.target_audience, game.circle,
            ),
        )
        await db.commit()
    return await get_game(game.id)


@router.patch("/{game_id}")
async def update_game(game_id: str, game: GameUpdate) -> dict:
    fields = {
        k: v
        for k, v in game.model_dump().items()
        if v is not None and k in _GAME_UPDATE_COLUMNS
    }
    if not fields:
        return await get_game(game_id)
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [game_id]
    async with aiosqlite.connect(config.DB_PATH) as db:
        result = await db.execute(
            f"UPDATE games SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            values,
        )
        await db.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Game not found")
    return await get_game(game_id)


@router.delete("/{game_id}", status_code=204)
async def delete_game(game_id: str) -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        result = await db.execute("DELETE FROM games WHERE id = ?", (game_id,))
        await db.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Game not found")
