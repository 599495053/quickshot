from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quickshot.feedback import compact_error_message, detailed_error_message  # noqa: E402


class FeedbackMessageTest(unittest.TestCase):
    def test_compact_error_message_includes_hint_and_redacts_sensitive_detail(self) -> None:
        msg = compact_error_message(
            "上传失败",
            r"D:\private\shot.png token=ghp_abcdef1234567890",
            max_length=200,
        )
        self.assertIn("上传失败", msg)
        self.assertIn("可复制诊断信息后反馈", msg)
        self.assertIn("<path>", msg)
        self.assertNotIn("ghp_", msg)
        self.assertNotIn(r"D:\private", msg)

    def test_compact_error_message_truncates_long_detail(self) -> None:
        msg = compact_error_message("OCR 失败", "x" * 400, max_length=60)
        self.assertLessEqual(len(msg), 60)
        self.assertIn("可复制诊断信息后反馈", msg)

    def test_detailed_error_message_has_reason_and_next_step(self) -> None:
        msg = detailed_error_message("无法获取屏幕截图。", "mss init failed")
        self.assertIn("无法获取屏幕截图。", msg)
        self.assertIn("原因：mss init failed", msg)
        self.assertIn("可从托盘菜单或设置页复制诊断信息后反馈。", msg)

    def test_detailed_error_message_can_skip_hint(self) -> None:
        msg = detailed_error_message("无法加载截图，图片为空。", include_hint=False)
        self.assertEqual(msg, "无法加载截图，图片为空。")


if __name__ == "__main__":
    unittest.main()
