from __future__ import annotations

import unittest

from services.discord_utils import format_hashtags, parse_list_input


class ParseListInputTests(unittest.TestCase):
    """parse_list_input のユニットテスト。"""

    def test_comma_separated(self) -> None:
        """カンマ区切りの文字列が正しくリストに変換されることを確認する。"""
        self.assertEqual(parse_list_input("a, b, c"), ["a", "b", "c"])

    def test_newline_separated(self) -> None:
        """改行区切りの文字列が正しくリストに変換されることを確認する。"""
        self.assertEqual(parse_list_input("a\nb\nc"), ["a", "b", "c"])

    def test_zenkaku_comma(self) -> None:
        """全角読点で区切られた文字列が正しくリストに変換されることを確認する。"""
        self.assertEqual(parse_list_input("a、b、c"), ["a", "b", "c"])

    def test_mixed_delimiters(self) -> None:
        """カンマ・改行・全角読点の混在した文字列が正しく変換されることを確認する。"""
        self.assertEqual(parse_list_input("a,b\nc、d"), ["a", "b", "c", "d"])

    def test_strips_whitespace(self) -> None:
        """各要素の前後の空白が除去されることを確認する。"""
        self.assertEqual(parse_list_input("  foo  ,  bar  "), ["foo", "bar"])

    def test_empty_string(self) -> None:
        """空文字列に対して空リストが返されることを確認する。"""
        self.assertEqual(parse_list_input(""), [])

    def test_only_whitespace(self) -> None:
        """空白のみの文字列に対して空リストが返されることを確認する。"""
        self.assertEqual(parse_list_input("   "), [])

    def test_trailing_comma(self) -> None:
        """末尾のカンマが無視されて空要素が含まれないことを確認する。"""
        self.assertEqual(parse_list_input("a,b,"), ["a", "b"])


class FormatHashtagsTests(unittest.TestCase):
    """format_hashtags のユニットテスト。"""

    def test_joins_with_space(self) -> None:
        """ハッシュタグリストがスペース区切りで結合されることを確認する。"""
        self.assertEqual(format_hashtags(["#indiegame", "#gamedev"]), "#indiegame #gamedev")

    def test_empty_list_returns_dash(self) -> None:
        """空リストに対して "-" が返されることを確認する。"""
        self.assertEqual(format_hashtags([]), "-")

    def test_whitespace_only_tags_are_skipped(self) -> None:
        """空白のみのタグが除外されることを確認する。"""
        self.assertEqual(format_hashtags(["#gamedev", "  ", "#indiedev"]), "#gamedev #indiedev")

    def test_single_tag(self) -> None:
        """単一タグが正しく返されることを確認する。"""
        self.assertEqual(format_hashtags(["#gamedev"]), "#gamedev")

    def test_strips_tag_whitespace(self) -> None:
        """タグ自体の前後の空白が除去されることを確認する。"""
        self.assertEqual(format_hashtags(["  #gamedev  "]), "#gamedev")

    def test_all_empty_returns_dash(self) -> None:
        """すべてのタグが空白のみの場合に "-" が返されることを確認する。"""
        self.assertEqual(format_hashtags(["  ", ""]), "-")


if __name__ == "__main__":
    unittest.main()
