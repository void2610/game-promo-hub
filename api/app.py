from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import analytics, appeals, assets, drafts, games, progress, schedule

app = FastAPI(title="Game Promo Hub API", version="0.1.0")

# CORS: Next.js フロントエンドからのアクセスを許可
_allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーターを登録
app.include_router(games.router, prefix="/v1/games", tags=["games"])
app.include_router(progress.router, prefix="/v1/progress", tags=["progress"])
app.include_router(appeals.router, prefix="/v1/appeals", tags=["appeals"])
app.include_router(assets.router, prefix="/v1/assets", tags=["assets"])
app.include_router(drafts.router, prefix="/v1/drafts", tags=["drafts"])
app.include_router(analytics.router, prefix="/v1/analytics", tags=["analytics"])
app.include_router(schedule.router, prefix="/v1/schedule", tags=["schedule"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
