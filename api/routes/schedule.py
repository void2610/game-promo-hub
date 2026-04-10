from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import config

router = APIRouter()


class SlotCreate(BaseModel):
    slot_time: str  # HH:MM 形式（JST）


class SlotUpdate(BaseModel):
    enabled: int | None = None


_SLOT_UPDATE_COLUMNS = frozenset(SlotUpdate.model_fields.keys())


@router.get("/slots")
async def list_slots() -> list[dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM schedule_slots ORDER BY slot_time ASC"
        ) as cur:
            rows = await cur.fetchall()
    return [dict(row) for row in rows]


@router.post("/slots", status_code=201)
async def create_slot(slot: SlotCreate) -> dict:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO schedule_slots (slot_time) VALUES (?)", (slot.slot_time,)
        )
        await db.commit()
        slot_id = cur.lastrowid
    return await get_slot(slot_id)


@router.get("/slots/{slot_id}")
async def get_slot(slot_id: int) -> dict:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM schedule_slots WHERE id = ?", (slot_id,)
        ) as cur:
            row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Schedule slot not found")
    return dict(row)


@router.patch("/slots/{slot_id}")
async def update_slot(slot_id: int, slot: SlotUpdate) -> dict:
    fields = {
        k: v
        for k, v in slot.model_dump().items()
        if v is not None and k in _SLOT_UPDATE_COLUMNS
    }
    if not fields:
        return await get_slot(slot_id)
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [slot_id]
    async with aiosqlite.connect(config.DB_PATH) as db:
        result = await db.execute(
            f"UPDATE schedule_slots SET {set_clause} WHERE id = ?", values
        )
        await db.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Schedule slot not found")
    return await get_slot(slot_id)


@router.delete("/slots/{slot_id}", status_code=204)
async def delete_slot(slot_id: int) -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        result = await db.execute(
            "DELETE FROM schedule_slots WHERE id = ?", (slot_id,)
        )
        await db.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Schedule slot not found")


@router.get("/queue")
async def get_queue() -> list[dict]:
    """承認済み・投稿待ちの下書きをキュー順に返す。"""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT * FROM tweet_drafts
            WHERE status = 'approved'
            ORDER BY approved_at ASC, created_at ASC
            """
        ) as cur:
            rows = await cur.fetchall()
    return [dict(row) for row in rows]
