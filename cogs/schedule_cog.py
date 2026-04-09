from __future__ import annotations

import sqlite3
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from config import JST
from services import db
from services.discord_utils import ensure_allowed


def _validate_slot_time(raw: str) -> str:
    """入力文字列を HH:MM 形式として検証し、正規化した文字列を返す。不正な場合は ValueError を送出する。"""
    parsed = datetime.strptime(raw, "%H:%M")
    return parsed.strftime("%H:%M")


class ScheduleCog(commands.Cog):
    """定期投稿スロットとキューの管理を担当する Cog。"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="schedule_slot_add", description="定期投稿スロットを追加する")
    async def schedule_slot_add(self, interaction: discord.Interaction, time_jst: str) -> None:
        """HH:MM 形式の JST 時刻を定期投稿スロットとして登録する。"""
        if not await ensure_allowed(interaction):
            return
        try:
            slot_time = _validate_slot_time(time_jst)
            slot_id = await db.add_schedule_slot(slot_time)
        except ValueError:
            await interaction.response.send_message("時刻は HH:MM 形式で指定してください。", ephemeral=True)
            return
        except sqlite3.IntegrityError:
            # 同じ時刻が既に登録されている場合
            await interaction.response.send_message("その時刻のスロットは既に存在します。", ephemeral=True)
            return
        await interaction.response.send_message(
            f"スロット #{slot_id} を {slot_time} JST に追加しました。",
            ephemeral=True,
        )

    @app_commands.command(name="schedule_slot_list", description="定期投稿スロット一覧を表示する")
    async def schedule_slot_list(self, interaction: discord.Interaction) -> None:
        """登録されているすべての投稿スロットを Embed で表示する。"""
        if not await ensure_allowed(interaction):
            return
        slots = await db.list_schedule_slots()
        if not slots:
            await interaction.response.send_message("登録済みスロットはありません。", ephemeral=True)
            return
        embed = discord.Embed(title="投稿スロット一覧", color=0x3498DB)
        for slot in slots:
            embed.add_field(name=f"#{slot['id']}", value=f"{slot['slot_time']} JST", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="schedule_slot_remove", description="定期投稿スロットを削除する")
    async def schedule_slot_remove(self, interaction: discord.Interaction, slot_id: int) -> None:
        """指定した ID の投稿スロットを削除する。"""
        if not await ensure_allowed(interaction):
            return
        await db.remove_schedule_slot(slot_id)
        await interaction.response.send_message(f"スロット #{slot_id} を削除しました。", ephemeral=True)

    @app_commands.command(name="schedule_queue_list", description="承認済みキューを表示する")
    async def schedule_queue_list(
        self,
        interaction: discord.Interaction,
        limit: app_commands.Range[int, 1, 20] = 10,
    ) -> None:
        """投稿待ちの承認済みキューを Embed で表示する（最大 limit 件）。"""
        if not await ensure_allowed(interaction):
            return
        queue = await db.list_approved_queue(limit=limit)
        if not queue:
            await interaction.response.send_message("承認済みキューは空です。", ephemeral=True)
            return
        embed = discord.Embed(title="承認済みキュー", color=0x95A5A6)
        for item in queue:
            embed.add_field(
                name=item["queue_id"],
                value=(
                    f"game: {item['game_id']}\n"
                    f"approved_at: {item.get('approved_at') or '-'}\n"
                    f"langs: {', '.join(item['langs'])}"
                ),
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="schedule_queue_cancel", description="承認済みキューを取り消す")
    async def schedule_queue_cancel(self, interaction: discord.Interaction, queue_id: str) -> None:
        """キューに入っている下書きグループを rejected にして取り消す。"""
        if not await ensure_allowed(interaction):
            return
        # "single:ID" 形式の場合は単一の下書き ID を抽出して処理
        if queue_id.startswith("single:"):
            await db.reject_draft_group(None, draft_id=int(queue_id.split(":", 1)[1]))
        else:
            await db.reject_draft_group(queue_id)
        await interaction.response.send_message(f"{queue_id} をキューから外しました。", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Cog を Bot に登録するセットアップ関数。"""
    await bot.add_cog(ScheduleCog(bot))
