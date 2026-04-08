from __future__ import annotations

import json

import discord
from discord import app_commands
from discord.ext import commands

from services import db, llm
from services.discord_utils import ensure_allowed, format_hashtags

VALID_MODES = ("progress", "appeal", "milestone", "random", "technical", "character", "art", "story")
VALID_LANGS = ("ja", "en", "both")
VALID_TONES = ("excited", "casual", "technical", "mysterious")


class ApprovalView(discord.ui.View):
    def __init__(self, cog: "PromoCog", draft_ids: list[int], draft_group_id: str | None) -> None:
        super().__init__(timeout=3600)
        self.cog = cog
        self.draft_ids = draft_ids
        self.draft_group_id = draft_group_id

    @discord.ui.button(label="承認してキューへ追加", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await ensure_allowed(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        await self.cog.approve_drafts(interaction, self.draft_ids, self.draft_group_id)
        self.stop()

    @discord.ui.button(label="再生成", style=discord.ButtonStyle.primary)
    async def regenerate(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await ensure_allowed(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        draft = await db.get_draft(self.draft_ids[0])
        if not draft:
            await interaction.followup.send("下書きが見つかりません。", ephemeral=True)
            return
        await db.reject_draft_group(self.draft_group_id, draft_id=self.draft_ids[0])
        await self.cog.generate_and_show(
            interaction,
            game_id=draft["game_id"],
            tone=draft.get("tone") or "casual",
            mode=draft.get("mode") or "random",
            lang="both" if self.draft_group_id else (draft.get("lang") or "ja"),
        )
        self.stop()

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await ensure_allowed(interaction):
            return
        await db.reject_draft_group(self.draft_group_id, draft_id=self.draft_ids[0])
        await interaction.response.send_message("下書きを破棄しました。", ephemeral=True)
        self.stop()


class PromoCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="promo_draft", description="ツイート下書きを生成する")
    async def promo_draft(
        self,
        interaction: discord.Interaction,
        game_id: str,
        mode: str = "random",
        lang: str = "ja",
        tone: str = "casual",
    ) -> None:
        if not await ensure_allowed(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        await self.generate_and_show(interaction, game_id=game_id, tone=tone, mode=mode, lang=lang)

    async def generate_and_show(
        self,
        interaction: discord.Interaction,
        game_id: str,
        tone: str,
        mode: str,
        lang: str,
    ) -> None:
        if mode not in VALID_MODES:
            await interaction.followup.send(f"mode は {', '.join(VALID_MODES)} から選んでください。", ephemeral=True)
            return
        if lang not in VALID_LANGS:
            await interaction.followup.send(f"lang は {', '.join(VALID_LANGS)} から選んでください。", ephemeral=True)
            return
        if tone not in VALID_TONES:
            await interaction.followup.send(f"tone は {', '.join(VALID_TONES)} から選んでください。", ephemeral=True)
            return

        game = await db.get_game(game_id)
        if not game:
            await interaction.followup.send(f"ゲーム `{game_id}` が見つかりません。", ephemeral=True)
            return

        await interaction.followup.send(f"`{game_id}` の下書きを生成中です。", ephemeral=True)
        context = await db.build_promo_context(game_id, mode)
        result = await llm.generate_promo_tweet(context.text, mode, lang, tone)

        asset = None
        asset_id = result.get("recommended_asset_id")
        if isinstance(asset_id, int):
            asset = await db.get_asset_by_id(asset_id)

        draft_group_id = db.generate_draft_group_id() if lang == "both" else None
        draft_ids: list[int] = []
        languages = ("ja", "en") if lang == "both" else (lang,)
        for language in languages:
            content = result.get("tweet_ja") if language == "ja" else result.get("tweet_en")
            draft_ids.append(
                await db.add_draft(
                    {
                        "draft_group_id": draft_group_id,
                        "game_id": game_id,
                        "mode": mode,
                        "lang": language,
                        "content": content or "",
                        "asset_id": asset["id"] if asset else None,
                        "tone": result.get("tone_used") or tone,
                        "strategy_note": result.get("strategy_note"),
                        "asset_reason": result.get("asset_reason"),
                        "source_progress_ids": context.progress_ids,
                        "source_appeal_ids": context.appeal_ids,
                    }
                )
            )

        embed = discord.Embed(title="プロモ下書き", color=0x1DA1F2)
        embed.add_field(name="ゲーム", value=f"{game['name_ja']} (`{game_id}`)", inline=False)
        embed.add_field(name="モード", value=mode)
        embed.add_field(name="トーン", value=result.get("tone_used") or tone)
        embed.add_field(name="ハッシュタグ", value=format_hashtags(game.get("hashtags", [])), inline=False)
        if "ja" in languages:
            embed.add_field(name="日本語", value=result.get("tweet_ja") or "-", inline=False)
        if "en" in languages:
            embed.add_field(name="English", value=result.get("tweet_en") or "-", inline=False)
        if asset:
            embed.add_field(
                name="推奨素材",
                value=f"`{asset['filename']}`\n{result.get('asset_reason') or ''}",
                inline=False,
            )
        embed.add_field(name="戦略メモ", value=result.get("strategy_note") or "-", inline=False)

        view = ApprovalView(self, draft_ids=draft_ids, draft_group_id=draft_group_id)
        message = await interaction.followup.send(embed=embed, view=view, ephemeral=True, wait=True)
        if draft_group_id:
            await db.update_draft_group_message(draft_group_id, str(message.id))
        else:
            await db.update_draft_message(draft_ids[0], str(message.id))

    async def approve_drafts(
        self,
        interaction: discord.Interaction,
        draft_ids: list[int],
        draft_group_id: str | None,
    ) -> None:
        if draft_group_id:
            await db.approve_draft_group(draft_group_id, approved_by=str(interaction.user.id))
            drafts = await db.get_drafts_by_group(draft_group_id)
            queue_id = draft_group_id
        else:
            draft_id = draft_ids[0]
            await db.approve_draft_group(None, approved_by=str(interaction.user.id), draft_id=draft_id)
            draft = await db.get_draft(draft_id)
            drafts = [draft] if draft else []
            queue_id = f"single:{draft_id}"

        embed = discord.Embed(title="キューへ追加しました", color=0x57F287)
        embed.add_field(name="Queue ID", value=queue_id, inline=False)
        embed.add_field(name="件数", value=str(len([draft for draft in drafts if draft])), inline=True)
        embed.add_field(name="状態", value="approved", inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PromoCog(bot))
