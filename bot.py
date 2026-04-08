from __future__ import annotations

import discord
from discord.ext import commands

from config import DISCORD_GUILD_ID, DISCORD_TOKEN, validate_discord_config
from services.db import init_db
from services.scheduler import dispatch_scheduled_posts, setup_scheduler

EXTENSIONS = (
    "cogs.game_cog",
    "cogs.progress_cog",
    "cogs.appeal_cog",
    "cogs.asset_cog",
    "cogs.promo_cog",
    "cogs.analytics_cog",
    "cogs.schedule_cog",
)


class PromoBot(commands.Bot):
    async def setup_hook(self) -> None:
        await init_db()
        for extension in EXTENSIONS:
            await self.load_extension(extension)
        setup_scheduler(self)
        if DISCORD_GUILD_ID:
            guild = discord.Object(id=DISCORD_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def dispatch_scheduled_posts(self) -> bool:
        return await dispatch_scheduled_posts(self)


def build_bot() -> PromoBot:
    intents = discord.Intents.default()
    intents.message_content = True
    return PromoBot(command_prefix="!", intents=intents)


bot = build_bot()


@bot.event
async def on_ready() -> None:
    print(f"Bot ready: {bot.user}")


if __name__ == "__main__":
    validate_discord_config()
    bot.run(DISCORD_TOKEN)
