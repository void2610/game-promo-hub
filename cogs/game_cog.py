from __future__ import annotations

import sqlite3

import discord
from discord import app_commands
from discord.ext import commands

from services import db
from services.discord_utils import ensure_allowed, format_hashtags, parse_list_input


class GameAddModal(discord.ui.Modal, title="ゲーム登録"):
    """ゲーム情報を入力するモーダルダイアログ。"""

    game_id = discord.ui.TextInput(label="ゲームID", placeholder="niwa-kobito", max_length=50)
    name_ja = discord.ui.TextInput(label="日本語名", max_length=100)
    name_en = discord.ui.TextInput(label="英語名", required=False, max_length=100)
    genre = discord.ui.TextInput(label="ジャンル", required=False, max_length=100)
    details = discord.ui.TextInput(
        label="補足",
        placeholder=(
            "platform=Steam\n"
            "status=development\n"
            "hashtags=#庭小人,#indiegame\n"
            "circle=ねこのおでこ\n"
            "steam_url=..."
        ),
        required=False,
        style=discord.TextStyle.paragraph,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """モーダル送信時の処理。補足欄を key=value 形式でパースして DB に登録する。"""
        if not await ensure_allowed(interaction):
            return
        # 補足欄の key=value 行をパース
        detail_map = {}
        for line in str(self.details).splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            detail_map[key.strip()] = value.strip()

        try:
            await db.add_game(
                {
                    "id": str(self.game_id).strip(),
                    "name_ja": str(self.name_ja).strip(),
                    "name_en": str(self.name_en).strip() or None,
                    "genre": str(self.genre).strip() or None,
                    "platform": detail_map.get("platform", "Steam"),
                    "status": detail_map.get("status", "development"),
                    "steam_url": detail_map.get("steam_url"),
                    "elevator_ja": detail_map.get("elevator_ja"),
                    "elevator_en": detail_map.get("elevator_en"),
                    "hashtags": parse_list_input(detail_map.get("hashtags", "")),
                    "target_audience": parse_list_input(detail_map.get("target_audience", "")),
                    "circle": detail_map.get("circle"),
                }
            )
        except sqlite3.IntegrityError:
            # 同一 ID が既に登録されている場合はエラーを返す
            await interaction.response.send_message(
                f"ゲームID `{str(self.game_id).strip()}` は既に登録されています。",
                ephemeral=True,
            )
            return
        game = await db.get_game(str(self.game_id).strip())
        embed = discord.Embed(title="ゲームを登録しました", color=0x3BA55D)
        embed.add_field(name="ID", value=game["id"])
        embed.add_field(name="名前", value=game["name_ja"])
        embed.add_field(name="ハッシュタグ", value=format_hashtags(game["hashtags"]), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class GameCog(commands.Cog):
    """ゲームの登録・一覧表示を担当する Cog。"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="game_add", description="ゲームを登録する")
    async def game_add(self, interaction: discord.Interaction) -> None:
        """ゲーム登録モーダルを開く。"""
        if not await ensure_allowed(interaction):
            return
        await interaction.response.send_modal(GameAddModal())

    @app_commands.command(name="game_list", description="登録されているゲーム一覧を表示する")
    async def game_list(self, interaction: discord.Interaction) -> None:
        """登録済みゲームの一覧を Embed で表示する（最大 25 件）。"""
        if not await ensure_allowed(interaction):
            return
        games = await db.list_games()
        if not games:
            await interaction.response.send_message("登録済みゲームはありません。", ephemeral=True)
            return

        embed = discord.Embed(title="登録ゲーム一覧", color=0x5865F2)
        for game in games[:25]:
            embed.add_field(
                name=f"{game['name_ja']} ({game['id']})",
                value=(
                    f"status: {game.get('status') or '-'}\n"
                    f"platform: {game.get('platform') or '-'}\n"
                    f"hashtags: {format_hashtags(game.get('hashtags', []))}"
                ),
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Cog を Bot に登録するセットアップ関数。"""
    await bot.add_cog(GameCog(bot))
