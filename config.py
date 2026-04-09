from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# .env ファイルを読み込み、環境変数として設定する
load_dotenv()

# プロジェクトのルートディレクトリ
BASE_DIR = Path(__file__).resolve().parent
# SQLite データベースのパス（デフォルト: promo.db）
DB_PATH = BASE_DIR / os.getenv("PROMO_DB_PATH", "promo.db")
# ゲーム素材ファイルの保存ディレクトリ
ASSETS_DIR = BASE_DIR / os.getenv("ASSETS_DIR", "assets")
# LLM プロンプトファイルの格納ディレクトリ
PROMPTS_DIR = BASE_DIR / os.getenv("PROMPTS_DIR", "prompts")
# DB スキーマファイルのパス
SCHEMA_PATH = BASE_DIR / "schema.sql"
# Claude CLI の実行タイムアウト（秒）
CLAUDE_TIMEOUT = int(os.getenv("CLAUDE_TIMEOUT", "120"))
# スケジューラのポーリング間隔（秒）
SCHEDULER_POLL_SECONDS = int(os.getenv("SCHEDULER_POLL_SECONDS", "30"))
# 日本標準時タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# Discord Bot の認証トークン
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
# コマンドを同期する必須のギルド ID
DISCORD_GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0")) or None
# Bot の操作を許可する Discord ユーザー ID のリスト
ALLOWED_USER_IDS = [
    int(value.strip())
    for value in os.getenv("ALLOWED_USER_IDS", "").split(",")
    if value.strip()
]

# Twitter/X API 認証情報
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")


def require_env(name: str, value: str | None) -> str:
    """必須の環境変数が設定されているかチェックし、未設定なら RuntimeError を送出する。"""
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def validate_discord_config() -> None:
    """Discord Bot に必要な環境変数がすべて設定されているか検証する。"""
    require_env("DISCORD_TOKEN", DISCORD_TOKEN)
    if not DISCORD_GUILD_ID:
        raise RuntimeError("Missing required environment variable: DISCORD_GUILD_ID")
    if not ALLOWED_USER_IDS:
        raise RuntimeError("ALLOWED_USER_IDS must contain at least one Discord user ID")


def validate_twitter_config() -> None:
    """Twitter/X API に必要な環境変数がすべて設定されているか検証する。"""
    require_env("TWITTER_BEARER_TOKEN", TWITTER_BEARER_TOKEN)
    require_env("TWITTER_API_KEY", TWITTER_API_KEY)
    require_env("TWITTER_API_SECRET", TWITTER_API_SECRET)
    require_env("TWITTER_ACCESS_TOKEN", TWITTER_ACCESS_TOKEN)
    require_env("TWITTER_ACCESS_SECRET", TWITTER_ACCESS_SECRET)

