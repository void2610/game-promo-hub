from __future__ import annotations

import unittest

from services.twitter import _extract_metrics_from_graphql, _parse_count


class ParseCountTests(unittest.TestCase):
    """_parse_count のユニットテスト。"""

    def test_plain_integer(self) -> None:
        """プレーンな整数文字列が正しく変換されることを確認する。"""
        self.assertEqual(_parse_count("123"), 123)

    def test_comma_separated(self) -> None:
        """カンマ区切りの数値が正しく変換されることを確認する。"""
        self.assertEqual(_parse_count("1,234"), 1234)

    def test_k_suffix_integer(self) -> None:
        """「12K」が 12000 に変換されることを確認する。"""
        self.assertEqual(_parse_count("12K"), 12000)

    def test_k_suffix_decimal(self) -> None:
        """「3.5K」が 3500 に変換されることを確認する。"""
        self.assertEqual(_parse_count("3.5K"), 3500)

    def test_m_suffix_integer(self) -> None:
        """「2M」が 2000000 に変換されることを確認する。"""
        self.assertEqual(_parse_count("2M"), 2_000_000)

    def test_m_suffix_decimal(self) -> None:
        """「1.2M」が 1200000 に変換されることを確認する。"""
        self.assertEqual(_parse_count("1.2M"), 1_200_000)

    def test_lowercase_k(self) -> None:
        """小文字「k」でも正しく変換されることを確認する。"""
        self.assertEqual(_parse_count("5k"), 5000)

    def test_lowercase_m(self) -> None:
        """小文字「m」でも正しく変換されることを確認する。"""
        self.assertEqual(_parse_count("1m"), 1_000_000)

    def test_empty_string(self) -> None:
        """空文字列に対して 0 が返されることを確認する。"""
        self.assertEqual(_parse_count(""), 0)

    def test_whitespace_only(self) -> None:
        """空白のみの文字列に対して 0 が返されることを確認する。"""
        self.assertEqual(_parse_count("  "), 0)

    def test_japanese_aria_label(self) -> None:
        """日本語の「の」を含む aria-label 形式が正しく変換されることを確認する。"""
        # "123 件の返信" → "の" を除去 → "123 件返信" → 数字のみ抽出 → 123
        self.assertEqual(_parse_count("123 件の返信"), 123)

    def test_strips_surrounding_whitespace(self) -> None:
        """前後の空白が除去されて正しく変換されることを確認する。"""
        self.assertEqual(_parse_count("  42  "), 42)

    def test_zero_string(self) -> None:
        """「0」が 0 に変換されることを確認する。"""
        self.assertEqual(_parse_count("0"), 0)

    def test_non_numeric_returns_zero(self) -> None:
        """数字を含まない文字列に対して 0 が返されることを確認する。"""
        self.assertEqual(_parse_count("abc"), 0)


class ExtractMetricsFromGraphqlTests(unittest.TestCase):
    """_extract_metrics_from_graphql のユニットテスト。"""

    def _make_graphql_response(
        self,
        tweet_id: str,
        impressions: int = 0,
        likes: int = 0,
        retweets: int = 0,
        replies: int = 0,
    ) -> dict:
        """TweetDetail GraphQL レスポンスのダミーデータを生成するヘルパー。"""
        return {
            "data": {
                "threaded_conversation_with_injections_v2": {
                    "instructions": [
                        {
                            "entries": [
                                {
                                    "content": {
                                        "itemContent": {
                                            "tweet_results": {
                                                "result": {
                                                    "__typename": "Tweet",
                                                    "rest_id": tweet_id,
                                                    "legacy": {
                                                        "favorite_count": likes,
                                                        "retweet_count": retweets,
                                                        "reply_count": replies,
                                                    },
                                                    "views": {
                                                        "count": str(impressions),
                                                    },
                                                }
                                            }
                                        }
                                    }
                                }
                            ]
                        }
                    ]
                }
            }
        }

    def test_extracts_all_metrics(self) -> None:
        """メトリクスがすべて正しく抽出されることを確認する。"""
        data = self._make_graphql_response(
            tweet_id="12345",
            impressions=1000,
            likes=50,
            retweets=10,
            replies=5,
        )
        result = _extract_metrics_from_graphql(data, "12345")
        self.assertIsNotNone(result)
        self.assertEqual(result["tweet_id"], "12345")
        self.assertEqual(result["impressions"], 1000)
        self.assertEqual(result["likes"], 50)
        self.assertEqual(result["retweets"], 10)
        self.assertEqual(result["replies"], 5)

    def test_returns_none_for_wrong_tweet_id(self) -> None:
        """ツイート ID が一致しない場合に None が返されることを確認する。"""
        data = self._make_graphql_response(tweet_id="99999", impressions=100)
        result = _extract_metrics_from_graphql(data, "12345")
        self.assertIsNone(result)

    def test_returns_none_for_empty_data(self) -> None:
        """空の辞書に対して None が返されることを確認する。"""
        result = _extract_metrics_from_graphql({}, "12345")
        self.assertIsNone(result)

    def test_returns_none_when_not_tweet_typename(self) -> None:
        """__typename が 'Tweet' でない場合に None が返されることを確認する。"""
        data = {
            "data": {
                "threaded_conversation_with_injections_v2": {
                    "instructions": [
                        {
                            "entries": [
                                {
                                    "content": {
                                        "itemContent": {
                                            "tweet_results": {
                                                "result": {
                                                    "__typename": "TweetWithVisibilityResults",
                                                    "rest_id": "12345",
                                                }
                                            }
                                        }
                                    }
                                }
                            ]
                        }
                    ]
                }
            }
        }
        result = _extract_metrics_from_graphql(data, "12345")
        self.assertIsNone(result)

    def test_zero_values_returned_correctly(self) -> None:
        """メトリクスがすべて 0 の場合でも正しく返されることを確認する。"""
        data = self._make_graphql_response(tweet_id="0", impressions=0, likes=0, retweets=0, replies=0)
        result = _extract_metrics_from_graphql(data, "0")
        self.assertIsNotNone(result)
        self.assertEqual(result["impressions"], 0)
        self.assertEqual(result["likes"], 0)

    def test_multiple_entries_finds_correct_tweet(self) -> None:
        """複数のエントリが存在する場合に正しいツイートのメトリクスを返すことを確認する。"""
        data = {
            "data": {
                "threaded_conversation_with_injections_v2": {
                    "instructions": [
                        {
                            "entries": [
                                {
                                    "content": {
                                        "itemContent": {
                                            "tweet_results": {
                                                "result": {
                                                    "__typename": "Tweet",
                                                    "rest_id": "111",
                                                    "legacy": {
                                                        "favorite_count": 1,
                                                        "retweet_count": 0,
                                                        "reply_count": 0,
                                                    },
                                                    "views": {"count": "10"},
                                                }
                                            }
                                        }
                                    }
                                },
                                {
                                    "content": {
                                        "itemContent": {
                                            "tweet_results": {
                                                "result": {
                                                    "__typename": "Tweet",
                                                    "rest_id": "222",
                                                    "legacy": {
                                                        "favorite_count": 99,
                                                        "retweet_count": 5,
                                                        "reply_count": 3,
                                                    },
                                                    "views": {"count": "500"},
                                                }
                                            }
                                        }
                                    }
                                },
                            ]
                        }
                    ]
                }
            }
        }
        result = _extract_metrics_from_graphql(data, "222")
        self.assertIsNotNone(result)
        self.assertEqual(result["likes"], 99)
        self.assertEqual(result["impressions"], 500)

    def test_handles_missing_views_count(self) -> None:
        """views.count が存在しない場合に impressions が 0 になることを確認する。"""
        data = {
            "data": {
                "threaded_conversation_with_injections_v2": {
                    "instructions": [
                        {
                            "entries": [
                                {
                                    "content": {
                                        "itemContent": {
                                            "tweet_results": {
                                                "result": {
                                                    "__typename": "Tweet",
                                                    "rest_id": "789",
                                                    "legacy": {
                                                        "favorite_count": 10,
                                                        "retweet_count": 2,
                                                        "reply_count": 1,
                                                    },
                                                    "views": {},
                                                }
                                            }
                                        }
                                    }
                                }
                            ]
                        }
                    ]
                }
            }
        }
        result = _extract_metrics_from_graphql(data, "789")
        self.assertIsNotNone(result)
        self.assertEqual(result["impressions"], 0)
        self.assertEqual(result["likes"], 10)


if __name__ == "__main__":
    unittest.main()
