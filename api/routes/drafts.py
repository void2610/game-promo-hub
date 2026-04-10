from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import config

router = APIRouter()


class DraftUpdate(BaseModel):
    content: str | None = None
    status: str | None = None
    approved_by: str | None = None


@router.get("")
async def list_drafts(
    status: str | None = None,
    game_id: str | None = None,
) -> list[dict]:
    conditions: list[str] = []
    params: list = []
    if status:
        conditions.append("status = ?")
        params.append(status)
    if game_id:
        conditions.append("game_id = ?")
        params.append(game_id)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT * FROM tweet_drafts
        {where}
        ORDER BY created_at DESC
    """
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cur:
            rows = await cur.fetchall()
    return [dict(row) for row in rows]


@router.get("/{draft_id}")
async def get_draft(draft_id: int) -> dict:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM tweet_drafts WHERE id = ?", (draft_id,)
        ) as cur:
            row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return dict(row)


@router.patch("/{draft_id}")
async def update_draft(draft_id: int, draft: DraftUpdate) -> dict:
    fields = {k: v for k, v in draft.model_dump().items() if v is not None}
    if not fields:
        return await get_draft(draft_id)
    # approved_at を自動設定
    if fields.get("status") == "approved" and "approved_at" not in fields:
        fields["approved_at"] = "CURRENT_TIMESTAMP"

    set_parts: list[str] = []
    values: list = []
    for k, v in fields.items():
        if v == "CURRENT_TIMESTAMP":
            set_parts.append(f"{k} = CURRENT_TIMESTAMP")
        else:
            set_parts.append(f"{k} = ?")
            values.append(v)
    values.append(draft_id)

    async with aiosqlite.connect(config.DB_PATH) as db:
        result = await db.execute(
            f"UPDATE tweet_drafts SET {', '.join(set_parts)} WHERE id = ?", values
        )
        await db.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Draft not found")
    return await get_draft(draft_id)


@router.delete("/{draft_id}", status_code=204)
async def delete_draft(draft_id: int) -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        result = await db.execute(
            "DELETE FROM tweet_drafts WHERE id = ?", (draft_id,)
        )
        await db.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Draft not found")
