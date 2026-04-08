from __future__ import annotations

import asyncio
from typing import Any

import tweepy

from config import (
    TWITTER_ACCESS_SECRET,
    TWITTER_ACCESS_TOKEN,
    TWITTER_API_KEY,
    TWITTER_API_SECRET,
    TWITTER_BEARER_TOKEN,
    validate_twitter_config,
)


def _get_client() -> tweepy.Client:
    validate_twitter_config()
    return tweepy.Client(
        bearer_token=TWITTER_BEARER_TOKEN,
        consumer_key=TWITTER_API_KEY,
        consumer_secret=TWITTER_API_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_SECRET,
    )


def _get_api_v1() -> tweepy.API:
    validate_twitter_config()
    auth = tweepy.OAuth1UserHandler(
        TWITTER_API_KEY,
        TWITTER_API_SECRET,
        TWITTER_ACCESS_TOKEN,
        TWITTER_ACCESS_SECRET,
    )
    return tweepy.API(auth)


async def post_tweet(
    content: str,
    media_path: str | None = None,
    game_id: str | None = None,
    reply_to_tweet_id: str | None = None,
) -> tuple[str, str]:
    def _post() -> tuple[str, str]:
        client = _get_client()
        media_ids: list[int] | None = None
        if media_path:
            api_v1 = _get_api_v1()
            media = api_v1.media_upload(media_path)
            media_ids = [media.media_id]

        response = client.create_tweet(
            text=content,
            media_ids=media_ids,
            in_reply_to_tweet_id=reply_to_tweet_id,
        )
        tweet_id = str(response.data["id"])
        return tweet_id, f"https://twitter.com/i/web/status/{tweet_id}"

    return await asyncio.to_thread(_post)


async def fetch_tweet_metrics(tweet_ids: list[str]) -> list[dict[str, Any]]:
    if not tweet_ids:
        return []

    def _fetch() -> list[dict[str, Any]]:
        client = _get_client()
        response = client.get_tweets(ids=tweet_ids, tweet_fields=["public_metrics", "created_at"])
        results: list[dict[str, Any]] = []
        for tweet in response.data or []:
            metrics = tweet.public_metrics or {}
            results.append(
                {
                    "tweet_id": str(tweet.id),
                    "impressions": int(metrics.get("impression_count", 0)),
                    "likes": int(metrics.get("like_count", 0)),
                    "retweets": int(metrics.get("retweet_count", 0)),
                    "replies": int(metrics.get("reply_count", 0)),
                }
            )
        return results

    return await asyncio.to_thread(_fetch)

