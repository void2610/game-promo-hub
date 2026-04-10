from __future__ import annotations

import pathlib

import aiofiles
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

import config
from api.db import connect

router = APIRouter()


@router.get("")
async def list_assets(game_id: str | None = None) -> list[dict]:
    query = "SELECT * FROM assets"
    params: list = []
    if game_id:
        query += " WHERE game_id = ?"
        params.append(game_id)
    query += " ORDER BY created_at DESC"
    async with connect() as db:
        async with db.execute(query, params) as cur:
            rows = await cur.fetchall()
    return [dict(row) for row in rows]


@router.get("/{asset_id}")
async def get_asset(asset_id: int) -> dict:
    async with connect() as db:
        async with db.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)) as cur:
            row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return dict(row)


@router.post("", status_code=201)
async def upload_asset(
    file: UploadFile = File(...),
    game_id: str = Form(...),
    asset_type: str | None = Form(None),
    description: str | None = Form(None),
    recommended_for: str | None = Form(None),
    width: int | None = Form(None),
    height: int | None = Form(None),
) -> dict:
    """素材ファイルをアップロードして DB に登録する。"""
    config.ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    # クライアント指定のファイル名をサニタイズ（パストラバーサル防止）
    # Path(...).name でディレクトリ成分を除去し、ファイル名部分のみを使用する
    safe_filename = pathlib.Path(file.filename or "").name or "upload"
    save_path = config.ASSETS_DIR / safe_filename

    content = await file.read()
    async with aiofiles.open(save_path, "wb") as fp:
        await fp.write(content)

    resolved_asset_type = asset_type or (
        safe_filename.rsplit(".", 1)[-1] if "." in safe_filename else None
    )

    async with connect() as db:
        cur = await db.execute(
            """
            INSERT INTO assets (game_id, filename, asset_type, description,
                                recommended_for, local_path, width, height)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                game_id, safe_filename, resolved_asset_type, description,
                recommended_for, str(save_path), width, height,
            ),
        )
        await db.commit()
        new_id = cur.lastrowid
    return await get_asset(new_id)


@router.delete("/{asset_id}", status_code=204)
async def delete_asset(asset_id: int) -> None:
    async with connect() as db:
        async with db.execute("SELECT local_path FROM assets WHERE id = ?", (asset_id,)) as cur:
            row = await cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Asset not found")
        local_path = pathlib.Path(row["local_path"])
        if local_path.exists():
            local_path.unlink()
        await db.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
        await db.commit()

