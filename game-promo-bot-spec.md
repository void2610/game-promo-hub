# game-promo-bot 実装仕様書

## 概要

複数のインディーゲームを同時開発している開発者が、ゲームの宣伝活動を半自動化するDiscordボット。
ゲームの進捗・アピールポイントをSQLiteで管理し、Discordコマンドをトリガーとして
Claude Code CLIに推論させてTwitter投稿用コンテンツを生成・投稿・分析するシステム。

### 設計方針
- **LLM推論はClaude Code CLIをsubprocessで呼び出す**（クラウドAPI不使用・コストゼロ）
- **データはSQLiteで一元管理**（マークダウンファイル不使用）
- **Discordがすべての操作インターフェース**
- **M1 MacBook Pro上で常時稼働**を前提とする

---

## 動作環境

- macOS（M1 MacBook Pro）
- Python 3.11+
- Claude Code CLI（`claude`コマンドがPATHに通っていること）
- Twitter Developer Account（API v2 / OAuth 2.0）
- Discord Bot Token

---

## ディレクトリ構造

```
game-promo-bot/
├── bot.py                        # エントリポイント
├── config.py                     # 環境変数・定数
├── requirements.txt
├── .env
├── promo.db                      # SQLiteデータベース（自動生成）
│
├── cogs/                         # Discordスラッシュコマンド
│   ├── __init__.py
│   ├── game_cog.py               # /game 系コマンド
│   ├── progress_cog.py           # /progress 系コマンド
│   ├── appeal_cog.py             # /appeal 系コマンド
│   ├── asset_cog.py              # /asset 系コマンド
│   ├── promo_cog.py              # /promo 系コマンド（メイン）
│   └── analytics_cog.py         # /analytics 系コマンド
│
├── services/
│   ├── __init__.py
│   ├── db.py                     # SQLite操作
│   ├── llm.py                    # Claude Code CLI呼び出し
│   ├── twitter.py                # Twitter API v2
│   └── scheduler.py             # APScheduler（予約投稿）
│
├── prompts/
│   ├── system_promo.txt          # プロモ生成システムプロンプト
│   ├── system_analytics.txt      # 分析システムプロンプト
│   └── brand_voice.txt           # 全ゲーム共通トーン制約
│
└── assets/                       # 画像・GIFファイル実体
    ├── niwa-kobito/
    └── void-red/
```

---

## .env

```env
DISCORD_TOKEN=your_discord_bot_token
TWITTER_BEARER_TOKEN=your_bearer_token
TWITTER_API_KEY=your_api_key
TWITTER_API_SECRET=your_api_secret
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_SECRET=your_access_secret
DISCORD_GUILD_ID=your_guild_id          # スラッシュコマンドを登録するサーバーID
ALLOWED_USER_IDS=123456789,987654321    # ボット操作を許可するDiscordユーザーID（カンマ区切り）
```

---

## requirements.txt

```
discord.py>=2.3.0
aiosqlite>=0.19.0
tweepy>=4.14.0
apscheduler>=3.10.0
python-dotenv>=1.0.0
aiofiles>=23.0.0
```

---

## DBスキーマ（`services/db.py` で `CREATE TABLE IF NOT EXISTS` として初期化）

```sql
-- ゲーム基本情報
CREATE TABLE IF NOT EXISTS games (
    id              TEXT PRIMARY KEY,
    name_ja         TEXT NOT NULL,
    name_en         TEXT,
    genre           TEXT,
    platform        TEXT DEFAULT 'Steam',
    status          TEXT DEFAULT 'development',  -- development | coming_soon | released
    steam_url       TEXT,
    elevator_ja     TEXT,   -- 140字エレベーターピッチ
    elevator_en     TEXT,
    hashtags        TEXT,   -- JSON配列文字列: ["#庭小人","#indiegame"]
    target_audience TEXT,   -- JSON配列文字列
    circle          TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 進捗ログ
CREATE TABLE IF NOT EXISTS progress_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT NOT NULL REFERENCES games(id),
    log_date        DATE NOT NULL,
    milestone       TEXT,
    content         TEXT NOT NULL,
    appeal_note     TEXT,           -- LLMへのヒント（どんなトーンで宣伝したいか）
    excitement      INTEGER DEFAULT 2,  -- 1:low 2:medium 3:high
    tweetable       INTEGER DEFAULT 1,  -- 0 or 1
    tweeted         INTEGER DEFAULT 0,  -- 使用済みフラグ
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- アピールポイント（恒久的な差別化情報）
CREATE TABLE IF NOT EXISTS appeal_points (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT NOT NULL REFERENCES games(id),
    category        TEXT,   -- mechanics | art | story | technical | character
    priority        INTEGER DEFAULT 2,  -- 1:low 2:mid 3:high
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    promo_tips      TEXT,           -- 宣伝での使い方メモ
    last_used_at    DATETIME,       -- 最後にツイートに使った日時
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 使用可能素材
CREATE TABLE IF NOT EXISTS assets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT NOT NULL REFERENCES games(id),
    filename        TEXT NOT NULL,
    asset_type      TEXT,           -- png | gif | mp4
    description     TEXT,
    recommended_for TEXT,           -- initial | technical | character | milestone | any
    local_path      TEXT NOT NULL,
    width           INTEGER,
    height          INTEGER,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 投稿済みツイート
CREATE TABLE IF NOT EXISTS tweets (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    tweet_id             TEXT UNIQUE,
    game_id              TEXT NOT NULL REFERENCES games(id),
    lang                 TEXT,       -- ja | en
    content              TEXT NOT NULL,
    asset_id             INTEGER REFERENCES assets(id),
    tone                 TEXT,
    strategy_note        TEXT,
    posted_at            DATETIME,
    tweet_url            TEXT,
    impressions          INTEGER,
    likes                INTEGER,
    retweets             INTEGER,
    replies              INTEGER,
    analytics_fetched_at DATETIME,
    approved_by          TEXT,       -- DiscordユーザーID
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 下書き（承認待ち）
CREATE TABLE IF NOT EXISTS tweet_drafts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT NOT NULL REFERENCES games(id),
    lang            TEXT,
    content         TEXT NOT NULL,
    asset_id        INTEGER REFERENCES assets(id),
    tone            TEXT,
    strategy_note   TEXT,
    asset_reason    TEXT,
    status          TEXT DEFAULT 'pending',  -- pending | approved | rejected
    discord_msg_id  TEXT,  -- 承認メッセージのDiscord message ID
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 分析サマリー
CREATE TABLE IF NOT EXISTS analytics_summaries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT NOT NULL REFERENCES games(id),
    period          TEXT,   -- 'YYYY-MM'
    best_time_slot  TEXT,
    best_tone       TEXT,
    best_asset_type TEXT,
    strategy_note   TEXT,
    raw_analysis    TEXT,   -- LLMの全出力JSON
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## `bot.py`

```python
import asyncio
import discord
from discord.ext import commands
from config import DISCORD_TOKEN, DISCORD_GUILD_ID
from services.db import init_db
from services.scheduler import setup_scheduler

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await init_db()
    setup_scheduler(bot)
    await bot.load_extension("cogs.game_cog")
    await bot.load_extension("cogs.progress_cog")
    await bot.load_extension("cogs.appeal_cog")
    await bot.load_extension("cogs.asset_cog")
    await bot.load_extension("cogs.promo_cog")
    await bot.load_extension("cogs.analytics_cog")

    guild = discord.Object(id=DISCORD_GUILD_ID)
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)
    print(f"✅ Bot ready: {bot.user}")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
```

---

## `config.py`

```python
import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN      = os.getenv("DISCORD_TOKEN")
DISCORD_GUILD_ID   = int(os.getenv("DISCORD_GUILD_ID"))
ALLOWED_USER_IDS   = [int(x) for x in os.getenv("ALLOWED_USER_IDS", "").split(",") if x]

TWITTER_BEARER_TOKEN  = os.getenv("TWITTER_BEARER_TOKEN")
TWITTER_API_KEY       = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET    = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN  = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

DB_PATH      = "promo.db"
ASSETS_DIR   = "assets"
PROMPTS_DIR  = "prompts"
CLAUDE_TIMEOUT = 120   # subprocess タイムアウト秒数
```

---

## `services/llm.py`（Claude Code CLI呼び出し）

```python
import asyncio
import json
import os
from config import CLAUDE_TIMEOUT, PROMPTS_DIR


async def run_claude(prompt: str, timeout: int = CLAUDE_TIMEOUT) -> str:
    """
    claude --print でサブプロセス起動し、stdoutを返す。
    --print: 非インタラクティブモード。プロンプトをstdinで受け取り結果をstdoutに出力。
    """
    proc = await asyncio.create_subprocess_exec(
        "claude",
        "--print",
        "--output-format", "text",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=prompt.encode("utf-8")),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError("Claude CLIがタイムアウトしました")

    if proc.returncode != 0:
        raise RuntimeError(f"Claude CLIエラー: {stderr.decode()}")

    return stdout.decode("utf-8").strip()


def _load_prompt(filename: str) -> str:
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _extract_json(raw: str) -> dict:
    """LLMの出力からJSON部分を抽出してパース"""
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"JSONが見つかりません: {raw[:200]}")
    return json.loads(raw[start:end])


async def generate_promo_tweet(context: str, mode: str, lang: str, tone: str) -> dict:
    """
    期待するJSONレスポンス:
    {
      "tweet_ja": "...",
      "tweet_en": "...",
      "recommended_asset_id": 3,
      "asset_reason": "...",
      "tone_used": "...",
      "strategy_note": "..."
    }
    """
    system  = _load_prompt("system_promo.txt")
    voice   = _load_prompt("brand_voice.txt")

    prompt = f"""{system}

{voice}

---

## リクエスト
- モード: {mode}
- 言語: {lang}
- トーン: {tone}

## ゲームデータ
{context}

---

## 出力形式
必ず以下のJSONのみを返すこと。前置き・説明文・マークダウン記法は一切不要。

{{
  "tweet_ja": "日本語ツイート本文（140字以内、ハッシュタグ除く）",
  "tweet_en": "English tweet body (under 250 chars, no hashtags)",
  "recommended_asset_id": <assets テーブルのid。素材がなければ null>,
  "asset_reason": "この素材を選んだ理由",
  "tone_used": "実際に使ったトーン",
  "strategy_note": "この文面の戦略的意図"
}}
"""
    raw = await run_claude(prompt)
    return _extract_json(raw)


async def generate_analytics_report(context: str, period: str) -> dict:
    """
    期待するJSONレスポンス:
    {
      "best_time_slot": "21:00-23:00 JST",
      "best_tone": "casual",
      "best_asset_type": "gif",
      "avoid_patterns": ["..."],
      "next_strategy": "...",
      "recommended_schedule": { "frequency": "週3回", "days": ["火","木","土"] }
    }
    """
    system = _load_prompt("system_analytics.txt")

    prompt = f"""{system}

## 分析対象期間: {period}

## ツイートデータ
{context}

---

## 出力形式
必ず以下のJSONのみを返すこと。

{{
  "best_time_slot": "最もエンゲージが高い時間帯",
  "best_tone": "最も効果的なトーン",
  "best_asset_type": "png | gif | none",
  "avoid_patterns": ["避けるべきパターン1", "..."],
  "next_strategy": "来月の宣伝戦略の提言（200字以内）",
  "recommended_schedule": {{
    "frequency": "週N回",
    "days": ["月", "水"]
  }}
}}
"""
    raw = await run_claude(prompt)
    return _extract_json(raw)
```

---

## `services/db.py`（主要関数）

```python
import aiosqlite
import json
from datetime import datetime, timedelta
from config import DB_PATH


async def init_db():
    """スキーマ初期化（bot起動時に呼ぶ）"""
    async with aiosqlite.connect(DB_PATH) as db:
        with open("schema.sql") as f:  # 上記DDLを schema.sql に保存
            await db.executescript(f.read())
        await db.commit()


# ---- games ----

async def add_game(data: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO games (id, name_ja, name_en, genre, platform, status,
                               steam_url, elevator_ja, elevator_en, hashtags,
                               target_audience, circle)
            VALUES (:id,:name_ja,:name_en,:genre,:platform,:status,
                    :steam_url,:elevator_ja,:elevator_en,:hashtags,
                    :target_audience,:circle)
        """, data)
        await db.commit()

async def get_game(game_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM games WHERE id=?", (game_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def list_games() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM games ORDER BY created_at DESC") as cur:
            return [dict(r) for r in await cur.fetchall()]


# ---- progress_logs ----

async def add_progress(data: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO progress_logs
                (game_id, log_date, milestone, content, appeal_note, excitement, tweetable)
            VALUES (:game_id,:log_date,:milestone,:content,:appeal_note,:excitement,:tweetable)
        """, data)
        await db.commit()

async def get_recent_progress(game_id: str, limit: int = 3) -> list[dict]:
    """未ツイート・tweetable=1 の最新N件"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM progress_logs
            WHERE game_id=? AND tweetable=1 AND tweeted=0
            ORDER BY log_date DESC LIMIT ?
        """, (game_id, limit)) as cur:
            return [dict(r) for r in await cur.fetchall()]

async def mark_progress_tweeted(progress_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE progress_logs SET tweeted=1 WHERE id=?", (progress_id,))
        await db.commit()


# ---- appeal_points ----

async def add_appeal(data: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO appeal_points (game_id, category, priority, title, content, promo_tips)
            VALUES (:game_id,:category,:priority,:title,:content,:promo_tips)
        """, data)
        await db.commit()

async def get_appeals(game_id: str, category: str = None, limit: int = 3) -> list[dict]:
    """優先度高・最近使っていないもの優先"""
    query = """
        SELECT * FROM appeal_points
        WHERE game_id=?
    """
    params = [game_id]
    if category:
        query += " AND category=?"
        params.append(category)
    query += " ORDER BY priority DESC, last_used_at ASC NULLS FIRST LIMIT ?"
    params.append(limit)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cur:
            return [dict(r) for r in await cur.fetchall()]

async def mark_appeal_used(appeal_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE appeal_points SET last_used_at=? WHERE id=?",
            (datetime.now().isoformat(), appeal_id)
        )
        await db.commit()


# ---- assets ----

async def add_asset(data: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO assets (game_id, filename, asset_type, description,
                                recommended_for, local_path, width, height)
            VALUES (:game_id,:filename,:asset_type,:description,
                    :recommended_for,:local_path,:width,:height)
        """, data)
        await db.commit()

async def get_assets(game_id: str, recommended_for: str = None) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM assets WHERE game_id=?"
        params = [game_id]
        if recommended_for:
            query += " AND (recommended_for=? OR recommended_for='any')"
            params.append(recommended_for)
        async with db.execute(query, params) as cur:
            return [dict(r) for r in await cur.fetchall()]


# ---- tweets ----

async def add_tweet(data: dict) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO tweets (tweet_id, game_id, lang, content, asset_id,
                                tone, strategy_note, posted_at, tweet_url, approved_by)
            VALUES (:tweet_id,:game_id,:lang,:content,:asset_id,
                    :tone,:strategy_note,:posted_at,:tweet_url,:approved_by)
        """, data)
        await db.commit()
        return cur.lastrowid

async def get_recent_tweets(game_id: str, days: int = 14) -> list[dict]:
    since = (datetime.now() - timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM tweets WHERE game_id=? AND posted_at > ?
            ORDER BY posted_at DESC
        """, (game_id, since)) as cur:
            return [dict(r) for r in await cur.fetchall()]

async def update_tweet_analytics(tweet_id: str, impressions: int, likes: int,
                                  retweets: int, replies: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE tweets SET impressions=?, likes=?, retweets=?, replies=?,
                              analytics_fetched_at=?
            WHERE tweet_id=?
        """, (impressions, likes, retweets, replies, datetime.now().isoformat(), tweet_id))
        await db.commit()


# ---- tweet_drafts ----

async def add_draft(data: dict) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO tweet_drafts
                (game_id, lang, content, asset_id, tone, strategy_note, asset_reason)
            VALUES (:game_id,:lang,:content,:asset_id,:tone,:strategy_note,:asset_reason)
        """, data)
        await db.commit()
        return cur.lastrowid

async def get_draft(draft_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tweet_drafts WHERE id=?", (draft_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def update_draft_status(draft_id: int, status: str, discord_msg_id: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tweet_drafts SET status=?, discord_msg_id=? WHERE id=?",
            (status, discord_msg_id, draft_id)
        )
        await db.commit()


# ---- LLM用コンテキスト構築 ----

async def build_promo_context(game_id: str, mode: str) -> str:
    """DBから情報を収集してLLMに渡すテキストを構築"""
    game     = await get_game(game_id)
    progress = await get_recent_progress(game_id, limit=3)
    appeals  = await get_appeals(game_id, category=None if mode == "random" else mode, limit=3)
    tweets   = await get_recent_tweets(game_id, days=14)
    assets   = await get_assets(game_id)

    hashtags = json.loads(game.get("hashtags") or "[]")

    ctx = f"""
### ゲーム基本情報
- ID: {game['id']}
- 名前: {game['name_ja']}（{game.get('name_en','')}）
- ジャンル: {game.get('genre','')}
- ステータス: {game.get('status','')}
- Steam URL: {game.get('steam_url','未定')}
- ハッシュタグ: {' '.join(hashtags)}
- ターゲット: {game.get('target_audience','')}
- エレベーターピッチ（日）: {game.get('elevator_ja','')}
- エレベーターピッチ（英）: {game.get('elevator_en','')}

### 最近の進捗（未ツイート・最新3件）
"""
    for p in progress:
        ctx += f"- [{p['log_date']}] {p['milestone'] or ''}: {p['content']}"
        if p.get('appeal_note'):
            ctx += f"（LLMへのヒント: {p['appeal_note']}）"
        ctx += f"  ※興奮度: {p['excitement']}/3\n"

    ctx += "\n### アピールポイント（優先度順）\n"
    for a in appeals:
        ctx += f"- [{a['category']}] {a['title']}: {a['content']}\n"
        if a.get('promo_tips'):
            ctx += f"  宣伝ヒント: {a['promo_tips']}\n"

    ctx += "\n### 直近14日のツイート（重複禁止）\n"
    for t in tweets:
        ctx += f"- {t['posted_at'][:10]}: {t['content'][:60]}...\n"

    ctx += "\n### 使用可能素材\n"
    for a in assets:
        ctx += f"- ID:{a['id']} [{a['asset_type']}] {a['filename']}: {a.get('description','')} （推奨用途: {a.get('recommended_for','')}）\n"

    return ctx
```

---

## `cogs/promo_cog.py`（メインコグ）

```python
import discord
from discord import app_commands
from discord.ext import commands
from services import db, llm, twitter
from config import ALLOWED_USER_IDS
import json


def is_allowed(interaction: discord.Interaction) -> bool:
    return interaction.user.id in ALLOWED_USER_IDS


class ApprovalView(discord.ui.View):
    """ツイート下書きの承認UI"""

    def __init__(self, draft_id: int, cog):
        super().__init__(timeout=3600)  # 1時間で期限切れ
        self.draft_id = draft_id
        self.cog = cog

    @discord.ui.button(label="✅ 承認して投稿", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_allowed(interaction):
            await interaction.response.send_message("権限がありません", ephemeral=True)
            return
        await interaction.response.defer()
        await self.cog.post_draft(interaction, self.draft_id)
        self.stop()

    @discord.ui.button(label="🔄 再生成", style=discord.ButtonStyle.primary)
    async def regenerate(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_allowed(interaction):
            await interaction.response.send_message("権限がありません", ephemeral=True)
            return
        await interaction.response.defer()
        draft = await db.get_draft(self.draft_id)
        await self.cog._generate_and_show(
            interaction, draft['game_id'],
            draft.get('tone','casual'), 'random', draft.get('lang','ja')
        )
        self.stop()

    @discord.ui.button(label="❌ キャンセル", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await db.update_draft_status(self.draft_id, "rejected")
        await interaction.response.send_message("キャンセルしました", ephemeral=True)
        self.stop()


class PromoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="promo_draft", description="ツイート下書きを生成する")
    @app_commands.describe(
        game_id="ゲームID",
        mode="progress / appeal / milestone / random",
        lang="ja / en / both",
        tone="excited / casual / technical / mysterious"
    )
    async def promo_draft(
        self, interaction: discord.Interaction,
        game_id: str,
        mode: str = "random",
        lang: str = "ja",
        tone: str = "casual"
    ):
        if not is_allowed(interaction):
            await interaction.response.send_message("権限がありません", ephemeral=True)
            return
        await interaction.response.defer()
        await self._generate_and_show(interaction, game_id, tone, mode, lang)

    async def _generate_and_show(self, interaction, game_id, tone, mode, lang):
        game = await db.get_game(game_id)
        if not game:
            await interaction.followup.send(f"❌ ゲーム `{game_id}` が見つかりません")
            return

        await interaction.followup.send(f"🎮 `{game_id}` のプロモツイートを生成中...")

        try:
            context = await db.build_promo_context(game_id, mode)
            result  = await llm.generate_promo_tweet(context, mode, lang, tone)
        except Exception as e:
            await interaction.followup.send(f"❌ 生成エラー: {e}")
            return

        # 素材情報の取得
        asset = None
        if result.get("recommended_asset_id"):
            assets = await db.get_assets(game_id)
            asset = next((a for a in assets if a["id"] == result["recommended_asset_id"]), None)

        # DB に下書き保存
        draft_id = await db.add_draft({
            "game_id":       game_id,
            "lang":          lang,
            "content":       result.get("tweet_ja") if lang == "ja" else result.get("tweet_en"),
            "asset_id":      result.get("recommended_asset_id"),
            "tone":          result.get("tone_used"),
            "strategy_note": result.get("strategy_note"),
            "asset_reason":  result.get("asset_reason"),
        })

        # Embed 作成
        embed = discord.Embed(title=f"📝 ツイート下書き #{draft_id}", color=0x1DA1F2)
        if lang in ("ja", "both"):
            embed.add_field(name="🇯🇵 日本語", value=result.get("tweet_ja", ""), inline=False)
        if lang in ("en", "both"):
            embed.add_field(name="🇺🇸 English", value=result.get("tweet_en", ""), inline=False)

        # ハッシュタグ
        game_data = await db.get_game(game_id)
        hashtags = json.loads(game_data.get("hashtags") or "[]")
        embed.add_field(name="🏷 ハッシュタグ", value=" ".join(hashtags), inline=False)

        if asset:
            embed.add_field(
                name="🖼 推奨素材",
                value=f"`{asset['filename']}`\n理由: {result.get('asset_reason','')}",
                inline=False
            )
        embed.add_field(name="📊 戦略メモ", value=result.get("strategy_note", ""), inline=False)

        view = ApprovalView(draft_id, self)
        await interaction.followup.send(embed=embed, view=view)

    async def post_draft(self, interaction: discord.Interaction, draft_id: int):
        """承認されたDraftをTwitterに投稿してDBに記録"""
        draft = await db.get_draft(draft_id)
        if not draft:
            await interaction.followup.send("❌ 下書きが見つかりません")
            return

        asset = None
        if draft.get("asset_id"):
            assets = await db.get_assets(draft["game_id"])
            asset = next((a for a in assets if a["id"] == draft["asset_id"]), None)

        try:
            tweet_id, tweet_url = await twitter.post_tweet(
                content=draft["content"],
                media_path=asset["local_path"] if asset else None,
                game_id=draft["game_id"]
            )
        except Exception as e:
            await interaction.followup.send(f"❌ 投稿エラー: {e}")
            return

        from datetime import datetime
        await db.add_tweet({
            "tweet_id":      tweet_id,
            "game_id":       draft["game_id"],
            "lang":          draft["lang"],
            "content":       draft["content"],
            "asset_id":      draft["asset_id"],
            "tone":          draft["tone"],
            "strategy_note": draft["strategy_note"],
            "posted_at":     datetime.now().isoformat(),
            "tweet_url":     tweet_url,
            "approved_by":   str(interaction.user.id),
        })
        await db.update_draft_status(draft_id, "approved")

        embed = discord.Embed(title="✅ 投稿完了", color=0x00FF00)
        embed.add_field(name="URL", value=tweet_url)
        embed.add_field(name="内容", value=draft["content"][:100], inline=False)
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(PromoCog(bot))
```

---

## `services/twitter.py`

```python
import tweepy
import asyncio
from config import (TWITTER_API_KEY, TWITTER_API_SECRET,
                    TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET,
                    TWITTER_BEARER_TOKEN)


def _get_client():
    return tweepy.Client(
        bearer_token=TWITTER_BEARER_TOKEN,
        consumer_key=TWITTER_API_KEY,
        consumer_secret=TWITTER_API_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_SECRET,
    )

def _get_api_v1():
    """メディアアップロード用（v1.1）"""
    auth = tweepy.OAuth1UserHandler(
        TWITTER_API_KEY, TWITTER_API_SECRET,
        TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
    )
    return tweepy.API(auth)


async def post_tweet(content: str, media_path: str = None, game_id: str = None) -> tuple[str, str]:
    """
    ツイートを投稿し (tweet_id, tweet_url) を返す。
    media_path が指定されていれば画像/GIFを添付。
    """
    def _post():
        client = _get_client()
        media_id = None

        if media_path:
            api_v1 = _get_api_v1()
            media = api_v1.media_upload(media_path)
            media_id = media.media_id

        resp = client.create_tweet(
            text=content,
            media_ids=[media_id] if media_id else None,
        )
        tweet_id = str(resp.data["id"])
        # ツイートURLはアカウントのusername取得後に組み立て（簡略化のためIDのみ使用）
        tweet_url = f"https://twitter.com/i/web/status/{tweet_id}"
        return tweet_id, tweet_url

    return await asyncio.get_event_loop().run_in_executor(None, _post)


async def fetch_tweet_metrics(tweet_ids: list[str]) -> list[dict]:
    """インプレッション等のメトリクスを取得（Academic Research or Basic Tier必要）"""
    def _fetch():
        client = _get_client()
        resp = client.get_tweets(
            ids=tweet_ids,
            tweet_fields=["public_metrics", "created_at"]
        )
        results = []
        for tweet in resp.data or []:
            m = tweet.public_metrics
            results.append({
                "tweet_id":    str(tweet.id),
                "impressions": m.get("impression_count", 0),
                "likes":       m.get("like_count", 0),
                "retweets":    m.get("retweet_count", 0),
                "replies":     m.get("reply_count", 0),
            })
        return results

    return await asyncio.get_event_loop().run_in_executor(None, _fetch)
```

---

## `cogs/analytics_cog.py`

```python
import discord
from discord import app_commands
from discord.ext import commands
from services import db, llm, twitter
from config import ALLOWED_USER_IDS
import json


class AnalyticsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="analytics_fetch", description="ツイートのインプレッションを取得")
    @app_commands.describe(game_id="ゲームID")
    async def analytics_fetch(self, interaction: discord.Interaction, game_id: str):
        if interaction.user.id not in ALLOWED_USER_IDS:
            await interaction.response.send_message("権限がありません", ephemeral=True)
            return
        await interaction.response.defer()

        tweets = await db.get_recent_tweets(game_id, days=90)
        unanalyzed = [t for t in tweets if t.get("analytics_fetched_at") is None and t.get("tweet_id")]

        if not unanalyzed:
            await interaction.followup.send("取得すべきツイートがありません")
            return

        metrics = await twitter.fetch_tweet_metrics([t["tweet_id"] for t in unanalyzed])
        for m in metrics:
            await db.update_tweet_analytics(**m)

        await interaction.followup.send(f"✅ {len(metrics)} 件のインプレッションを更新しました")

    @app_commands.command(name="analytics_report", description="宣伝活動の分析レポートを生成")
    @app_commands.describe(game_id="ゲームID", period="期間（例: 2026-04）")
    async def analytics_report(self, interaction: discord.Interaction,
                                game_id: str, period: str = None):
        if interaction.user.id not in ALLOWED_USER_IDS:
            await interaction.response.send_message("権限がありません", ephemeral=True)
            return
        await interaction.response.defer()

        from datetime import datetime
        if not period:
            period = datetime.now().strftime("%Y-%m")

        tweets = await db.get_recent_tweets(game_id, days=60)
        analyzed = [t for t in tweets if t.get("impressions") is not None]

        if not analyzed:
            await interaction.followup.send("分析できるデータが不足しています（先に `/analytics_fetch` を実行してください）")
            return

        context = "\n".join([
            f"- [{t['posted_at'][:10]}] tone:{t['tone']} impressions:{t['impressions']} "
            f"likes:{t['likes']} retweets:{t['retweets']} | {t['content'][:60]}"
            for t in analyzed
        ])

        await interaction.followup.send("📊 LLMで分析中...")
        result = await llm.generate_analytics_report(context, period)

        embed = discord.Embed(title=f"📊 分析レポート {game_id} / {period}", color=0xFFD700)
        embed.add_field(name="🕐 最適投稿時間帯", value=result.get("best_time_slot", "不明"), inline=True)
        embed.add_field(name="🎭 最適トーン",      value=result.get("best_tone", "不明"),       inline=True)
        embed.add_field(name="🖼 最適素材タイプ",  value=result.get("best_asset_type", "不明"), inline=True)
        embed.add_field(name="⚠️ 避けるべきパターン",
                        value="\n".join(result.get("avoid_patterns", [])), inline=False)
        embed.add_field(name="🚀 来月の戦略", value=result.get("next_strategy", ""), inline=False)
        schedule = result.get("recommended_schedule", {})
        embed.add_field(name="📅 推奨スケジュール",
                        value=f"{schedule.get('frequency','')} / {','.join(schedule.get('days',[]))}曜日",
                        inline=False)

        # DBに保存
        async with __import__('aiosqlite').connect(__import__('config').DB_PATH) as db_conn:
            await db_conn.execute("""
                INSERT INTO analytics_summaries
                    (game_id, period, best_time_slot, best_tone, best_asset_type, strategy_note, raw_analysis)
                VALUES (?,?,?,?,?,?,?)
            """, (game_id, period, result.get("best_time_slot"), result.get("best_tone"),
                  result.get("best_asset_type"), result.get("next_strategy"), json.dumps(result)))
            await db_conn.commit()

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="analytics_top", description="エンゲージメント上位ツイートを表示")
    @app_commands.describe(game_id="ゲームID", limit="表示件数（デフォルト5）")
    async def analytics_top(self, interaction: discord.Interaction, game_id: str, limit: int = 5):
        await interaction.response.defer()
        async with __import__('aiosqlite').connect(__import__('config').DB_PATH) as db_conn:
            db_conn.row_factory = __import__('aiosqlite').Row
            async with db_conn.execute("""
                SELECT *, CAST(likes + retweets AS FLOAT) / NULLIF(impressions, 0) as eng_rate
                FROM tweets WHERE game_id=? AND impressions IS NOT NULL
                ORDER BY eng_rate DESC LIMIT ?
            """, (game_id, limit)) as cur:
                rows = [dict(r) for r in await cur.fetchall()]

        embed = discord.Embed(title=f"🏆 エンゲージメント Top {limit} / {game_id}", color=0xFF6B35)
        for i, t in enumerate(rows, 1):
            rate = (t.get("eng_rate") or 0) * 100
            embed.add_field(
                name=f"#{i} {rate:.2f}% ❤️{t['likes']} 🔁{t['retweets']} 👁{t['impressions']}",
                value=f"{t['content'][:80]}\n[リンク]({t['tweet_url']})",
                inline=False
            )
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AnalyticsCog(bot))
```

---

## `prompts/system_promo.txt`

```
あなたはインディーゲームの宣伝専門のコピーライターです。
提供されたゲームデータを読み込み、Twitterに投稿するためのコンテンツを生成します。

## 絶対ルール
- 日本語ツイート：ハッシュタグを除いて140字以内
- 英語ツイート：ハッシュタグを除いて250字以内
- 絵文字は1〜3個まで
- 「直近14日のツイート」と内容・切り口が30%以上同じになってはいけない
- 発売日が未定の場合は確定的な日付に言及しない
- 未実装機能を実装済みのように断言しない
- 競合他社の名指し批判をしない

## 良いツイートの条件
- 最初の一文で興味を引く
- 具体的な数字や固有名詞を使う（「改善した」でなく「VFX Graphで作り直した」）
- 開発者の生の声・感情が伝わる
- 見た人が「いいね」したくなる終わり方

## 出力
JSONのみを返すこと。余分なテキスト不要。
```

---

## `prompts/brand_voice.txt`

```
## 開発者について
- 個人/小規模サークル「ねこのおでこ」のゲーム開発者
- Steamでの商業リリースを目指している
- Unity使用、VFX Graph・Shader Graphが得意
- 技術的な話題も気軽に話せるオープンなスタイル

## トーンの基準
- excited：開発の興奮・発見を素直に表現。感嘆符多め。
- casual：普段の会話のような親しみやすさ。押しつけがましくない。
- technical：技術的な詳細を誇りをもって語る。エンジニアに刺さる。
- mysterious：ゲームの世界観に引き込む。謎めかした表現。

## 禁止表現
- 「ぜひ」「是非」（古い印象）
- 「〜となっております」（丁寧すぎる）
- 過度な宣伝っぽさ（「今すぐチェック！」等）
```

---

## コマンド一覧（完成形）

| コマンド | 説明 |
|---|---|
| `/game_add` | ゲームをモーダルで登録 |
| `/game_list` | 登録ゲーム一覧表示 |
| `/progress_add <game_id>` | 進捗をモーダルで追加 |
| `/appeal_add <game_id>` | アピールポイントを追加 |
| `/asset_add <game_id>` | 素材ファイルを添付して登録 |
| `/promo_draft <game_id> [mode] [lang] [tone]` | ツイート下書き生成・承認UI表示 |
| `/analytics_fetch <game_id>` | インプレッションをTwitterから取得・DB更新 |
| `/analytics_report <game_id> [period]` | LLMで分析レポート生成 |
| `/analytics_top <game_id> [limit]` | エンゲージメント上位ツイート表示 |

---

## 実装優先順位

```
Phase 1（Week 1）: 基盤
  - schema.sql + services/db.py
  - bot.py + config.py
  - /game_add, /game_list, /progress_add

Phase 2（Week 2）: LLM連携
  - services/llm.py（claude --print subprocess）
  - prompts/*.txt
  - /promo_draft（承認UIまで）

Phase 3（Week 3）: Twitter投稿
  - services/twitter.py
  - 承認→投稿フローの完成
  - /asset_add

Phase 4（Week 4）: 分析ループ
  - /analytics_fetch
  - /analytics_report
  - /analytics_top
```

---

## 起動方法

```bash
# 依存インストール
pip install -r requirements.txt

# Claude CLIが使えるか確認
echo "「テスト」を英語にして。英語のみ返すこと。" | claude --print

# Bot起動
python bot.py
```
