from __future__ import annotations

from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from config import JST
from services import db
from services.discord_utils import autocomplete_game_id, ensure_allowed


EXCITEMENT_CHOICES = [
    app_commands.Choice(name="1", value=1),
    app_commands.Choice(name="2", value=2),
    app_commands.Choice(name="3", value=3),
]


class ProgressAddModal(discord.ui.Modal, title="進捗登録"):
    """進捗情報を入力するモーダルダイアログ。"""

    milestone = discord.ui.TextInput(label="マイルストーン", required=False, max_length=100)
    content = discord.ui.TextInput(label="進捗内容", style=discord.TextStyle.paragraph, max_length=1000)
    appeal_note = discord.ui.TextInput(
        label="宣伝ヒント",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=500,
    )
    log_date = discord.ui.TextInput(label="日付", default="", required=False, placeholder="YYYY-MM-DD")

    def __init__(self, game_id: str, excitement: int, tweetable: bool) -> None:
        super().__init__()
        self.game_id = game_id
        self.excitement = excitement
        self.tweetable = tweetable
        # 日付欄のデフォルト値を今日の JST 日付に設定
        self.log_date.default = datetime.now(JST).strftime("%Y-%m-%d")

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """モーダル送信時の処理。進捗ログを DB に追加する。"""
        if not await ensure_allowed(interaction):
            return
        game = await db.get_game(self.game_id)
        if not game:
            await interaction.response.send_message(f"ゲーム `{self.game_id}` が見つかりません。", ephemeral=True)
            return
        progress_id = await db.add_progress(
            {
                "game_id": self.game_id,
                "log_date": str(self.log_date).strip() or datetime.now(JST).strftime("%Y-%m-%d"),
                "milestone": str(self.milestone).strip() or None,
                "content": str(self.content).strip(),
                "appeal_note": str(self.appeal_note).strip() or None,
                "excitement": self.excitement,
                "tweetable": 1 if self.tweetable else 0,
            }
        )
        await interaction.response.send_message(
            f"進捗 #{progress_id} を `{self.game_id}` に追加しました。",
            ephemeral=True,
        )


class ProgressCog(commands.Cog):
    """進捗ログの登録を担当する Cog。"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="progress_add", description="進捗ログを追加する")
    @app_commands.describe(game_id="ゲームID", excitement="1-3", tweetable="投稿候補に含めるか")
    @app_commands.choices(excitement=EXCITEMENT_CHOICES)
    @app_commands.autocomplete(game_id=autocomplete_game_id)
    async def progress_add(
        self,
        interaction: discord.Interaction,
        game_id: str,
        excitement: int = 2,
        tweetable: bool = True,
    ) -> None:
        """進捗登録モーダルを開く。excitement と tweetable フラグをモーダルに引き渡す。"""
        if not await ensure_allowed(interaction):
            return
        await interaction.response.send_modal(ProgressAddModal(game_id, excitement, tweetable))


async def setup(bot: commands.Bot) -> None:
    """Cog を Bot に登録するセットアップ関数。"""
    await bot.add_cog(ProgressCog(bot))
