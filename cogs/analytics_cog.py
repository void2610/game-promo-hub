from __future__ import annotations

from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from config import JST
from services import db, llm, twitter
from services.discord_utils import autocomplete_game_id, ensure_allowed


class AnalyticsCog(commands.Cog):
    """X/Twitter のアナリティクス取得・レポート生成を担当する Cog。"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="analytics_fetch", description="X/Twitter のメトリクスを今すぐ手動取得する")
    @app_commands.autocomplete(game_id=autocomplete_game_id)
    async def analytics_fetch(self, interaction: discord.Interaction, game_id: str) -> None:
        """直近 90 日のツイートのメトリクスを Twitter API から一括取得して DB に保存する。
        すでに取得済みのツイートも再取得して最新値に更新し、履歴に追記する。
        """
        if not await ensure_allowed(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        tweets = await db.get_recent_tweets_for_analytics(game_id, days=90)
        target_ids = [tweet["tweet_id"] for tweet in tweets if tweet.get("tweet_id")]
        if not target_ids:
            await interaction.followup.send("更新対象のツイートはありません。", ephemeral=True)
            return
        metrics = await twitter.fetch_tweet_metrics(target_ids)
        for item in metrics:
            await db.update_tweet_analytics(**item)
        await interaction.followup.send(f"{len(metrics)} 件のメトリクスを更新しました。", ephemeral=True)

    @app_commands.command(name="analytics_report", description="宣伝分析レポートを生成する")
    @app_commands.autocomplete(game_id=autocomplete_game_id)
    async def analytics_report(
        self,
        interaction: discord.Interaction,
        game_id: str,
        period: str | None = None,
    ) -> None:
        """過去 60 日のツイートデータを LLM に渡し、分析レポートを生成して表示する。"""
        if not await ensure_allowed(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        # period 未指定の場合は今月（JST）を使用
        if period is None:
            period = datetime.now(JST).strftime("%Y-%m")
        tweets = await db.get_recent_tweets_for_analytics(game_id, days=60)
        # メトリクスが取得済みのツイートのみを分析対象にする
        analyzed = [tweet for tweet in tweets if tweet.get("impressions") is not None]
        if not analyzed:
            await interaction.followup.send("分析対象データが不足しています。先に `/analytics_fetch` を実行してください。", ephemeral=True)
            return

        # ツイートデータをテキスト形式にまとめて LLM に渡す
        context = "\n".join(
            (
                f"- [{str(tweet['posted_at'])[:10]}] tone:{tweet.get('tone') or '-'} "
                f"impressions:{tweet.get('impressions') or 0} likes:{tweet.get('likes') or 0} "
                f"retweets:{tweet.get('retweets') or 0} replies:{tweet.get('replies') or 0} "
                f"| {tweet['content'][:80]}"
            )
            for tweet in analyzed
        )
        result = await llm.generate_analytics_report(context, period)
        await db.save_analytics_summary(game_id, period, result)

        schedule = result.get("recommended_schedule") or {}
        embed = discord.Embed(title=f"分析レポート {game_id} / {period}", color=0xFEE75C)
        embed.add_field(name="最適時間帯", value=result.get("best_time_slot") or "-", inline=True)
        embed.add_field(name="最適トーン", value=result.get("best_tone") or "-", inline=True)
        embed.add_field(name="最適素材", value=result.get("best_asset_type") or "-", inline=True)
        embed.add_field(name="避けるべきパターン", value="\n".join(result.get("avoid_patterns") or ["-"]), inline=False)
        embed.add_field(name="次の戦略", value=result.get("next_strategy") or "-", inline=False)
        embed.add_field(
            name="推奨スケジュール",
            value=f"{schedule.get('frequency', '-')} / {', '.join(schedule.get('days', []))}",
            inline=False,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="analytics_top", description="エンゲージメント上位投稿を表示する")
    @app_commands.autocomplete(game_id=autocomplete_game_id)
    async def analytics_top(
        self,
        interaction: discord.Interaction,
        game_id: str,
        limit: app_commands.Range[int, 1, 10] = 5,
    ) -> None:
        """エンゲージメント率の高い上位ツイートを Embed で表示する。"""
        if not await ensure_allowed(interaction):
            return
        top = await db.get_top_tweets(game_id, limit=limit)
        if not top:
            await interaction.response.send_message("対象データがありません。", ephemeral=True)
            return
        embed = discord.Embed(title=f"Top {limit} / {game_id}", color=0xEB459E)
        for index, tweet in enumerate(top, start=1):
            rate = (tweet.get("eng_rate") or 0) * 100
            embed.add_field(
                name=f"#{index} {rate:.2f}% ❤️{tweet.get('likes') or 0} 🔁{tweet.get('retweets') or 0}",
                value=f"{tweet['content'][:100]}\n{tweet.get('tweet_url') or '-'}",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


    @app_commands.command(name="analytics_history", description="ツイートのインプレッション時系列を表示する")
    async def analytics_history(
        self,
        interaction: discord.Interaction,
        tweet_id: str,
    ) -> None:
        """指定したツイートのインプレッション・いいね・RT の時系列履歴を Embed で表示する。"""
        if not await ensure_allowed(interaction):
            return
        history = await db.get_tweet_metrics_history(tweet_id)
        if not history:
            await interaction.response.send_message(
                "この tweet_id のメトリクス履歴がありません。自動取得を待つか、今すぐ反映したい場合は `/analytics_fetch` を実行してください。",
                ephemeral=True,
            )
            return
        embed = discord.Embed(
            title=f"インプレッション履歴 / {tweet_id}",
            description=f"取得回数: {len(history)} 回",
            color=0x1DA1F2,
        )
        # 最新 10 件に絞って表示する（Discord の Embed フィールド上限は 25）
        for snapshot in history[-10:]:
            raw_fetched_at = snapshot.get("fetched_at") or ""
            try:
                fetched_at = datetime.fromisoformat(raw_fetched_at).strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                fetched_at = str(raw_fetched_at)[:16]
            embed.add_field(
                name=fetched_at,
                value=(
                    f"👁 {snapshot.get('impressions') or 0}  "
                    f"❤️ {snapshot.get('likes') or 0}  "
                    f"🔁 {snapshot.get('retweets') or 0}  "
                    f"💬 {snapshot.get('replies') or 0}"
                ),
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Cog を Bot に登録するセットアップ関数。"""
    await bot.add_cog(AnalyticsCog(bot))
