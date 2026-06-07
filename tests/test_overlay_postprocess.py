"""Overlay 后处理变换测试。"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QRect  # noqa: E402
from PyQt6.QtGui import QColor, QPainter, QPixmap  # noqa: E402
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


class ApplyShadowTest(unittest.TestCase):

    def test_apply_shadow_expands_pixmap(self):
        ov = _make_overlay()
        old_w = ov.edit_pixmap.width()
        old_h = ov.edit_pixmap.height()
        ov.apply_shadow()
        self.assertGreater(ov.edit_pixmap.width(), old_w)
        self.assertGreater(ov.edit_pixmap.height(), old_h)
        self.assertIn("阴影", ov.message)

    def test_apply_shadow_empty_pixmap_noop(self):
        ov = _make_overlay()
        ov.edit_pixmap = QPixmap()
        ov.apply_shadow()
        # 不崩溃

    def test_undo_reverts_shadow(self):
        ov = _make_overlay()
        old_w = ov.edit_pixmap.width()
        old_h = ov.edit_pixmap.height()
        ov.apply_shadow()
        self.assertGreater(ov.edit_pixmap.width(), old_w)
        ov.undo()
        self.assertEqual(ov.edit_pixmap.width(), old_w)
        self.assertEqual(ov.edit_pixmap.height(), old_h)


class ApplyBorderTest(unittest.TestCase):

    def test_apply_border_expands_pixmap(self):
        ov = _make_overlay()
        old_w = ov.edit_pixmap.width()
        old_h = ov.edit_pixmap.height()
        ov.apply_border()
        self.assertGreater(ov.edit_pixmap.width(), old_w)
        self.assertGreater(ov.edit_pixmap.height(), old_h)
        self.assertIn("边框", ov.message)

    def test_apply_border_uses_stroke_width(self):
        ov = _make_overlay()
        ov.stroke_width = 10
        old_w = ov.edit_pixmap.width()
        ov.apply_border()
        # 两边各加 10px = 20px
        self.assertEqual(ov.edit_pixmap.width(), old_w + 20)

    def test_undo_reverts_border(self):
        ov = _make_overlay()
        old_w = ov.edit_pixmap.width()
        ov.apply_border()
        self.assertGreater(ov.edit_pixmap.width(), old_w)
        ov.undo()
        self.assertEqual(ov.edit_pixmap.width(), old_w)


class ApplyWatermarkTest(unittest.TestCase):

    def test_apply_watermark_modifies_pixmap(self):
        ov = _make_overlay()
        old_size = (ov.edit_pixmap.width(), ov.edit_pixmap.height())
        ov.apply_watermark()
        # 水印不改变尺寸
        self.assertEqual((ov.edit_pixmap.width(), ov.edit_pixmap.height()), old_size)
        self.assertIn("水印", ov.message)

    def test_apply_watermark_empty_pixmap_noop(self):
        ov = _make_overlay()
        ov.edit_pixmap = QPixmap()
        ov.apply_watermark()
        # 不崩溃

    def test_undo_reverts_watermark(self):
        ov = _make_overlay()
        # 记录原始像素
        original_pixel = ov.edit_pixmap.toImage().pixel(200, 150)
        ov.apply_watermark()
        ov.undo()
        restored_pixel = ov.edit_pixmap.toImage().pixel(200, 150)
        self.assertEqual(original_pixel, restored_pixel)


class ApplyBlurTest(unittest.TestCase):

    def test_apply_blur_changes_high_contrast_region(self):
        ov = _make_overlay()
        pixmap = QPixmap(80, 40)
        pixmap.fill(QColor(0, 0, 0))
        painter = QPainter(pixmap)
        try:
            painter.fillRect(QRect(40, 0, 40, 40), QColor(255, 255, 255))
        finally:
            painter.end()

        ov.base_edit_pixmap = pixmap.copy()
        ov.edit_pixmap = pixmap.copy()
        ov.invalidate_image_cache()

        before = ov.edit_pixmap.toImage().pixelColor(39, 20)
        ov.apply_blur(QRect(20, 0, 40, 40))
        after = ov.edit_pixmap.toImage().pixelColor(39, 20)

        self.assertEqual(ov.annotations[-1]["type"], "blur")
        self.assertIn("patch", ov.annotations[-1])
        self.assertNotEqual(before, after)
        self.assertGreater(after.red(), before.red())
        self.assertLess(after.red(), 255)


class ExtendSelectionRectTest(unittest.TestCase):

    def test_extend_selection_rect(self):
        ov = _make_overlay()
        ov.selection_rect = QRect(100, 100, 400, 300)
        ov._extend_selection_rect(400, 300, 8, 8, 8, 8)
        # 应该向外扩展
        self.assertLess(ov.selection_rect.left(), 100)
        self.assertLess(ov.selection_rect.top(), 100)
        self.assertGreater(ov.selection_rect.right(), 499)
        self.assertGreater(ov.selection_rect.bottom(), 399)

    def test_extend_selection_rect_null_noop(self):
        ov = _make_overlay()
        ov.selection_rect = QRect()
        ov._extend_selection_rect(400, 300, 8, 8, 8, 8)
        # 不崩溃


if __name__ == "__main__":
    unittest.main()
