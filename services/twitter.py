from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from playwright.async_api import BrowserContext, Page, Response, async_playwright

from config import (
    TWITTER_PASSWORD,
    TWITTER_SESSION_PATH,
    TWITTER_USERNAME,
    validate_twitter_config,
)

LOGGER = logging.getLogger(__name__)

_X_LOGIN_URL = "https://x.com/i/flow/login"
_X_HOME_URL = "https://x.com/home"
_X_TWEET_URL = "https://x.com/i/web/status/{tweet_id}"
# CreateTweet レスポンスのポーリング最大試行回数（0.5 秒間隔で最大 15 秒待機）
_MAX_TWEET_RESPONSE_POLLS = 30

# モジュールレベルのシングルトン
_playwright_instance = None
_browser = None
_context: BrowserContext | None = None
_lock: asyncio.Lock | None = None


def _get_lock() -> asyncio.Lock:
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


async def _get_context() -> BrowserContext:
    """ブラウザコンテキストを取得または初期化する（非同期ロックで排他制御）。"""
    global _playwright_instance, _browser, _context

    async with _get_lock():
        if _context is not None:
            return _context

        validate_twitter_config()
        _playwright_instance = await async_playwright().start()
        _browser = await _playwright_instance.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        ctx_kwargs: dict[str, Any] = {
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "viewport": {"width": 1280, "height": 800},
            "locale": "ja-JP",
        }
        if TWITTER_SESSION_PATH.exists():
            try:
                ctx_kwargs["storage_state"] = json.loads(TWITTER_SESSION_PATH.read_text())
                LOGGER.info("Twitter セッションファイルを読み込みました: %s", TWITTER_SESSION_PATH)
            except Exception:
                LOGGER.warning("Twitter セッションファイルの読み込みに失敗しました。再ログインします。")
        _context = await _browser.new_context(**ctx_kwargs)
        return _context


async def _save_session(context: BrowserContext) -> None:
    """現在のブラウザセッション（クッキー等）をファイルに保存する。"""
    storage = await context.storage_state()
    TWITTER_SESSION_PATH.write_text(json.dumps(storage, ensure_ascii=False))
    LOGGER.info("Twitter セッションを保存しました: %s", TWITTER_SESSION_PATH)


async def _login(context: BrowserContext) -> None:
    """X/Twitter にユーザー名・パスワードでログインしてセッションを保存する。"""
    page = await context.new_page()
    try:
        await page.goto(_X_LOGIN_URL, wait_until="networkidle", timeout=30000)

        # ユーザー名入力
        username_input = page.locator('input[autocomplete="username"]')
        await username_input.wait_for(timeout=10000)
        await username_input.fill(TWITTER_USERNAME or "")
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(1500)

        # 「電話またはユーザー名の確認」ステップが挟まる場合に対応する
        try:
            confirm_input = page.locator('input[data-testid="ocfEnterTextTextInput"]')
            if await confirm_input.is_visible(timeout=2000):
                await confirm_input.fill(TWITTER_USERNAME or "")
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(1500)
        except Exception:
            pass

        # パスワード入力
        password_input = page.locator('input[name="password"]')
        await password_input.wait_for(timeout=10000)
        await password_input.fill(TWITTER_PASSWORD or "")
        await page.keyboard.press("Enter")

        # ホームページへの遷移を待つ（x.com 配下かつ flow でないページを確認する）
        await page.wait_for_url(
            lambda url: url.startswith("https://x.com/home") or (
                url.startswith("https://x.com/") and "flow" not in url
            ),
            timeout=20000,
        )
        await _save_session(context)
        LOGGER.info("X/Twitter へのログインに成功しました。")
    finally:
        await page.close()


async def _ensure_logged_in() -> BrowserContext:
    """ログイン状態を確認し、必要に応じて再ログインしてコンテキストを返す。"""
    context = await _get_context()
    page = await context.new_page()
    try:
        await page.goto(_X_HOME_URL, wait_until="domcontentloaded", timeout=20000)
        current_url = page.url
        if "login" in current_url or "i/flow" in current_url:
            LOGGER.info("セッションが切れています。再ログインします。")
            TWITTER_SESSION_PATH.unlink(missing_ok=True)
            await _login(context)
    finally:
        await page.close()
    return context


def _parse_count(text: str) -> int:
    """「1,234」「12K」「3.5M」などの数値テキストを整数に変換する。"""
    # \u306e は日本語の助詞「の」。X/Twitter の aria-label が「123 件の返信」のような形式になるため除去する
    text = text.strip().replace(",", "").replace("\u306e", "")
    if not text:
        return 0
    try:
        if text.upper().endswith("K"):
            return int(float(text[:-1]) * 1_000)
        if text.upper().endswith("M"):
            return int(float(text[:-1]) * 1_000_000)
        # 数字以外を除去して変換する
        digits = re.sub(r"[^\d]", "", text)
        return int(digits) if digits else 0
    except ValueError:
        return 0


async def _get_action_count(page: Page, action: str) -> int:
    """ツイートアクションボタン（reply / retweet / like）のカウントを取得する。"""
    try:
        btn = page.locator(f'[data-testid="{action}"]').first
        # aria-label から数値を抽出する（例: "123 件の返信" / "123 Replies"）
        aria_label = await btn.get_attribute("aria-label", timeout=5000)
        if aria_label:
            numbers = re.findall(r"[\d,]+", aria_label)
            if numbers:
                return _parse_count(numbers[0])
        # aria-label がない場合はボタン内スパンのテキストを使う
        span = btn.locator("span[data-testid='app-text-transition-container']")
        text = await span.inner_text(timeout=3000)
        return _parse_count(text)
    except Exception:
        return 0


def _extract_metrics_from_graphql(data: dict[str, Any], tweet_id: str) -> dict[str, Any] | None:
    """TweetDetail GraphQL レスポンスからメトリクスを抽出する。"""
    try:
        instructions = (
            data.get("data", {})
            .get("threaded_conversation_with_injections_v2", {})
            .get("instructions", [])
        )
        for instruction in instructions:
            for entry in instruction.get("entries", []):
                result = (
                    entry.get("content", {})
                    .get("itemContent", {})
                    .get("tweet_results", {})
                    .get("result", {})
                )
                if result.get("__typename") == "Tweet" and str(result.get("rest_id", "")) == tweet_id:
                    legacy = result.get("legacy", {})
                    views = result.get("views", {})
                    return {
                        "tweet_id": tweet_id,
                        "impressions": int(views.get("count", 0) or 0),
                        "likes": int(legacy.get("favorite_count", 0) or 0),
                        "retweets": int(legacy.get("retweet_count", 0) or 0),
                        "replies": int(legacy.get("reply_count", 0) or 0),
                    }
    except Exception:
        pass
    return None


async def _scrape_tweet_metrics(context: BrowserContext, tweet_id: str) -> dict[str, Any]:
    """単一ツイートのメトリクスをスクレイピングして辞書で返す。

    GraphQL レスポンス傍受を優先し、失敗した場合は DOM から取得する。
    """
    page = await context.new_page()
    graphql_result: dict[str, Any] | None = None

    async def handle_response(response: Response) -> None:
        nonlocal graphql_result
        if "TweetDetail" in response.url and graphql_result is None:
            try:
                body = await response.json()
                graphql_result = _extract_metrics_from_graphql(body, tweet_id)
            except Exception:
                pass

    page.on("response", handle_response)
    try:
        url = _X_TWEET_URL.format(tweet_id=tweet_id)
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        # GraphQL レスポンスが捌けるまで少し待機する
        await page.wait_for_timeout(2500)

        if graphql_result is not None:
            return graphql_result

        # GraphQL 取得に失敗した場合は DOM からフォールバック取得する
        LOGGER.warning("ツイート %s: GraphQL レスポンスが取得できなかったため DOM からフォールバック取得します", tweet_id)
        replies = await _get_action_count(page, "reply")
        retweets = await _get_action_count(page, "retweet")
        likes = await _get_action_count(page, "like")
        return {
            "tweet_id": tweet_id,
            "impressions": 0,
            "likes": likes,
            "retweets": retweets,
            "replies": replies,
        }
    finally:
        page.remove_listener("response", handle_response)
        await page.close()


async def post_tweet(
    content: str,
    media_path: str | None = None,
    game_id: str | None = None,
    reply_to_tweet_id: str | None = None,
) -> tuple[str, str]:
    """ツイートを投稿し、(tweet_id, tweet_url) を返す。

    Playwright でブラウザを操作して X/Twitter に投稿する。
    reply_to_tweet_id が指定された場合は、そのツイートへのリプライとして投稿する。
    """
    context = await _ensure_logged_in()
    page = await context.new_page()
    tweet_id_from_response: list[str] = []

    async def handle_create_tweet(response: Response) -> None:
        if "CreateTweet" in response.url and response.request.method == "POST":
            try:
                body = await response.json()
                tid = (
                    body.get("data", {})
                    .get("create_tweet", {})
                    .get("tweet_results", {})
                    .get("result", {})
                    .get("rest_id", "")
                )
                if tid:
                    tweet_id_from_response.append(str(tid))
            except Exception:
                pass

    page.on("response", handle_create_tweet)
    try:
        if reply_to_tweet_id:
            # リプライの場合：親ツイートページへ遷移してリプライボタンをクリックする
            await page.goto(
                _X_TWEET_URL.format(tweet_id=reply_to_tweet_id),
                wait_until="domcontentloaded",
                timeout=20000,
            )
            await page.wait_for_timeout(2000)
            reply_btn = page.locator('[data-testid="reply"]').first
            await reply_btn.click()
            await page.wait_for_timeout(1500)
        else:
            await page.goto("https://x.com/compose/tweet", wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(1500)

        # テキスト入力欄に本文を入力する
        text_area = page.locator('[data-testid="tweetTextarea_0"]')
        await text_area.wait_for(timeout=10000)
        await text_area.click()
        await text_area.type(content, delay=20)

        # メディアファイルを添付する
        if media_path:
            try:
                async with page.expect_file_chooser(timeout=5000) as fc_info:
                    media_btn = page.locator('[data-testid="attachments"]')
                    await media_btn.click()
                file_chooser = await fc_info.value
                await file_chooser.set_files(media_path)
                await page.wait_for_timeout(2000)
            except Exception:
                LOGGER.warning("メディアの添付に失敗しました: %s", media_path)

        # 投稿ボタンをクリックする（CreateTweet レスポンスからツイート ID を取得する）
        submit_btn = page.locator('[data-testid="tweetButtonInline"]')
        if not await submit_btn.is_visible(timeout=3000):
            submit_btn = page.locator('[data-testid="tweetButton"]')
        await submit_btn.click()

        # CreateTweet レスポンスを最大 15 秒待機する
        for _ in range(_MAX_TWEET_RESPONSE_POLLS):
            if tweet_id_from_response:
                break
            await asyncio.sleep(0.5)

        if not tweet_id_from_response:
            raise RuntimeError("CreateTweet レスポンスからツイート ID を取得できませんでした。")

        tweet_id = tweet_id_from_response[0]
        tweet_url = f"https://x.com/i/web/status/{tweet_id}"
        LOGGER.info("ツイート投稿成功: %s", tweet_url)
        return tweet_id, tweet_url
    finally:
        page.remove_listener("response", handle_create_tweet)
        await page.close()


async def fetch_tweet_metrics(tweet_ids: list[str]) -> list[dict[str, Any]]:
    """指定したツイート ID の公開メトリクス（Views・いいね・RT・リプライ）をスクレイピングで取得する。

    各ツイートのページを Playwright で巡回してメトリクスを収集する。
    取得失敗のツイートはゼロ値で返す。

    Returns:
        tweet_id, impressions (views), likes, retweets, replies を含む辞書のリスト。
    """
    if not tweet_ids:
        return []

    context = await _ensure_logged_in()
    results: list[dict[str, Any]] = []

    for tweet_id in tweet_ids:
        try:
            metrics = await _scrape_tweet_metrics(context, tweet_id)
            results.append(metrics)
        except Exception:
            LOGGER.exception("ツイート %s のメトリクス取得に失敗しました", tweet_id)
            results.append(
                {
                    "tweet_id": tweet_id,
                    "impressions": 0,
                    "likes": 0,
                    "retweets": 0,
                    "replies": 0,
                }
            )
        # レート制限を避けるための待機
        await asyncio.sleep(1)

    return results

