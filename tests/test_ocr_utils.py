"""OCR 工具函数测试。

覆盖 ocr.py 中的关键纯函数分支：
- normalize_ocr_symbols: 全角→半角符号转换
- has_cjk: CJK 字符检测
- should_join_with_space: 空格拼接判断
- format_rapidocr_result: RapidOCR 结果格式化
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quickshot.ocr import (
    clean_ocr_text,
    detect_privacy_info,
    deep_clean_ocr_text,
    extract_numbers,
    extract_chinese,
    format_rapidocr_result,
    has_cjk,
    normalize_ocr_symbols,
    should_join_with_space,
)
from PyQt6.QtGui import QImage


class NormalizeOcrSymbolsTest(unittest.TestCase):

    def test_fullwidth_comma(self) -> None:
        self.assertEqual(normalize_ocr_symbols("，"), ",")

    def test_fullwidth_period(self) -> None:
        self.assertEqual(normalize_ocr_symbols("。"), ".")

    def test_fullwidth_parens(self) -> None:
        self.assertEqual(normalize_ocr_symbols("（）"), "()")

    def test_non_breaking_space(self) -> None:
        self.assertEqual(normalize_ocr_symbols("a\u00a0b"), "a b")

    def test_mixed_text(self) -> None:
        result = normalize_ocr_symbols("你好，世界！")
        self.assertEqual(result, "你好,世界!")

    def test_empty_string(self) -> None:
        self.assertEqual(normalize_ocr_symbols(""), "")

    def test_ascii_passthrough(self) -> None:
        self.assertEqual(normalize_ocr_symbols("hello"), "hello")


class HasCjkTest(unittest.TestCase):

    def test_chinese_char(self) -> None:
        self.assertTrue(has_cjk("中"))

    def test_japanese_hiragana(self) -> None:
        self.assertFalse(has_cjk("ぁ"))

    def test_ascii_only(self) -> None:
        self.assertFalse(has_cjk("hello"))

    def test_empty(self) -> None:
        self.assertFalse(has_cjk(""))

    def test_mixed(self) -> None:
        self.assertTrue(has_cjk("hello中world"))


class ShouldJoinWithSpaceTest(unittest.TestCase):

    def test_empty_previous(self) -> None:
        self.assertFalse(should_join_with_space("", "hello", 10.0, 20.0))

    def test_empty_current(self) -> None:
        self.assertFalse(should_join_with_space("hello", "", 10.0, 20.0))

    def test_cjk_adjacent_no_space(self) -> None:
        self.assertFalse(should_join_with_space("中", "国", 15.0, 20.0))

    def test_latin_with_large_gap(self) -> None:
        self.assertTrue(should_join_with_space("hello", "world", 15.0, 20.0))

    def test_latin_with_small_gap(self) -> None:
        self.assertFalse(should_join_with_space("hello", "world", 2.0, 20.0))

    def test_punctuation_no_space(self) -> None:
        self.assertFalse(should_join_with_space("hello", ",world", 15.0, 20.0))
        self.assertFalse(should_join_with_space("hello(", "test", 15.0, 20.0))


class FormatRapidocrResultTest(unittest.TestCase):

    def test_empty_result(self) -> None:
        self.assertEqual(format_rapidocr_result([]), "")
        self.assertEqual(format_rapidocr_result(None), "")

    def test_single_block(self) -> None:
        result = [
            [[10, 10], [100, 10], [100, 30], [10, 30]], "Hello"
        ]
        self.assertEqual(format_rapidocr_result([result]), "Hello")

    def test_two_blocks_same_line(self) -> None:
        result = [
            [[[10, 10], [60, 10], [60, 30], [10, 30]], "Hello"],
            [[[70, 10], [130, 10], [130, 30], [70, 30]], "World"],
        ]
        text = format_rapidocr_result(result)
        self.assertIn("Hello", text)
        self.assertIn("World", text)

    def test_two_blocks_different_lines(self) -> None:
        result = [
            [[[10, 10], [100, 10], [100, 30], [10, 30]], "Line1"],
            [[[10, 60], [100, 60], [100, 80], [10, 80]], "Line2"],
        ]
        text = format_rapidocr_result(result)
        self.assertIn("Line1", text)
        self.assertIn("Line2", text)
        self.assertIn("\n", text)

    def test_malformed_box_skipped(self) -> None:
        result = [
            [[[10, 10], [100, 10], [100, 30], [10, 30]], "Good"],
            [[], "Bad"],
        ]
        text = format_rapidocr_result(result)
        self.assertEqual(text, "Good")

    def test_empty_text_skipped(self) -> None:
        result = [
            [[[10, 10], [100, 10], [100, 30], [10, 30]], "  "],
            [[[10, 60], [100, 60], [100, 80], [10, 80]], "OK"],
        ]
        text = format_rapidocr_result(result)
        self.assertEqual(text, "OK")


class CleanOcrTextTest(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(clean_ocr_text(""), "")

    def test_strip_lines(self):
        self.assertEqual(clean_ocr_text("  hello  \n  world  "), "hello\nworld")

    def test_merge_empty_lines(self):
        self.assertEqual(clean_ocr_text("a\n\n\n\nb"), "a\n\nb")

    def test_normalize_spaces(self):
        self.assertEqual(clean_ocr_text("hello   world"), "hello world")

    def test_preserve_single_empty_line(self):
        self.assertEqual(clean_ocr_text("a\n\nb"), "a\n\nb")


class DeepCleanOcrTextTest(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(deep_clean_ocr_text(""), "")

    def test_merge_empty_lines(self):
        self.assertEqual(deep_clean_ocr_text("a\n\n\nb"), "a\nb")

    def test_fix_duplicate_punctuation(self):
        self.assertEqual(deep_clean_ocr_text("你好，，世界"), "你好，世界")
        self.assertEqual(deep_clean_ocr_text("测试。。完成"), "测试。完成")

    def test_remove_extra_spaces(self):
        self.assertEqual(deep_clean_ocr_text("hello  world"), "hello world")

    def test_fix_cjk_spaces(self):
        self.assertEqual(deep_clean_ocr_text("你 好 世 界"), "你好世界")


class ExtractNumbersTest(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(extract_numbers(""), [])

    def test_single_number(self):
        self.assertEqual(extract_numbers("价格100元"), ["100"])

    def test_multiple_numbers(self):
        self.assertEqual(extract_numbers("电话13812345678"), ["13812345678"])

    def test_decimal(self):
        self.assertEqual(extract_numbers("价格3.14元"), ["3.14"])

    def test_no_numbers(self):
        self.assertEqual(extract_numbers("没有数字"), [])


class ExtractChineseTest(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(extract_chinese(""), "")

    def test_pure_chinese(self):
        self.assertEqual(extract_chinese("你好世界"), "你好世界")

    def test_mixed(self):
        self.assertEqual(extract_chinese("Hello你好World世界"), "你好世界")

    def test_no_chinese(self):
        self.assertEqual(extract_chinese("Hello World"), "")


class OcrEngineRegistryTest(unittest.TestCase):
    """OCR 引擎注册表测试。"""

    def test_registry_recognize_tries_engines_in_order(self):
        from quickshot.ocr_engine import OcrEngine, OcrEngineRegistry

        calls = []

        class FakeEngine(OcrEngine):
            def __init__(self, name, result):
                self._name = name
                self._result = result
            def identifier(self):
                return self._name
            def display_name(self):
                return self._name
            def is_available(self):
                return True
            def recognize(self, prepared_image):
                calls.append(self._name)
                return self._result

        reg = OcrEngineRegistry()
        reg.register(FakeEngine("a", ""))
        reg.register(FakeEngine("b", "hello"))
        from PyQt6.QtGui import QImage
        result = reg.recognize(QImage())
        # a 返回空，应该继续尝试 b
        self.assertEqual(calls, ["a", "b"])
        self.assertEqual(result.text, "hello")
        self.assertEqual(result.engine_key, "b")

    def test_registry_skips_unavailable_engine(self):
        from quickshot.ocr_engine import OcrEngine, OcrEngineRegistry

        class UnavailableEngine(OcrEngine):
            def identifier(self):
                return "unavail"
            def display_name(self):
                return "unavail"
            def is_available(self):
                return False
            def recognize(self, prepared_image):
                raise AssertionError("should not be called")

        class OkEngine(OcrEngine):
            def identifier(self):
                return "ok"
            def display_name(self):
                return "ok"
            def is_available(self):
                return True
            def recognize(self, prepared_image):
                return "found text"

        reg = OcrEngineRegistry()
        reg.register(UnavailableEngine())
        reg.register(OkEngine())
        from PyQt6.QtGui import QImage
        result = reg.recognize(QImage())
        self.assertEqual(result.engine_key, "ok")

    def test_registry_all_fail_returns_empty(self):
        from quickshot.ocr_engine import OcrEngine, OcrEngineRegistry

        class FailEngine(OcrEngine):
            def identifier(self):
                return "fail"
            def display_name(self):
                return "fail"
            def is_available(self):
                return True
            def recognize(self, prepared_image):
                raise RuntimeError("boom")

        reg = OcrEngineRegistry()
        reg.register(FailEngine())
        from PyQt6.QtGui import QImage
        result = reg.recognize(QImage())
        self.assertEqual(result.text, "")
        self.assertIn("失败", result.note)

    def test_get_default_registry_returns_singleton(self):
        from quickshot.ocr_engine import get_default_registry
        r1 = get_default_registry()
        r2 = get_default_registry()
        self.assertIs(r1, r2)


class RapidOcrOptionalTest(unittest.TestCase):
    def test_rapidocr_engine_availability_uses_optional_component_probe(self):
        from quickshot.ocr_engine import RapidOcrEngine

        with patch("quickshot.ocr.is_rapidocr_available", return_value=False):
            self.assertFalse(RapidOcrEngine().is_available())

    def test_privacy_detection_falls_back_to_windows_ocr_when_rapidocr_is_missing(self):
        image = QImage(3000, 100, QImage.Format.Format_RGB32)
        windows_result = [
            [[[10, 20], [130, 20], [130, 40], [10, 40]], "手机号 13812345678"],
        ]

        with patch("quickshot.ocr.is_rapidocr_available", return_value=False):
            with patch("quickshot.ocr._recognize_privacy_lines_with_windows_ocr", return_value=windows_result) as fallback:
                rects = detect_privacy_info(image)

        fallback.assert_called_once()
        self.assertEqual(rects, [(10, 20, 120, 20)])

    def test_windows_ocr_lines_are_converted_to_rapidocr_shape(self):
        from quickshot.ocr import _windows_ocr_lines_to_rapidocr_result

        converted = _windows_ocr_lines_to_rapidocr_result([
            {"Text": "邮箱 test@example.com", "BoundingBox": [5, 7, 105, 27]},
            {"Text": "", "BoundingBox": [1, 2, 3, 4]},
            {"Text": "bad", "BoundingBox": [9, 9, 8, 10]},
        ])

        self.assertEqual(converted, [
            [[[5.0, 7.0], [105.0, 7.0], [105.0, 27.0], [5.0, 27.0]], "邮箱 test@example.com"],
        ])

    def test_prewarm_skips_when_optional_component_is_missing(self):
        import quickshot.ocr as ocr

        previous = ocr._PREWARM_FUTURE
        try:
            ocr._PREWARM_FUTURE = None
            with patch("quickshot.ocr.is_rapidocr_available", return_value=False):
                ocr.schedule_rapidocr_prewarm()
            self.assertIsNone(ocr._PREWARM_FUTURE)
        finally:
            ocr._PREWARM_FUTURE = previous


if __name__ == "__main__":
    unittest.main()
