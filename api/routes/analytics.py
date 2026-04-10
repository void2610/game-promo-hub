from __future__ import annotations

from fastapi import APIRouter

from api.db import connect

router = APIRouter()


@router.get("/tweets")
async def list_tweets(game_id: str | None = None) -> list[dict]:
    query = "SELECT * FROM tweets"
    params: list = []
    if game_id:
        query += " WHERE game_id = ?"
        params.append(game_id)
    query += " ORDER BY posted_at DESC"
    async with connect() as db:
        async with db.execute(query, params) as cur:
            rows = await cur.fetchall()
    return [dict(row) for row in rows]


@router.get("/summaries")
async def list_summaries(game_id: str | None = None) -> list[dict]:
    query = "SELECT * FROM analytics_summaries"
    params: list = []
    if game_id:
        query += " WHERE game_id = ?"
        params.append(game_id)
    query += " ORDER BY created_at DESC"
    async with connect() as db:
        async with db.execute(query, params) as cur:
            rows = await cur.fetchall()
    return [dict(row) for row in rows]


@router.get("/metrics/history")
async def list_metrics_history(tweet_id: str | None = None) -> list[dict]:
    query = "SELECT * FROM tweet_metrics_history"
    params: list = []
    if tweet_id:
        query += " WHERE tweet_id = ?"
        params.append(tweet_id)
    query += " ORDER BY fetched_at ASC"
    async with connect() as db:
        async with db.execute(query, params) as cur:
            rows = await cur.fetchall()
    return [dict(row) for row in rows]
