"""ToolStrategy + CoordinateSystem 测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, call

from PyQt6.QtCore import QPoint, QPointF, QRect, QSize

from quickshot.overlay._tool_strategies import (
    ArrowStrategy,
    BlurStrategy,
    DashedRectStrategy,
    EllipseStrategy,
    HighlightStrategy,
    MosaicStrategy,
    PenStrategy,
    RectStrategy,
    ToolContext,
    TOOL_STRATEGIES,
)
from quickshot.overlay.coords import CoordinateSystem


# ═══════════════════════════════════════════════════════════════════
#  ToolStrategy 测试
# ═══════════════════════════════════════════════════════════════════

def _make_ctx(**overrides) -> ToolContext:
    defaults = dict(
        start=QPoint(10, 10),
        end=QPoint(100, 100),
        path=[QPoint(10, 10), QPoint(50, 50), QPoint(100, 100)],
        active_tool="arrow",
        push_history=MagicMock(),
        draw_arrow_on_pixmap=MagicMock(),
        draw_rect_on_pixmap=MagicMock(),
        draw_ellipse_on_pixmap=MagicMock(),
        draw_dashed_rect_on_pixmap=MagicMock(),
        draw_freehand_on_pixmap=MagicMock(),
        draw_highlight_on_pixmap=MagicMock(),
        apply_mosaic=MagicMock(),
        apply_blur=MagicMock(),
        draw_arrow_preview=MagicMock(),
        draw_rect_preview=MagicMock(),
        draw_ellipse_preview=MagicMock(),
        draw_dashed_rect_preview=MagicMock(),
        draw_freehand_preview=MagicMock(),
        draw_mosaic_preview=MagicMock(),
        draw_blur_preview=MagicMock(),
    )
    defaults.update(overrides)
    return ToolContext(**defaults)


class ArrowStrategyTest(unittest.TestCase):

    def test_commit_calls_draw_arrow(self):
        ctx = _make_ctx()
        ArrowStrategy().commit(ctx)
        ctx.push_history.assert_called_once()
        ctx.draw_arrow_on_pixmap.assert_called_once_with(QPoint(10, 10), QPoint(100, 100))

    def test_commit_too_short_noop(self):
        ctx = _make_ctx(start=QPoint(10, 10), end=QPoint(11, 11))
        ArrowStrategy().commit(ctx)
        ctx.push_history.assert_not_called()

    def test_preview_calls_draw_arrow_preview(self):
        ctx = _make_ctx()
        painter = MagicMock()
        ArrowStrategy().preview(ctx, painter)
        ctx.draw_arrow_preview.assert_called_once()


class RectStrategyTest(unittest.TestCase):

    def test_commit_calls_draw_rect(self):
        ctx = _make_ctx()
        RectStrategy().commit(ctx)
        ctx.push_history.assert_called_once()
        ctx.draw_rect_on_pixmap.assert_called_once()

    def test_commit_too_small_noop(self):
        ctx = _make_ctx(start=QPoint(10, 10), end=QPoint(12, 12))
        RectStrategy().commit(ctx)
        ctx.push_history.assert_not_called()


class EllipseStrategyTest(unittest.TestCase):

    def test_commit_calls_draw_ellipse(self):
        ctx = _make_ctx()
        EllipseStrategy().commit(ctx)
        ctx.push_history.assert_called_once()
        ctx.draw_ellipse_on_pixmap.assert_called_once()


class DashedRectStrategyTest(unittest.TestCase):

    def test_commit_calls_draw_dashed_rect(self):
        ctx = _make_ctx()
        DashedRectStrategy().commit(ctx)
        ctx.push_history.assert_called_once()
        ctx.draw_dashed_rect_on_pixmap.assert_called_once()


class PenStrategyTest(unittest.TestCase):

    def test_commit_calls_draw_freehand(self):
        ctx = _make_ctx()
        PenStrategy().commit(ctx)
        ctx.push_history.assert_called_once()
        ctx.draw_freehand_on_pixmap.assert_called_once()

    def test_commit_too_few_points_noop(self):
        ctx = _make_ctx(path=[QPoint(10, 10)])
        PenStrategy().commit(ctx)
        ctx.push_history.assert_not_called()


class HighlightStrategyTest(unittest.TestCase):

    def test_commit_calls_draw_highlight(self):
        ctx = _make_ctx()
        HighlightStrategy().commit(ctx)
        ctx.push_history.assert_called_once()
        ctx.draw_highlight_on_pixmap.assert_called_once()


class MosaicStrategyTest(unittest.TestCase):

    def test_commit_calls_apply_mosaic(self):
        ctx = _make_ctx()
        MosaicStrategy().commit(ctx)
        ctx.push_history.assert_called_once()
        ctx.apply_mosaic.assert_called_once()

    def test_commit_too_small_noop(self):
        ctx = _make_ctx(start=QPoint(10, 10), end=QPoint(15, 15))
        MosaicStrategy().commit(ctx)
        ctx.push_history.assert_not_called()


class BlurStrategyTest(unittest.TestCase):

    def test_commit_calls_apply_blur(self):
        ctx = _make_ctx()
        BlurStrategy().commit(ctx)
        ctx.push_history.assert_called_once()
        ctx.apply_blur.assert_called_once()


class ToolStrategiesRegistryTest(unittest.TestCase):

    def test_all_tools_registered(self):
        expected = {"arrow", "rect", "ellipse", "dashed_rect", "pen", "highlight", "mosaic", "blur"}
        self.assertEqual(set(TOOL_STRATEGIES.keys()), expected)

    def test_each_strategy_has_correct_tool_name(self):
        for name, strategy in TOOL_STRATEGIES.items():
            with self.subTest(name=name):
                self.assertEqual(strategy.tool_name, name)


# ═══════════════════════════════════════════════════════════════════
#  CoordinateSystem 测试
# ═══════════════════════════════════════════════════════════════════

class ClampPointTest(unittest.TestCase):

    def test_inside_no_change(self):
        rect = QRect(0, 0, 800, 600)
        p = CoordinateSystem.clamp_point(QPoint(400, 300), rect)
        self.assertEqual(p, QPoint(400, 300))

    def test_clamp_left(self):
        rect = QRect(0, 0, 800, 600)
        p = CoordinateSystem.clamp_point(QPoint(-10, 300), rect)
        self.assertEqual(p.x(), 0)

    def test_clamp_right(self):
        rect = QRect(0, 0, 800, 600)
        p = CoordinateSystem.clamp_point(QPoint(999, 300), rect)
        self.assertEqual(p.x(), rect.right())  # QRect.right() = 799

    def test_clamp_top(self):
        rect = QRect(0, 0, 800, 600)
        p = CoordinateSystem.clamp_point(QPoint(400, -10), rect)
        self.assertEqual(p.y(), 0)

    def test_clamp_bottom(self):
        rect = QRect(0, 0, 800, 600)
        p = CoordinateSystem.clamp_point(QPoint(400, 999), rect)
        self.assertEqual(p.y(), rect.bottom())  # QRect.bottom() = 599


class LogicalToPhysicalRectTest(unittest.TestCase):

    def test_identity_scale(self):
        cs = CoordinateSystem(1.0, 1.0, 0, 0)
        rect = QRect(100, 100, 300, 200)
        raw_size = QSize(1920, 1080)
        result = cs.logical_to_physical_rect(rect, raw_size)
        self.assertEqual(result, QRect(100, 100, 300, 200))

    def test_2x_scale(self):
        cs = CoordinateSystem(2.0, 2.0, 0, 0)
        rect = QRect(100, 100, 300, 200)
        raw_size = QSize(1920, 1080)
        result = cs.logical_to_physical_rect(rect, raw_size)
        self.assertEqual(result, QRect(200, 200, 600, 400))

    def test_null_rect_returns_empty(self):
        cs = CoordinateSystem(1.0, 1.0, 0, 0)
        result = cs.logical_to_physical_rect(QRect(), QSize(1920, 1080))
        self.assertTrue(result.isNull())

    def test_clamps_to_raw_size(self):
        cs = CoordinateSystem(2.0, 2.0, 0, 0)
        rect = QRect(900, 500, 200, 200)
        raw_size = QSize(1920, 1080)
        result = cs.logical_to_physical_rect(rect, raw_size)
        self.assertLessEqual(result.right(), 1920)
        self.assertLessEqual(result.bottom(), 1080)


class WidgetToImageTest(unittest.TestCase):

    def test_top_left_is_origin(self):
        sel = QRect(100, 100, 400, 300)
        img_size = QSize(800, 600)
        result = CoordinateSystem.widget_to_image(QPoint(100, 100), sel, img_size)
        self.assertEqual(result, QPoint(0, 0))

    def test_bottom_right_is_max(self):
        sel = QRect(100, 100, 400, 300)
        img_size = QSize(800, 600)
        # (499-100)*800/400 = 798, (399-100)*600/300 = 598
        result = CoordinateSystem.widget_to_image(QPoint(499, 399), sel, img_size)
        self.assertEqual(result, QPoint(798, 598))

    def test_center_maps_to_center(self):
        sel = QRect(100, 100, 400, 300)
        img_size = QSize(800, 600)
        result = CoordinateSystem.widget_to_image(QPoint(300, 250), sel, img_size)
        self.assertEqual(result, QPoint(400, 300))

    def test_outside_returns_none(self):
        sel = QRect(100, 100, 400, 300)
        img_size = QSize(800, 600)
        result = CoordinateSystem.widget_to_image(QPoint(50, 50), sel, img_size)
        self.assertIsNone(result)

    def test_outside_clamped(self):
        sel = QRect(100, 100, 400, 300)
        img_size = QSize(800, 600)
        result = CoordinateSystem.widget_to_image(QPoint(50, 50), sel, img_size, clamped=True)
        self.assertIsNotNone(result)
        self.assertEqual(result, QPoint(0, 0))

    def test_empty_image_returns_none(self):
        sel = QRect(100, 100, 400, 300)
        result = CoordinateSystem.widget_to_image(QPoint(300, 250), sel, QSize())
        self.assertIsNone(result)


class ImageToWidgetTest(unittest.TestCase):

    def test_origin_maps_to_top_left(self):
        sel = QRect(100, 100, 400, 300)
        img_size = QSize(800, 600)
        result = CoordinateSystem.image_to_widget(QPoint(0, 0), sel, img_size)
        self.assertAlmostEqual(result.x(), 100.0)
        self.assertAlmostEqual(result.y(), 100.0)

    def test_max_maps_to_bottom_right(self):
        sel = QRect(100, 100, 400, 300)
        img_size = QSize(800, 600)
        result = CoordinateSystem.image_to_widget(QPoint(800, 600), sel, img_size)
        self.assertAlmostEqual(result.x(), 500.0)
        self.assertAlmostEqual(result.y(), 400.0)


class ScaledStrokeWidthTest(unittest.TestCase):

    def test_identity_scale(self):
        sel = QRect(0, 0, 800, 600)
        img_size = QSize(800, 600)
        result = CoordinateSystem.scaled_stroke_width(3.0, sel, img_size)
        self.assertAlmostEqual(result, 3.0)

    def test_half_scale_returns_minimum(self):
        sel = QRect(0, 0, 400, 300)
        img_size = QSize(800, 600)
        result = CoordinateSystem.scaled_stroke_width(1.0, sel, img_size)
        self.assertGreaterEqual(result, 1.4)

    def test_empty_image_returns_original(self):
        result = CoordinateSystem.scaled_stroke_width(5.0, QRect(0, 0, 100, 100), QSize())
        self.assertEqual(result, 5.0)


class AnnotationPointsToWidgetTest(unittest.TestCase):

    def test_basic_conversion(self):
        item = {"points": [(0, 0), (100, 100)]}
        sel = QRect(100, 100, 400, 300)
        img_size = QSize(800, 600)
        result = CoordinateSystem.annotation_points_to_widget(item, sel, img_size)
        self.assertEqual(len(result), 2)

    def test_empty_points(self):
        item = {"points": []}
        sel = QRect(100, 100, 400, 300)
        img_size = QSize(800, 600)
        result = CoordinateSystem.annotation_points_to_widget(item, sel, img_size)
        self.assertEqual(len(result), 0)

    def test_invalid_points_skipped(self):
        item = {"points": [(0, 0), "invalid", (100, 100)]}
        sel = QRect(100, 100, 400, 300)
        img_size = QSize(800, 600)
        result = CoordinateSystem.annotation_points_to_widget(item, sel, img_size)
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
