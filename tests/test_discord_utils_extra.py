from __future__ import annotations

import unittest
import unittest.mock

import discord

from services.discord_utils import is_allowed_user


def _make_interaction(user_id: int | None) -> discord.Interaction:
    """テスト用の discord.Interaction モックを生成する。"""
    interaction = unittest.mock.MagicMock(spec=discord.Interaction)
    if user_id is None:
        interaction.user = None
    else:
        interaction.user = unittest.mock.MagicMock()
        interaction.user.id = user_id
    return interaction


class IsAllowedUserTests(unittest.TestCase):
    """is_allowed_user のユニットテスト。"""

    def test_allowed_user_returns_true(self) -> None:
        """許可リストに含まれるユーザーに対して True が返されることを確認する。"""
        with unittest.mock.patch("services.discord_utils.ALLOWED_USER_IDS", [111, 222, 333]):
            interaction = _make_interaction(222)
            self.assertTrue(is_allowed_user(interaction))

    def test_disallowed_user_returns_false(self) -> None:
        """許可リストに含まれないユーザーに対して False が返されることを確認する。"""
        with unittest.mock.patch("services.discord_utils.ALLOWED_USER_IDS", [111, 222]):
            interaction = _make_interaction(999)
            self.assertFalse(is_allowed_user(interaction))

    def test_none_user_returns_false(self) -> None:
        """interaction.user が None の場合に False が返されることを確認する。"""
        with unittest.mock.patch("services.discord_utils.ALLOWED_USER_IDS", [111]):
            interaction = _make_interaction(None)
            self.assertFalse(is_allowed_user(interaction))

    def test_empty_allowed_list_returns_false(self) -> None:
        """許可リストが空の場合に False が返されることを確認する。"""
        with unittest.mock.patch("services.discord_utils.ALLOWED_USER_IDS", []):
            interaction = _make_interaction(111)
            self.assertFalse(is_allowed_user(interaction))

    def test_first_user_in_list_allowed(self) -> None:
        """許可リストの最初のユーザー ID が許可されることを確認する。"""
        with unittest.mock.patch("services.discord_utils.ALLOWED_USER_IDS", [100, 200, 300]):
            interaction = _make_interaction(100)
            self.assertTrue(is_allowed_user(interaction))

    def test_last_user_in_list_allowed(self) -> None:
        """許可リストの最後のユーザー ID が許可されることを確認する。"""
        with unittest.mock.patch("services.discord_utils.ALLOWED_USER_IDS", [100, 200, 300]):
            interaction = _make_interaction(300)
            self.assertTrue(is_allowed_user(interaction))

    def test_user_id_zero_not_allowed(self) -> None:
        """ユーザー ID が 0 で許可リストに 0 がない場合に False が返されることを確認する。"""
        with unittest.mock.patch("services.discord_utils.ALLOWED_USER_IDS", [100, 200]):
            interaction = _make_interaction(0)
            self.assertFalse(is_allowed_user(interaction))


if __name__ == "__main__":
    unittest.main()
