"""FastAPI + Discord Bot の統合起動エントリポイント。

同一 asyncio イベントループ上で Uvicorn（FastAPI）と discord.py Bot を並走させる。
環境変数 DISCORD_ENABLED=false を設定すると Discord Bot を起動しない（テスト・Docker 動作確認時に使用）。
"""
from __future__ import annotations

import asyncio
import logging
import os

import uvicorn

import config
from api.app import app
from services.db import init_db

logger = logging.getLogger(__name__)

_DISCORD_ENABLED = os.getenv("DISCORD_ENABLED", "true").lower() not in ("false", "0", "no")


async def _run_discord() -> None:
    from bot import build_bot
    bot = build_bot()
    config.validate_discord_config()
    try:
        await bot.start(config.DISCORD_TOKEN)  # type: ignore[arg-type]
    except Exception as exc:
        logger.error("Discord Bot error: %s", exc)
        raise


async def _run_api() -> None:
    port = int(os.getenv("API_PORT", "8080"))
    server_config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(server_config)
    await server.serve()


async def main() -> None:
    await init_db()

    if _DISCORD_ENABLED:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(_run_api())
            tg.create_task(_run_discord())
    else:
        logger.info("Discord Bot disabled (DISCORD_ENABLED=false). Starting API only.")
        await _run_api()


if __name__ == "__main__":
    asyncio.run(main())
