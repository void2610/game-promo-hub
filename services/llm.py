from __future__ import annotations

import asyncio
import json

from config import CLAUDE_TIMEOUT, PROMPTS_DIR


async def run_claude(prompt: str, timeout: int = CLAUDE_TIMEOUT) -> str:
    process = await asyncio.create_subprocess_exec(
        "claude",
        "--print",
        "--output-format",
        "text",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=prompt.encode("utf-8")),
            timeout=timeout,
        )
    except asyncio.TimeoutError as exc:
        process.kill()
        raise RuntimeError("Claude CLI timed out") from exc

    if process.returncode != 0:
        raise RuntimeError(f"Claude CLI failed: {stderr.decode('utf-8', errors='ignore').strip()}")

    text = stdout.decode("utf-8").strip()
    if not text:
        raise RuntimeError("Claude CLI returned an empty response")
    return text


def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def extract_json(raw: str) -> dict:
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start < 0 or end <= start:
        raise ValueError(f"JSON payload not found in Claude output: {raw[:200]}")
    return json.loads(raw[start:end])


async def generate_promo_tweet(context: str, mode: str, lang: str, tone: str) -> dict:
    prompt = f"""{_load_prompt("system_promo.txt")}

{_load_prompt("brand_voice.txt")}

---

## リクエスト
- モード: {mode}
- 言語: {lang}
- トーン: {tone}

## ゲームデータ
{context}

---

## 出力形式
必ず以下のJSONのみを返すこと。前置き・説明文・マークダウン記法は不要。

{{
  "tweet_ja": "日本語ツイート本文",
  "tweet_en": "English tweet body",
  "recommended_asset_id": null,
  "asset_reason": "素材の採用理由",
  "tone_used": "最終的に使ったトーン",
  "strategy_note": "文面の戦略意図"
}}
"""
    return extract_json(await run_claude(prompt))


async def generate_analytics_report(context: str, period: str) -> dict:
    prompt = f"""{_load_prompt("system_analytics.txt")}

## 分析対象期間: {period}

## ツイートデータ
{context}

---

## 出力形式
必ず以下のJSONのみを返すこと。

{{
  "best_time_slot": "最も強い時間帯",
  "best_tone": "最も効果的なトーン",
  "best_asset_type": "png | gif | mp4 | none",
  "avoid_patterns": ["避けるべき要素"],
  "next_strategy": "次の月に向けた提案",
  "recommended_schedule": {{
    "frequency": "週N回",
    "days": ["火", "木"]
  }}
}}
"""
    return extract_json(await run_claude(prompt))

