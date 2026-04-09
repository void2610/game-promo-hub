from __future__ import annotations

import unittest

import config


class RequireEnvTests(unittest.TestCase):
    """require_env のユニットテスト。"""

    def test_returns_value_when_set(self) -> None:
        """値が設定されている場合にその値がそのまま返されることを確認する。"""
        self.assertEqual(config.require_env("TEST_VAR", "hello"), "hello")

    def test_raises_when_none(self) -> None:
        """値が None の場合に RuntimeError が送出されることを確認する。"""
        with self.assertRaises(RuntimeError) as ctx:
            config.require_env("MISSING_VAR", None)
        self.assertIn("MISSING_VAR", str(ctx.exception))

    def test_raises_when_empty_string(self) -> None:
        """値が空文字列の場合に RuntimeError が送出されることを確認する。"""
        with self.assertRaises(RuntimeError) as ctx:
            config.require_env("EMPTY_VAR", "")
        self.assertIn("EMPTY_VAR", str(ctx.exception))

    def test_error_message_includes_variable_name(self) -> None:
        """エラーメッセージに変数名が含まれることを確認する。"""
        with self.assertRaises(RuntimeError) as ctx:
            config.require_env("MY_SECRET_KEY", None)
        self.assertIn("MY_SECRET_KEY", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
