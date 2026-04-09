from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from services import db
from services.discord_utils import ensure_allowed


class AppealAddModal(discord.ui.Modal, title="アピールポイント登録"):
    """アピールポイントを入力するモーダルダイアログ。"""

    category = discord.ui.TextInput(label="カテゴリ", placeholder="mechanics / art / story / technical")
    priority = discord.ui.TextInput(label="優先度", default="2", placeholder="1-3")
    title_input = discord.ui.TextInput(label="タイトル", max_length=100)
    content = discord.ui.TextInput(label="内容", style=discord.TextStyle.paragraph, max_length=1000)
    promo_tips = discord.ui.TextInput(
        label="宣伝ヒント",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=500,
    )

    def __init__(self, game_id: str) -> None:
        super().__init__()
        self.game_id = game_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """モーダル送信時の処理。優先度を 1–3 にクランプして DB に登録する。"""
        if not await ensure_allowed(interaction):
            return
        game = await db.get_game(self.game_id)
        if not game:
            await interaction.response.send_message(f"ゲーム `{self.game_id}` が見つかりません。", ephemeral=True)
            return
        # 優先度の入力値を 1–3 の範囲にクランプする
        try:
            priority = max(1, min(3, int(str(self.priority).strip() or "2")))
        except ValueError:
            priority = 2
        appeal_id = await db.add_appeal(
            {
                "game_id": self.game_id,
                "category": str(self.category).strip() or "general",
                "priority": priority,
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
    async def appeal_add(self, interaction: discord.Interaction, game_id: str) -> None:
        """アピールポイント登録モーダルを開く。"""
        if not await ensure_allowed(interaction):
            return
        await interaction.response.send_modal(AppealAddModal(game_id))


async def setup(bot: commands.Bot) -> None:
    """Cog を Bot に登録するセットアップ関数。"""
    await bot.add_cog(AppealCog(bot))

