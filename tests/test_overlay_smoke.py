"""Overlay 烟雾测试：确保各标注工具的 select_tool + paint 链路不抛异常。

历史上曾出现 ``QPainterPath`` 漏导入导致点击箭头按钮闪退的事故，本测试
覆盖所有绘制工具，在 paintEvent 路径上跑一遍，提早暴露未定义符号、
NameError、类型不匹配等低级错误。
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

# 让测试既能在仓库根目录运行，也能在 tests/ 目录运行
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, QRect  # noqa: E402
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


def _paint_once(overlay: FloatingSnipOverlay) -> None:
    canvas = QPixmap(overlay.width(), overlay.height())
    canvas.fill(QColor(0, 0, 0))
    painter = QPainter(canvas)
    try:
        overlay.paint_edit_mode(painter)
    finally:
        painter.end()


class OverlayToolSmokeTest(unittest.TestCase):
    """每种工具走一遍 select_tool + paint + 模拟拖拽 paint。"""

    DRAW_TOOLS = ("arrow", "rect", "pen", "highlight", "mosaic")
    # 仅这些工具会激活 stroke 颜色/线宽样式面板（mosaic/blur 无 stroke 配置）
    STYLE_TOOLS = ("arrow", "rect", "pen", "highlight")
    ALL_TOOLS = DRAW_TOOLS + ("text",)

    def test_select_each_tool_and_paint(self) -> None:
        for tool in self.ALL_TOOLS:
            with self.subTest(tool=tool):
                overlay = _make_overlay()
                overlay.select_tool(tool)
                _paint_once(overlay)

    def test_drag_preview_for_draw_tools(self) -> None:
        for tool in self.DRAW_TOOLS:
            with self.subTest(tool=tool):
                overlay = _make_overlay()
                overlay.select_tool(tool)
                overlay.drag_start = QPoint(50, 50)
                overlay.drag_end = QPoint(200, 150)
                overlay.dragging_annotation = True
                if tool in ("pen", "highlight"):
                    overlay.drag_path = [QPoint(50, 50), QPoint(120, 100), QPoint(200, 150)]
                _paint_once(overlay)

    def test_commit_arrow_annotation(self) -> None:
        overlay = _make_overlay()
        overlay.select_tool("arrow")
        overlay.push_history()
        overlay.draw_arrow_on_pixmap(QPoint(50, 50), QPoint(200, 150))
        self.assertEqual(overlay.annotations[-1]["type"], "arrow")

    def test_style_panel_renders_for_all_draw_tools(self) -> None:
        # 直接覆盖之前 QPainterPath 漏导入触发的崩溃路径
        for tool in self.STYLE_TOOLS:
            with self.subTest(tool=tool):
                overlay = _make_overlay()
                overlay.select_tool(tool)
                self.assertEqual(overlay.style_panel_kind, "style")
                _paint_once(overlay)

    def test_ocr_region_preview_paints(self) -> None:
        # 覆盖 OCR 局部框选预览路径，避免 QRectF 这类只在交互分支出现的漏导入。
        overlay = _make_overlay()
        overlay.ocr_region_mode = True
        overlay.active_tool = "none"
        overlay.dragging_annotation = True
        overlay.drag_start = QPoint(40, 40)
        overlay.drag_end = QPoint(220, 140)
        _paint_once(overlay)


if __name__ == "__main__":
    unittest.main()
