from __future__ import annotations

from contextlib import asynccontextmanager

import aiosqlite

import config


@asynccontextmanager
async def connect():
    """aiosqlite 非同期接続のコンテキストマネージャ。

    外部キー制約（PRAGMA foreign_keys = ON）を接続ごとに有効にする。
    SQLite はデフォルトで接続ごとに外部キー制約が無効なため、このヘルパーを経由して
    DB アクセスすることで制約が確実に適用される。
    """
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        yield db
