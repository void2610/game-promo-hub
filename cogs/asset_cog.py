from __future__ import annotations

from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from config import ASSETS_DIR
from services import db
from services.discord_utils import autocomplete_game_id, ensure_allowed


ASSET_USAGE_CHOICES = [
    app_commands.Choice(name="initial", value="initial"),
    app_commands.Choice(name="technical", value="technical"),
    app_commands.Choice(name="character", value="character"),
    app_commands.Choice(name="milestone", value="milestone"),
    app_commands.Choice(name="any", value="any"),
]


class AssetCog(commands.Cog):
    """素材ファイルの登録を担当する Cog。"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="asset_add", description="添付ファイルを素材として登録する")
    @app_commands.describe(
        game_id="ゲームID",
        file="登録する画像/GIF/動画",
        description="素材の説明",
        recommended_for="initial / technical / character / milestone / any",
    )
    @app_commands.choices(recommended_for=ASSET_USAGE_CHOICES)
    @app_commands.autocomplete(game_id=autocomplete_game_id)
    async def asset_add(
        self,
        interaction: discord.Interaction,
        game_id: str,
        file: discord.Attachment,
        description: str | None = None,
        recommended_for: str = "any",
    ) -> None:
        """Discord に添付されたファイルをローカルに保存し、素材として DB に登録する。"""
        if not await ensure_allowed(interaction):
            return
        game = await db.get_game(game_id)
        if not game:
            await interaction.response.send_message(f"ゲーム `{game_id}` が見つかりません。", ephemeral=True)
            return

        # ゲームごとのサブディレクトリに素材ファイルを保存
        target_dir = Path(ASSETS_DIR) / game_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / file.filename
        await file.save(target_path)

        # 拡張子から素材タイプを判定（拡張子なしの場合は "bin" とする）
        asset_type = target_path.suffix.lower().lstrip(".") or "bin"
        asset_id = await db.add_asset(
            {
                "game_id": game_id,
                "filename": file.filename,
                "asset_type": asset_type,
                "description": description,
                "recommended_for": recommended_for,
                "local_path": str(target_path),
                "width": file.width,
                "height": file.height,
            }
        )
        embed = discord.Embed(title="素材を登録しました", color=0xED4245)
        embed.add_field(name="ID", value=str(asset_id))
        embed.add_field(name="ファイル", value=file.filename)
        embed.add_field(name="用途", value=recommended_for)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Cog を Bot に登録するセットアップ関数。"""
    await bot.add_cog(AssetCog(bot))
