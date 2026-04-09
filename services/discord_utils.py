from __future__ import annotations

from typing import Iterable

import discord

from config import ALLOWED_USER_IDS


def is_allowed_user(interaction: discord.Interaction) -> bool:
    """インタラクションを実行したユーザーが許可リストに含まれるか判定する。"""
    return interaction.user is not None and interaction.user.id in ALLOWED_USER_IDS


async def ensure_allowed(interaction: discord.Interaction) -> bool:
    """権限チェックを行い、許可されていない場合はエラーメッセージを送信して False を返す。"""
    if is_allowed_user(interaction):
        return True
    # すでにレスポンス済みの場合は followup で送信
    if interaction.response.is_done():
        await interaction.followup.send("権限がありません。", ephemeral=True)
    else:
        await interaction.response.send_message("権限がありません。", ephemeral=True)
    return False


def parse_list_input(raw: str) -> list[str]:
    """カンマ・改行・全角読点で区切られた文字列をリストに変換する。"""
    values: list[str] = []
    for line in raw.replace("、", ",").splitlines():
        for piece in line.split(","):
            value = piece.strip()
            if value:
                values.append(value)
    return values


def format_hashtags(hashtags: Iterable[str]) -> str:
    """ハッシュタグのリストをスペース区切りの文字列にフォーマットする。空の場合は "-" を返す。"""
    return " ".join(tag.strip() for tag in hashtags if tag.strip()) or "-"


