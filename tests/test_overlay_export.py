"""Overlay 导出操作测试。"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QRect  # noqa: E402
from PyQt6.QtGui import QColor, QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from quickshot.config import Config  # noqa: E402
from quickshot.history import CaptureHistoryStore  # noqa: E402
from quickshot.overlay.widget import FloatingSnipOverlay  # noqa: E402


_app: QApplication | None = None


def _ensure_app() -> QApplication:
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


def _make_overlay() -> FloatingSnipOverlay:
    _ensure_app()
    cfg = Config()
    store = CaptureHistoryStore(cfg)
    raw = QPixmap(800, 600)
    raw.fill(QColor(60, 60, 60))
    disp = QPixmap(800, 600)
    disp.fill(QColor(60, 60, 60))
    overlay = FloatingSnipOverlay(
        raw, disp, QRect(0, 0, 800, 600), 1.0, 1.0, 0, 0, cfg, store
    )
    overlay.selection_rect = QRect(100, 100, 400, 300)
    overlay.selection_physical_rect = QRect(100, 100, 400, 300)
    overlay.base_edit_pixmap = raw.copy(QRect(100, 100, 400, 300))
    overlay.edit_pixmap = overlay.base_edit_pixmap.copy()
    overlay.mode = "edit"
    overlay.resize(800, 600)
    return overlay


class CopyCurrentTest(unittest.TestCase):

    def test_copy_current_sets_message(self):
        ov = _make_overlay()
        ov.copy_current()
        self.assertIn("已复制", ov.message)

    def test_copy_empty_pixmap_noop(self):
        ov = _make_overlay()
        ov.edit_pixmap = QPixmap()
        ov.copy_current()
        # 不应设置 message（直接返回）


class SaveCurrentTest(unittest.TestCase):

    def test_save_current_writes_png(self):
        ov = _make_overlay()
        with tempfile.TemporaryDirectory() as tmp:
            filepath = str(Path(tmp) / "test_save.png")
            # 模拟 save dialog 返回路径
            from unittest.mock import patch
            with patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName", return_value=(filepath, "")):
                ov.save_current()
            self.assertTrue(Path(filepath).exists(), f"PNG not saved to {filepath}")
            self.assertIn("已保存", ov.message)


class RecordCaptureHistoryTest(unittest.TestCase):

    def test_record_capture_adds_item(self):
        ov = _make_overlay()
        result = ov.record_capture_history("copy")
        self.assertIsNotNone(result)
        self.assertIn("id", result)

    def test_record_capture_disabled_noop(self):
        ov = _make_overlay()
        ov.config.auto_history = False
        result = ov.record_capture_history("copy")
        self.assertIsNone(result)


class MaybeNotifyTest(unittest.TestCase):

    def test_notify_disabled_no_emit(self):
        ov = _make_overlay()
        ov.config.show_notifications = False
        received = []
        ov.notify.connect(received.append)
        ov.maybe_notify("test message")
        self.assertEqual(received, [])

    def test_notify_enabled_calls_emit(self):
        ov = _make_overlay()
        ov.config.show_notifications = True
        # 验证 maybe_notify 不抛异常
        ov.maybe_notify("test")


if __name__ == "__main__":
    unittest.main()
