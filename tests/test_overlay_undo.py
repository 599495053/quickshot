"""Overlay 撤销/重做测试。"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, QRect  # noqa: E402
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


class PushHistoryTest(unittest.TestCase):

    def test_push_history_increments_stack(self):
        ov = _make_overlay()
        self.assertEqual(len(ov.history), 0)
        ov.push_history()
        self.assertEqual(len(ov.history), 1)
        ov.push_history()
        self.assertEqual(len(ov.history), 2)

    def test_push_history_clears_redo(self):
        ov = _make_overlay()
        ov.push_history()
        ov.undo()
        self.assertEqual(len(ov.redo_stack), 1)
        ov.push_history()
        self.assertEqual(len(ov.redo_stack), 0)

    def test_push_history_max_15(self):
        ov = _make_overlay()
        for _ in range(20):
            ov.push_history()
        self.assertLessEqual(len(ov.history), 15)


class UndoRedoTest(unittest.TestCase):

    def test_undo_restores_previous_state(self):
        ov = _make_overlay()
        original_pixmap = ov.edit_pixmap.copy()
        ov.push_history()
        # 修改 pixmap
        ov.edit_pixmap.fill(QColor(255, 0, 0))
        ov.undo()
        # 应该恢复到原始状态
        self.assertEqual(ov.edit_pixmap.width(), original_pixmap.width())
        self.assertEqual(ov.edit_pixmap.height(), original_pixmap.height())

    def test_redo_after_undo(self):
        ov = _make_overlay()
        ov.push_history()
        modified = ov.edit_pixmap.copy()
        modified.fill(QColor(255, 0, 0))
        ov.edit_pixmap = modified
        ov.undo()
        self.assertEqual(len(ov.redo_stack), 1)
        ov.redo()
        self.assertEqual(len(ov.history), 1)

    def test_undo_empty_stack_noop(self):
        ov = _make_overlay()
        self.assertEqual(len(ov.history), 0)
        ov.undo()
        self.assertEqual(len(ov.history), 0)
        self.assertIn("没有可撤销", ov.message)

    def test_redo_empty_stack_noop(self):
        ov = _make_overlay()
        self.assertEqual(len(ov.redo_stack), 0)
        ov.redo()
        self.assertEqual(len(ov.redo_stack), 0)
        self.assertIn("没有可重做", ov.message)


class ClearAnnotationsTest(unittest.TestCase):

    def test_clear_annotations_resets_all(self):
        ov = _make_overlay()
        ov.push_history()
        ov.annotations.append({"type": "text", "x": 10, "y": 10, "text": "hello", "size": 28, "color": "#fff"})
        ov.active_tool = "arrow"
        ov.dragging_annotation = True
        ov.clear_annotations()
        self.assertEqual(len(ov.annotations), 0)
        self.assertEqual(len(ov.history), 0)
        self.assertEqual(ov.active_tool, "none")
        self.assertFalse(ov.dragging_annotation)

    def test_clear_empty_noop(self):
        ov = _make_overlay()
        ov.clear_annotations()
        self.assertIn("没有标注", ov.message)


class DeleteSelectedTextTest(unittest.TestCase):

    def test_delete_selected_text(self):
        ov = _make_overlay()
        ov.annotations.append({"type": "text", "x": 10, "y": 10, "text": "hello", "size": 28, "color": "#fff"})
        ov.selected_text_index = 0
        ov.delete_selected_text()
        self.assertEqual(len(ov.annotations), 0)
        self.assertIn("已删除", ov.message)

    def test_delete_no_selection_noop(self):
        ov = _make_overlay()
        ov.selected_text_index = -1
        ov.delete_selected_text()
        self.assertIn("没有选中", ov.message)


if __name__ == "__main__":
    unittest.main()
