from __future__ import annotations

import unittest
import unittest.mock

import config


class ValidateTwitterConfigTests(unittest.TestCase):
    """validate_twitter_config のユニットテスト。"""

    def test_passes_when_both_set(self) -> None:
        """TWITTER_USERNAME と TWITTER_PASSWORD が両方設定されている場合に例外が発生しないことを確認する。"""
        with (
            unittest.mock.patch.object(config, "TWITTER_USERNAME", "user"),
            unittest.mock.patch.object(config, "TWITTER_PASSWORD", "pass"),
        ):
            config.validate_twitter_config()  # 例外が発生しないことを確認

    def test_raises_when_username_missing(self) -> None:
        """TWITTER_USERNAME が未設定の場合に RuntimeError が送出されることを確認する。"""
        with (
            unittest.mock.patch.object(config, "TWITTER_USERNAME", None),
            unittest.mock.patch.object(config, "TWITTER_PASSWORD", "pass"),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                config.validate_twitter_config()
            self.assertIn("TWITTER_USERNAME", str(ctx.exception))

    def test_raises_when_password_missing(self) -> None:
        """TWITTER_PASSWORD が未設定の場合に RuntimeError が送出されることを確認する。"""
        with (
            unittest.mock.patch.object(config, "TWITTER_USERNAME", "user"),
            unittest.mock.patch.object(config, "TWITTER_PASSWORD", None),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                config.validate_twitter_config()
            self.assertIn("TWITTER_PASSWORD", str(ctx.exception))

    def test_raises_when_username_empty(self) -> None:
        """TWITTER_USERNAME が空文字列の場合に RuntimeError が送出されることを確認する。"""
        with (
            unittest.mock.patch.object(config, "TWITTER_USERNAME", ""),
            unittest.mock.patch.object(config, "TWITTER_PASSWORD", "pass"),
        ):
            with self.assertRaises(RuntimeError):
                config.validate_twitter_config()

    def test_raises_when_both_missing(self) -> None:
        """両方が未設定の場合に RuntimeError が送出されることを確認する。"""
        with (
            unittest.mock.patch.object(config, "TWITTER_USERNAME", None),
            unittest.mock.patch.object(config, "TWITTER_PASSWORD", None),
        ):
            with self.assertRaises(RuntimeError):
                config.validate_twitter_config()


class ValidateDiscordConfigTests(unittest.TestCase):
    """validate_discord_config のユニットテスト。"""

    def test_passes_when_all_set(self) -> None:
        """すべての Discord 設定が正しく設定されている場合に例外が発生しないことを確認する。"""
        with (
            unittest.mock.patch.object(config, "DISCORD_TOKEN", "token-xyz"),
            unittest.mock.patch.object(config, "DISCORD_GUILD_ID", 12345),
            unittest.mock.patch.object(config, "ALLOWED_USER_IDS", [99]),
        ):
            config.validate_discord_config()  # 例外が発生しないことを確認

    def test_raises_when_token_missing(self) -> None:
        """DISCORD_TOKEN が未設定の場合に RuntimeError が送出されることを確認する。"""
        with (
            unittest.mock.patch.object(config, "DISCORD_TOKEN", None),
            unittest.mock.patch.object(config, "DISCORD_GUILD_ID", 12345),
            unittest.mock.patch.object(config, "ALLOWED_USER_IDS", [99]),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                config.validate_discord_config()
            self.assertIn("DISCORD_TOKEN", str(ctx.exception))

    def test_raises_when_guild_id_missing(self) -> None:
        """DISCORD_GUILD_ID が未設定（None/0）の場合に RuntimeError が送出されることを確認する。"""
        with (
            unittest.mock.patch.object(config, "DISCORD_TOKEN", "token-xyz"),
            unittest.mock.patch.object(config, "DISCORD_GUILD_ID", None),
            unittest.mock.patch.object(config, "ALLOWED_USER_IDS", [99]),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                config.validate_discord_config()
            self.assertIn("DISCORD_GUILD_ID", str(ctx.exception))

    def test_raises_when_guild_id_zero(self) -> None:
        """DISCORD_GUILD_ID が 0 の場合に RuntimeError が送出されることを確認する。"""
        with (
            unittest.mock.patch.object(config, "DISCORD_TOKEN", "token-xyz"),
            unittest.mock.patch.object(config, "DISCORD_GUILD_ID", 0),
            unittest.mock.patch.object(config, "ALLOWED_USER_IDS", [99]),
        ):
            with self.assertRaises(RuntimeError):
                config.validate_discord_config()

    def test_raises_when_allowed_users_empty(self) -> None:
        """ALLOWED_USER_IDS が空の場合に RuntimeError が送出されることを確認する。"""
        with (
            unittest.mock.patch.object(config, "DISCORD_TOKEN", "token-xyz"),
            unittest.mock.patch.object(config, "DISCORD_GUILD_ID", 12345),
            unittest.mock.patch.object(config, "ALLOWED_USER_IDS", []),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                config.validate_discord_config()
            self.assertIn("ALLOWED_USER_IDS", str(ctx.exception))

    def test_raises_when_token_empty(self) -> None:
        """DISCORD_TOKEN が空文字列の場合に RuntimeError が送出されることを確認する。"""
        with (
            unittest.mock.patch.object(config, "DISCORD_TOKEN", ""),
            unittest.mock.patch.object(config, "DISCORD_GUILD_ID", 12345),
            unittest.mock.patch.object(config, "ALLOWED_USER_IDS", [99]),
        ):
            with self.assertRaises(RuntimeError):
                config.validate_discord_config()


if __name__ == "__main__":
    unittest.main()
