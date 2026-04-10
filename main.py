"""FastAPI + Discord Bot の統合起動エントリポイント。

同一 asyncio イベントループ上で Uvicorn（FastAPI）と discord.py Bot を並走させる。
"""
from __future__ import annotations

import asyncio
import os

import uvicorn

import config
from api.app import app
from bot import PromoBot, build_bot
from services.db import init_db


async def _run_discord(bot: PromoBot) -> None:
    config.validate_discord_config()
    await bot.start(config.DISCORD_TOKEN)  # type: ignore[arg-type]


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

    bot = build_bot()

    async with asyncio.TaskGroup() as tg:
        tg.create_task(_run_api())
        tg.create_task(_run_discord(bot))


if __name__ == "__main__":
    asyncio.run(main())
