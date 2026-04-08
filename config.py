from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / os.getenv("PROMO_DB_PATH", "promo.db")
ASSETS_DIR = BASE_DIR / os.getenv("ASSETS_DIR", "assets")
PROMPTS_DIR = BASE_DIR / os.getenv("PROMPTS_DIR", "prompts")
SCHEMA_PATH = BASE_DIR / "schema.sql"
CLAUDE_TIMEOUT = int(os.getenv("CLAUDE_TIMEOUT", "120"))
SCHEDULER_POLL_SECONDS = int(os.getenv("SCHEDULER_POLL_SECONDS", "30"))
JST = ZoneInfo("Asia/Tokyo")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0")) or None
ALLOWED_USER_IDS = [
    int(value.strip())
    for value in os.getenv("ALLOWED_USER_IDS", "").split(",")
    if value.strip()
]

TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")


def require_env(name: str, value: str | None) -> str:
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def validate_discord_config() -> None:
    require_env("DISCORD_TOKEN", DISCORD_TOKEN)
    if not DISCORD_GUILD_ID:
        raise RuntimeError("Missing required environment variable: DISCORD_GUILD_ID")
    if not ALLOWED_USER_IDS:
        raise RuntimeError("ALLOWED_USER_IDS must contain at least one Discord user ID")


def validate_twitter_config() -> None:
    require_env("TWITTER_BEARER_TOKEN", TWITTER_BEARER_TOKEN)
    require_env("TWITTER_API_KEY", TWITTER_API_KEY)
    require_env("TWITTER_API_SECRET", TWITTER_API_SECRET)
    require_env("TWITTER_ACCESS_TOKEN", TWITTER_ACCESS_TOKEN)
    require_env("TWITTER_ACCESS_SECRET", TWITTER_ACCESS_SECRET)

