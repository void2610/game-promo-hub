from __future__ import annotations

import unittest

from services import llm


class LlmParsingTests(unittest.TestCase):
    """LLM 出力のパース処理に関するユニットテスト。"""

    def test_extract_json_accepts_wrapped_payload(self) -> None:
        """前後に余分なテキストがあっても JSON を正しく抽出できることを確認する。"""
        payload = llm.extract_json("note\n{\"tweet_ja\":\"a\",\"tweet_en\":\"b\"}\nend")
        self.assertEqual(payload["tweet_ja"], "a")
        self.assertEqual(payload["tweet_en"], "b")

    def test_extract_json_rejects_missing_json(self) -> None:
        """JSON が含まれない文字列に対して ValueError が送出されることを確認する。"""
        with self.assertRaises(ValueError):
            llm.extract_json("plain text only")


if __name__ == "__main__":
    unittest.main()

