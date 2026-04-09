from __future__ import annotations

import discord
from discord.ext import commands

from config import DISCORD_GUILD_ID, DISCORD_TOKEN, validate_discord_config
from services.db import init_db
from services.scheduler import dispatch_analytics, dispatch_scheduled_posts, setup_scheduler

# 読み込む Cog（機能モジュール）の一覧
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
        """Bot 起動時の初期化処理。DB 初期化・Cog 読み込み・スケジューラ起動・コマンド同期を行う。"""
        await init_db()
        for extension in EXTENSIONS:
            await self.load_extension(extension)
        setup_scheduler(self)
        # validate_discord_config() により設定済みのギルドへコマンドを同期（反映が速い）
        guild = discord.Object(id=DISCORD_GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    async def dispatch_scheduled_posts(self) -> bool:
        """スケジューラから呼ばれる定期投稿の実行。"""
        return await dispatch_scheduled_posts(self)

    async def dispatch_analytics(self) -> int:
        """スケジューラから呼ばれる自動アナリティクス取得の実行。"""
        return await dispatch_analytics(self)


def build_bot() -> PromoBot:
    """Bot インスタンスを生成して返す。"""
    intents = discord.Intents.default()
    intents.message_content = True
    return PromoBot(command_prefix="!", intents=intents)


bot = build_bot()


@bot.event
async def on_ready() -> None:
    """Bot の準備が完了したときに呼ばれるイベント。"""
    print(f"Bot ready: {bot.user}")


if __name__ == "__main__":
    validate_discord_config()
    bot.run(DISCORD_TOKEN)
