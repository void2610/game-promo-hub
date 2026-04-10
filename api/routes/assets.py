from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

import config

router = APIRouter()


class AssetMeta(BaseModel):
    game_id: str
    asset_type: str | None = None
    description: str | None = None
    recommended_for: str | None = None
    width: int | None = None
    height: int | None = None


@router.get("")
async def list_assets(game_id: str | None = None) -> list[dict]:
    query = "SELECT * FROM assets"
    params: list = []
    if game_id:
        query += " WHERE game_id = ?"
        params.append(game_id)
    query += " ORDER BY created_at DESC"
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cur:
            rows = await cur.fetchall()
    return [dict(row) for row in rows]


@router.get("/{asset_id}")
async def get_asset(asset_id: int) -> dict:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)) as cur:
            row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return dict(row)


@router.post("", status_code=201)
async def upload_asset(file: UploadFile, meta: AssetMeta) -> dict:
    """素材ファイルをアップロードして DB に登録する。"""
    config.ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    save_path = config.ASSETS_DIR / file.filename
    content = await file.read()
    save_path.write_bytes(content)

    asset_type = meta.asset_type or (file.filename.rsplit(".", 1)[-1] if "." in (file.filename or "") else None)

    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO assets (game_id, filename, asset_type, description,
                                recommended_for, local_path, width, height)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                meta.game_id, file.filename, asset_type, meta.description,
                meta.recommended_for, str(save_path), meta.width, meta.height,
            ),
        )
        await db.commit()
        new_id = cur.lastrowid
    return await get_asset(new_id)


@router.delete("/{asset_id}", status_code=204)
async def delete_asset(asset_id: int) -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT local_path FROM assets WHERE id = ?", (asset_id,)) as cur:
            row = await cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Asset not found")
        import pathlib
        local_path = pathlib.Path(row["local_path"])
        if local_path.exists():
            local_path.unlink()
        await db.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
        await db.commit()
