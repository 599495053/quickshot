"""hotkey_util 快捷键解析工具测试。

覆盖 hotkey_util.py 中的快捷键字符串解析逻辑。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quickshot.hotkey_util import (  # noqa: E402
    format_hotkey_string,
    get_vk_poll_codes,
    parse_hotkey_string,
    validate_hotkey,
)


class ParseHotkeyStringTest(unittest.TestCase):

    def test_ctrl_a(self) -> None:
        result = parse_hotkey_string("Ctrl+A")
        self.assertIsNotNone(result)
        mods, vk = result
        self.assertNotEqual(mods, 0)
        self.assertNotEqual(vk, 0)

    def test_shift_a(self) -> None:
        result = parse_hotkey_string("Shift+A")
        self.assertIsNotNone(result)

    def test_alt_a(self) -> None:
        result = parse_hotkey_string("Alt+A")
        self.assertIsNotNone(result)

    def test_ctrl_shift_a(self) -> None:
        result = parse_hotkey_string("Ctrl+Shift+A")
        self.assertIsNotNone(result)
        mods, vk = result
        self.assertNotEqual(mods, 0)

    def test_empty_string(self) -> None:
        self.assertIsNone(parse_hotkey_string(""))

    def test_single_key_no_modifier(self) -> None:
        # 单独一个按键没有修饰键，应该返回 None
        self.assertIsNone(parse_hotkey_string("A"))

    def test_f_keys(self) -> None:
        for i in range(1, 13):
            result = parse_hotkey_string(f"Ctrl+F{i}")
            self.assertIsNotNone(result, f"Ctrl+F{i} should parse")

    def test_number_keys(self) -> None:
        for ch in "0123456789":
            result = parse_hotkey_string(f"Ctrl+{ch}")
            self.assertIsNotNone(result, f"Ctrl+{ch} should parse")

    def test_case_insensitive_modifiers(self) -> None:
        # 修饰键首字母大写，按键不区分大小写
        r1 = parse_hotkey_string("Ctrl+A")
        r2 = parse_hotkey_string("Ctrl+a")
        # 两者都应该成功解析
        self.assertIsNotNone(r1)
        self.assertIsNotNone(r2)


class FormatHotkeyStringTest(unittest.TestCase):

    def test_roundtrip(self) -> None:
        result = parse_hotkey_string("Ctrl+Shift+A")
        self.assertIsNotNone(result)
        mods, vk = result
        formatted = format_hotkey_string(mods, vk)
        self.assertIn("Ctrl", formatted)
        self.assertIn("Shift", formatted)


class ValidateHotkeyTest(unittest.TestCase):

    def test_valid(self) -> None:
        ok, err = validate_hotkey("Ctrl+A")
        self.assertTrue(ok)
        self.assertEqual(err, "")

    def test_empty(self) -> None:
        ok, err = validate_hotkey("")
        self.assertFalse(ok)

    def test_no_modifier(self) -> None:
        ok, err = validate_hotkey("A")
        self.assertFalse(ok)


class PollHotkeyCodesTest(unittest.TestCase):

    def test_modifier_codes_are_grouped_by_modifier(self) -> None:
        groups, vk = get_vk_poll_codes("Ctrl+Shift+A")
        self.assertEqual(vk, 0x41)
        self.assertIn([0x11, 0xA2, 0xA3], groups)
        self.assertIn([0x10, 0xA0, 0xA1], groups)


if __name__ == "__main__":
    unittest.main()
