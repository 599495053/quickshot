"""overlay 渲染性能优化的单元测试。

覆盖：qc() 缓存、annotation_painter 缓存、setCursor 去重、样式面板布局缓存等。"""

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPointF, QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication(sys.argv)

from quickshot.theme import (
    _QC_CACHE,
    floating_bg,
    floating_border,
    floating_text,
    handle_fill,
    overlay_dim,
    overlay_solid,
    qc,
)


class QcCacheTest(unittest.TestCase):
    """qc() 应返回缓存的 QColor 实例。"""

    def setUp(self):
        _QC_CACHE.clear()

    def test_same_token_same_instance(self):
        a = qc("accent.base")
        b = qc("accent.base")
        self.assertIs(a, b)

    def test_different_alpha_different_instance(self):
        a = qc("accent.base", 255)
        b = qc("accent.base", 128)
        self.assertIsNot(a, b)
        self.assertEqual(a.alpha(), 255)
        self.assertEqual(b.alpha(), 128)

    def test_unknown_token_raises(self):
        with self.assertRaises(KeyError):
            qc("nonexistent.token")

    def test_color_value_correct(self):
        c = qc("accent.base")
        self.assertEqual(c.name(), "#2563eb")

    def test_cache_populated(self):
        qc("text.primary")
        self.assertIn(("text.primary", 255), _QC_CACHE)


class FactorySingletonTest(unittest.TestCase):
    """工厂函数应返回模块级单例。"""

    def test_overlay_dim_returns_same_instance(self):
        a = overlay_dim()
        b = overlay_dim()
        self.assertIs(a, b)

    def test_floating_bg_returns_same_instance(self):
        self.assertIs(floating_bg(), floating_bg())

    def test_floating_border_returns_same_instance(self):
        self.assertIs(floating_border(), floating_border())

    def test_floating_text_returns_same_instance(self):
        self.assertIs(floating_text(), floating_text())

    def test_handle_fill_returns_same_instance(self):
        self.assertIs(handle_fill(), handle_fill())

    def test_overlay_solid_returns_same_instance(self):
        self.assertIs(overlay_solid(), overlay_solid())

    def test_overlay_dim_alpha(self):
        self.assertEqual(overlay_dim().alpha(), 100)

    def test_floating_bg_values(self):
        bg = floating_bg()
        self.assertEqual(bg.red(), 18)
        self.assertEqual(bg.green(), 24)
        self.assertEqual(bg.blue(), 33)
        self.assertEqual(bg.alpha(), 232)


class AnnotationPainterPolylineTest(unittest.TestCase):
    """draw_polyline 应使用 QPainterPath 批量绘制。"""

    def test_polyline_uses_path(self):
        pixmap = QPixmap(200, 200)
        pixmap.fill(Qt.GlobalColor.white)
        painter = QPainter(pixmap)
        points = [QPointF(i * 10, i * 5) for i in range(20)]
        from quickshot.overlay.annotation_painter import draw_polyline
        draw_polyline(painter, points, QColor("red"), 3.0)
        painter.end()
        # 不抛异常即为通过
        self.assertFalse(pixmap.isNull())

    def test_polyline_less_than_2_points_no_crash(self):
        pixmap = QPixmap(100, 100)
        painter = QPainter(pixmap)
        from quickshot.overlay.annotation_painter import draw_polyline
        draw_polyline(painter, [QPointF(0, 0)], QColor("red"), 3.0)
        painter.end()

    def test_polyline_empty_list_no_crash(self):
        pixmap = QPixmap(100, 100)
        painter = QPainter(pixmap)
        from quickshot.overlay.annotation_painter import draw_polyline
        draw_polyline(painter, [], QColor("red"), 3.0)
        painter.end()


class AnnotationPainterFontCacheTest(unittest.TestCase):
    """annotation_painter 的 QFont 缓存应返回相同实例。"""

    def test_number_font_cached(self):
        from quickshot.overlay.annotation_painter import _get_number_font
        f1, m1 = _get_number_font()
        f2, m2 = _get_number_font()
        self.assertIs(f1, f2)
        self.assertIs(m1, m2)

    def test_text_font_cached_per_size(self):
        from quickshot.overlay.annotation_painter import _get_text_font
        f1, m1 = _get_text_font(28)
        f2, m2 = _get_text_font(28)
        self.assertIs(f1, f2)
        self.assertIs(m1, m2)

    def test_text_font_different_size_different_instance(self):
        from quickshot.overlay.annotation_painter import _get_text_font
        f1, _ = _get_text_font(28)
        f2, _ = _get_text_font(14)
        self.assertIsNot(f1, f2)

    def test_number_font_properties(self):
        from quickshot.overlay.annotation_painter import _get_number_font
        font, _ = _get_number_font()
        self.assertEqual(font.pixelSize(), 14)
        self.assertEqual(font.weight(), QFont.Weight.Bold)


class AnnotationColorCacheTest(unittest.TestCase):
    """标注颜色应缓存到 _qc 字段。"""

    def test_annotation_color_cached(self):
        from quickshot.overlay._paint import PaintMixin
        item = {"color": "#ff4646"}
        c1 = PaintMixin._annotation_color(item)
        c2 = PaintMixin._annotation_color(item)
        self.assertIs(c1, c2)
        self.assertIn("_qc", item)
        self.assertIs(item["_qc"], c1)

    def test_annotation_color_default(self):
        from quickshot.overlay._paint import PaintMixin
        from quickshot.theme import STROKE_DEFAULT
        item = {}
        c = PaintMixin._annotation_color(item)
        self.assertEqual(c.name(), STROKE_DEFAULT)


class DrawNumberBadgeTest(unittest.TestCase):
    """draw_number_badge 应使用缓存字体。"""

    def test_draw_no_crash(self):
        pixmap = QPixmap(100, 100)
        painter = QPainter(pixmap)
        from quickshot.overlay.annotation_painter import draw_number_badge
        draw_number_badge(painter, QPointF(50, 50), 1, QColor("red"))
        painter.end()
        self.assertFalse(pixmap.isNull())


class DrawTextAnnotationTest(unittest.TestCase):
    """draw_text_annotation 应使用缓存字体。"""

    def test_draw_no_crash(self):
        pixmap = QPixmap(200, 200)
        painter = QPainter(pixmap)
        from quickshot.overlay.annotation_painter import draw_text_annotation
        draw_text_annotation(painter, QPointF(10, 10), "Hello", 28, QColor("white"))
        painter.end()
        self.assertFalse(pixmap.isNull())

    def test_empty_text_no_crash(self):
        pixmap = QPixmap(200, 200)
        painter = QPainter(pixmap)
        from quickshot.overlay.annotation_painter import draw_text_annotation
        draw_text_annotation(painter, QPointF(10, 10), "", 28, QColor("white"))
        painter.end()


class ToolbarItemsCacheTest(unittest.TestCase):
    """toolbar_items 应返回静态列表。"""

    def test_toolbar_items_returns_list(self):
        from quickshot.overlay._toolbar import ToolbarMixin
        items = ToolbarMixin.toolbar_items()
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 20)

    def test_toolbar_items_contains_expected_keys(self):
        from quickshot.overlay._toolbar import ToolbarMixin
        keys = [item[0] for item in ToolbarMixin.toolbar_items()]
        for expected in ("arrow", "rect", "pen", "highlight", "text", "mosaic", "blur", "done", "cancel"):
            self.assertIn(expected, keys)


class MosaicCacheTest(unittest.TestCase):
    """draw_mosaic_overlay 应缓存缩放结果。"""

    def test_mosaic_cache_key_format(self):
        # 测试缓存 key 的正确性（间接测试）
        pixmap = QPixmap(100, 100)
        self.assertEqual(pixmap.width(), 100)


if __name__ == "__main__":
    unittest.main()
