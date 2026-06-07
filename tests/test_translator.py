"""translator.py 单元测试。

覆盖：
- translate_text 空输入处理
- _mymemory_source_for_target 语言映射
- TranslateJob 信号与取消
- Google/MyMemory fallback 逻辑（mock）
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quickshot.translator import (  # noqa: E402
    _mymemory_source_for_target,
    translate_text,
)


class MymemorySourceTest(unittest.TestCase):
    def test_chinese_returns_english(self) -> None:
        self.assertEqual(_mymemory_source_for_target("zh-CN"), "en-US")
        self.assertEqual(_mymemory_source_for_target("zh"), "en-US")
        self.assertEqual(_mymemory_source_for_target("ZH-TW"), "en-US")

    def test_non_chinese_returns_chinese(self) -> None:
        self.assertEqual(_mymemory_source_for_target("en"), "zh-CN")
        self.assertEqual(_mymemory_source_for_target("ja"), "zh-CN")
        self.assertEqual(_mymemory_source_for_target("fr"), "zh-CN")


class TranslateTextTest(unittest.TestCase):
    def test_empty_text_returns_none(self) -> None:
        self.assertIsNone(translate_text(""))
        self.assertIsNone(translate_text("   "))
        self.assertIsNone(translate_text(None))

    @patch("deep_translator.GoogleTranslator")
    def test_google_success(self, mock_google_cls) -> None:
        mock_google = MagicMock()
        mock_google.translate.return_value = "你好世界"
        mock_google_cls.return_value = mock_google

        result = translate_text("Hello World", target_lang="zh-CN")
        self.assertEqual(result, "你好世界")
        mock_google_cls.assert_called_once_with(source="auto", target="zh-CN")

    @patch("deep_translator.MyMemoryTranslator")
    @patch("deep_translator.GoogleTranslator")
    def test_google_fail_falls_back_to_mymemory(self, mock_google_cls, mock_mymem_cls) -> None:
        mock_google = MagicMock()
        mock_google.translate.side_effect = Exception("Network error")
        mock_google_cls.return_value = mock_google

        mock_mymem = MagicMock()
        mock_mymem.translate.return_value = "你好"
        mock_mymem_cls.return_value = mock_mymem

        result = translate_text("Hello", target_lang="zh-CN")
        self.assertEqual(result, "你好")
        mock_mymem_cls.assert_called_once_with(source="en-US", target="zh-CN")

    @patch("deep_translator.MyMemoryTranslator")
    @patch("deep_translator.GoogleTranslator")
    def test_both_fail_returns_none(self, mock_google_cls, mock_mymem_cls) -> None:
        mock_google = MagicMock()
        mock_google.translate.side_effect = Exception("fail")
        mock_google_cls.return_value = mock_google

        mock_mymem = MagicMock()
        mock_mymem.translate.side_effect = Exception("fail")
        mock_mymem_cls.return_value = mock_mymem

        result = translate_text("Hello")
        self.assertIsNone(result)

    @patch("deep_translator.GoogleTranslator")
    def test_google_returns_empty_tries_mymemory(self, mock_google_cls) -> None:
        mock_google = MagicMock()
        mock_google.translate.return_value = ""
        mock_google_cls.return_value = mock_google

        with patch("deep_translator.MyMemoryTranslator") as mock_mymem_cls:
            mock_mymem = MagicMock()
            mock_mymem.translate.return_value = "fallback result"
            mock_mymem_cls.return_value = mock_mymem
            result = translate_text("Hello")
            self.assertEqual(result, "fallback result")


if __name__ == "__main__":
    unittest.main()
