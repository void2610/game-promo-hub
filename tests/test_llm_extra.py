from __future__ import annotations

import unittest

from services import llm


class ExtractJsonEdgeCaseTests(unittest.TestCase):
    """extract_json の追加エッジケーステスト。"""

    def test_nested_json_object(self) -> None:
        """ネストされた JSON オブジェクトが正しく抽出されることを確認する。"""
        raw = '{"outer": {"inner": "value"}, "count": 3}'
        result = llm.extract_json(raw)
        self.assertEqual(result["outer"]["inner"], "value")
        self.assertEqual(result["count"], 3)

    def test_json_with_surrounding_text(self) -> None:
        """JSON の前後にテキストがあっても正しく抽出されることを確認する。"""
        raw = 'Some prefix text\n{"key": "hello"}\nSome suffix text'
        result = llm.extract_json(raw)
        self.assertEqual(result["key"], "hello")

    def test_json_with_array_value(self) -> None:
        """値に配列を含む JSON が正しく抽出されることを確認する。"""
        raw = '{"avoid_patterns": ["long text", "no images"], "score": 5}'
        result = llm.extract_json(raw)
        self.assertIsInstance(result["avoid_patterns"], list)
        self.assertEqual(len(result["avoid_patterns"]), 2)

    def test_json_with_null_value(self) -> None:
        """null 値を含む JSON が正しく抽出されることを確認する。"""
        raw = '{"recommended_asset_id": null, "tone": "excited"}'
        result = llm.extract_json(raw)
        self.assertIsNone(result["recommended_asset_id"])
        self.assertEqual(result["tone"], "excited")

    def test_json_with_unicode(self) -> None:
        """日本語を含む JSON が正しく抽出されることを確認する。"""
        raw = '{"tweet_ja": "面白いゲームです！", "tweet_en": "It is a fun game!"}'
        result = llm.extract_json(raw)
        self.assertEqual(result["tweet_ja"], "面白いゲームです！")

    def test_raises_for_empty_string(self) -> None:
        """空文字列に対して ValueError が送出されることを確認する。"""
        with self.assertRaises(ValueError):
            llm.extract_json("")

    def test_raises_for_no_braces(self) -> None:
        """波括弧を含まない文字列に対して ValueError が送出されることを確認する。"""
        with self.assertRaises(ValueError):
            llm.extract_json("no json here at all")

    def test_raises_for_only_opening_brace(self) -> None:
        """開き波括弧のみで閉じ波括弧がない場合に ValueError または json.JSONDecodeError が送出されることを確認する。"""
        import json

        with self.assertRaises((ValueError, json.JSONDecodeError)):
            llm.extract_json("{ no closing brace")

    def test_uses_outermost_braces(self) -> None:
        """最初の '{' から最後の '}' までを JSON として解釈することを確認する。"""
        raw = 'text {"a": {"b": "c"}} more text'
        result = llm.extract_json(raw)
        self.assertEqual(result["a"]["b"], "c")

    def test_boolean_values(self) -> None:
        """真偽値を含む JSON が正しく解釈されることを確認する。"""
        raw = '{"success": true, "failed": false}'
        result = llm.extract_json(raw)
        self.assertTrue(result["success"])
        self.assertFalse(result["failed"])


if __name__ == "__main__":
    unittest.main()
