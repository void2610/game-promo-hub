from __future__ import annotations

import unittest

from services import llm


class LlmParsingTests(unittest.TestCase):
    def test_extract_json_accepts_wrapped_payload(self) -> None:
        payload = llm.extract_json("note\n{\"tweet_ja\":\"a\",\"tweet_en\":\"b\"}\nend")
        self.assertEqual(payload["tweet_ja"], "a")
        self.assertEqual(payload["tweet_en"], "b")

    def test_extract_json_rejects_missing_json(self) -> None:
        with self.assertRaises(ValueError):
            llm.extract_json("plain text only")


if __name__ == "__main__":
    unittest.main()

