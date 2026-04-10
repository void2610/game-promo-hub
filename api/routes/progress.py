from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import config

router = APIRouter()


class ProgressCreate(BaseModel):
    game_id: str
    log_date: str
    milestone: str | None = None
    content: str
    appeal_note: str | None = None
    excitement: int = 2
    tweetable: int = 1


class ProgressUpdate(BaseModel):
    milestone: str | None = None
    content: str | None = None
    appeal_note: str | None = None
    excitement: int | None = None
    tweetable: int | None = None
    tweeted: int | None = None


_PROGRESS_UPDATE_COLUMNS = frozenset(ProgressUpdate.model_fields.keys())


@router.get("")
async def list_progress(game_id: str | None = None) -> list[dict]:
    query = "SELECT * FROM progress_logs"
    params: list = []
    if game_id:
        query += " WHERE game_id = ?"
        params.append(game_id)
    query += " ORDER BY log_date DESC, created_at DESC"
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cur:
            rows = await cur.fetchall()
    return [dict(row) for row in rows]


@router.get("/{progress_id}")
async def get_progress(progress_id: int) -> dict:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM progress_logs WHERE id = ?", (progress_id,)
        ) as cur:
            row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Progress log not found")
    return dict(row)


@router.post("", status_code=201)
async def create_progress(progress: ProgressCreate) -> dict:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO progress_logs (game_id, log_date, milestone, content,
                                       appeal_note, excitement, tweetable)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                progress.game_id, progress.log_date, progress.milestone,
                progress.content, progress.appeal_note, progress.excitement,
                progress.tweetable,
            ),
        )
        await db.commit()
        new_id = cur.lastrowid
    return await get_progress(new_id)


@router.patch("/{progress_id}")
async def update_progress(progress_id: int, progress: ProgressUpdate) -> dict:
    fields = {
        k: v
        for k, v in progress.model_dump().items()
        if v is not None and k in _PROGRESS_UPDATE_COLUMNS
    }
    if not fields:
        return await get_progress(progress_id)
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [progress_id]
    async with aiosqlite.connect(config.DB_PATH) as db:
        result = await db.execute(
            f"UPDATE progress_logs SET {set_clause} WHERE id = ?", values
        )
        await db.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Progress log not found")
    return await get_progress(progress_id)


@router.delete("/{progress_id}", status_code=204)
async def delete_progress(progress_id: int) -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        result = await db.execute(
            "DELETE FROM progress_logs WHERE id = ?", (progress_id,)
        )
        await db.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Progress log not found")
