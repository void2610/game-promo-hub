from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import config

router = APIRouter()


class AppealCreate(BaseModel):
    game_id: str
    category: str | None = None
    priority: int = 2
    title: str
    content: str
    promo_tips: str | None = None


class AppealUpdate(BaseModel):
    category: str | None = None
    priority: int | None = None
    title: str | None = None
    content: str | None = None
    promo_tips: str | None = None


_APPEAL_UPDATE_COLUMNS = frozenset(AppealUpdate.model_fields.keys())


@router.get("")
async def list_appeals(game_id: str | None = None) -> list[dict]:
    query = "SELECT * FROM appeal_points"
    params: list = []
    if game_id:
        query += " WHERE game_id = ?"
        params.append(game_id)
    query += " ORDER BY priority DESC, last_used_at ASC"
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cur:
            rows = await cur.fetchall()
    return [dict(row) for row in rows]


@router.get("/{appeal_id}")
async def get_appeal(appeal_id: int) -> dict:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM appeal_points WHERE id = ?", (appeal_id,)
        ) as cur:
            row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Appeal point not found")
    return dict(row)


@router.post("", status_code=201)
async def create_appeal(appeal: AppealCreate) -> dict:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO appeal_points (game_id, category, priority, title, content, promo_tips)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (appeal.game_id, appeal.category, appeal.priority, appeal.title,
             appeal.content, appeal.promo_tips),
        )
        await db.commit()
        new_id = cur.lastrowid
    return await get_appeal(new_id)


@router.patch("/{appeal_id}")
async def update_appeal(appeal_id: int, appeal: AppealUpdate) -> dict:
    fields = {
        k: v
        for k, v in appeal.model_dump().items()
        if v is not None and k in _APPEAL_UPDATE_COLUMNS
    }
    if not fields:
        return await get_appeal(appeal_id)
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [appeal_id]
    async with aiosqlite.connect(config.DB_PATH) as db:
        result = await db.execute(
            f"UPDATE appeal_points SET {set_clause} WHERE id = ?", values
        )
        await db.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Appeal point not found")
    return await get_appeal(appeal_id)


@router.delete("/{appeal_id}", status_code=204)
async def delete_appeal(appeal_id: int) -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        result = await db.execute(
            "DELETE FROM appeal_points WHERE id = ?", (appeal_id,)
        )
        await db.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Appeal point not found")
