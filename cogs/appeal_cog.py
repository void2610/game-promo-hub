from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from services import db
from services.discord_utils import autocomplete_game_id, ensure_allowed


APPEAL_CATEGORY_CHOICES = [
    app_commands.Choice(name="mechanics", value="mechanics"),
    app_commands.Choice(name="art", value="art"),
    app_commands.Choice(name="story", value="story"),
    app_commands.Choice(name="technical", value="technical"),
    app_commands.Choice(name="general", value="general"),
]

APPEAL_PRIORITY_CHOICES = [
    app_commands.Choice(name="1", value=1),
    app_commands.Choice(name="2", value=2),
    app_commands.Choice(name="3", value=3),
]


class AppealAddModal(discord.ui.Modal, title="アピールポイント登録"):
    """アピールポイントを入力するモーダルダイアログ。"""

    title_input = discord.ui.TextInput(label="タイトル", max_length=100)
    content = discord.ui.TextInput(label="内容", style=discord.TextStyle.paragraph, max_length=1000)
    promo_tips = discord.ui.TextInput(
        label="宣伝ヒント",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=500,
    )

    def __init__(self, game_id: str, category: str, priority: int) -> None:
        super().__init__()
        self.game_id = game_id
        self.category = category
        self.priority = priority

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """モーダル送信時の処理。コマンド引数で受け取った分類情報とともに DB に登録する。"""
        if not await ensure_allowed(interaction):
            return
        game = await db.get_game(self.game_id)
        if not game:
            await interaction.response.send_message(f"ゲーム `{self.game_id}` が見つかりません。", ephemeral=True)
            return
        appeal_id = await db.add_appeal(
            {
                "game_id": self.game_id,
                "category": self.category,
                "priority": self.priority,
                "title": str(self.title_input).strip(),
                "content": str(self.content).strip(),
                "promo_tips": str(self.promo_tips).strip() or None,
            }
        )
        await interaction.response.send_message(
            f"アピールポイント #{appeal_id} を `{self.game_id}` に追加しました。",
            ephemeral=True,
        )


class AppealCog(commands.Cog):
    """アピールポイントの登録を担当する Cog。"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="appeal_add", description="アピールポイントを追加する")
    @app_commands.describe(game_id="ゲームID", category="カテゴリ", priority="優先度")
    @app_commands.choices(category=APPEAL_CATEGORY_CHOICES, priority=APPEAL_PRIORITY_CHOICES)
    @app_commands.autocomplete(game_id=autocomplete_game_id)
    async def appeal_add(
        self,
        interaction: discord.Interaction,
        game_id: str,
        category: str = "general",
        priority: int = 2,
    ) -> None:
        """アピールポイント登録モーダルを開く。"""
        if not await ensure_allowed(interaction):
            return
        await interaction.response.send_modal(AppealAddModal(game_id, category, priority))


async def setup(bot: commands.Bot) -> None:
    """Cog を Bot に登録するセットアップ関数。"""
    await bot.add_cog(AppealCog(bot))
