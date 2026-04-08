from __future__ import annotations

from typing import Iterable

import discord

from config import ALLOWED_USER_IDS


def is_allowed_user(interaction: discord.Interaction) -> bool:
    return interaction.user is not None and interaction.user.id in ALLOWED_USER_IDS


async def ensure_allowed(interaction: discord.Interaction) -> bool:
    if is_allowed_user(interaction):
        return True
    if interaction.response.is_done():
        await interaction.followup.send("権限がありません。", ephemeral=True)
    else:
        await interaction.response.send_message("権限がありません。", ephemeral=True)
    return False


def parse_list_input(raw: str) -> list[str]:
    values: list[str] = []
    for line in raw.replace("、", ",").splitlines():
        for piece in line.split(","):
            value = piece.strip()
            if value:
                values.append(value)
    return values


def format_hashtags(hashtags: Iterable[str]) -> str:
    return " ".join(tag.strip() for tag in hashtags if tag.strip()) or "-"

