"""UndoMixin — 撤销栈、清空标注、删除文字。"""

from __future__ import annotations

from typing import Dict, List

from PyQt6.QtGui import QPixmap


class UndoMixin:

    def copy_annotations(self) -> List[Dict[str, object]]:
        copied: List[Dict[str, object]] = []
        for item in self.annotations:
            cloned = dict(item)
            patch = cloned.get("patch")
            if isinstance(patch, QPixmap):
                cloned["patch"] = patch.copy()
            copied.append(cloned)
        return copied

    def push_history(self) -> None:
        if not self.edit_pixmap.isNull():
            self.history.append((
                self.edit_pixmap.copy(),
                self.copy_annotations(),
                bool(getattr(self, "selection_snapshot_required", False)),
            ))
            self.redo_stack.clear()
            if len(self.history) > 15:
                self.history.pop(0)

    def _reset_text_state(self) -> None:
        self.text_drag.reset()
        self.editing_text_index = -1

    def clear_annotations(self) -> None:
        if self.edit_pixmap.isNull():
            return
        if not self.annotations and not self.history:
            self.message = "当前没有标注可清空"
            self.update()
            return

        self.annotations.clear()
        self.history.clear()
        self.redo_stack.clear()
        self.active_tool = "none"
        self.dragging_annotation = False
        self.drag_start = None
        self.drag_end = None
        self.drag_path = []
        self._reset_text_state()
        self.adjust_preview_pixmap = QPixmap()
        self.adjust_cleared_annotations = False

        if not self.recapture_current_selection():
            self.message = "清空标注失败，请重新截图"
            self.update()
            return

        self.update_selection_display_cache()
        self.message = "已清空全部标注，可继续编辑或复制"
        self.update_drag_button_layout()
        self.update_toolbar_layout()
        self.repaint()

    def delete_selected_text(self) -> None:
        if self.selected_text_index < 0 or self.selected_text_index >= len(self.annotations):
            self.message = "当前没有选中的文字"
            self.update()
            return
        item = self.annotations[self.selected_text_index]
        if item.get("type") != "text":
            self.message = "当前没有选中的文字"
            self.update()
            return

        self.push_history()
        self.annotations.pop(self.selected_text_index)
        self._reset_text_state()
        self.rebuild_edit_pixmap()
        self.message = "已删除当前文字标注"
        self.update()

    def undo(self) -> None:
        if not self.history:
            self.message = "没有可撤销的操作"
            self.update()
            return
        self.redo_stack.append((
            self.edit_pixmap.copy(),
            self.copy_annotations(),
            bool(getattr(self, "selection_snapshot_required", False)),
        ))
        pixmap, annotations, snapshot_required = self.history.pop()
        self.edit_pixmap = pixmap
        self.edit_pixmap.setDevicePixelRatio(1.0)
        self.annotations = annotations
        self.selection_snapshot_required = bool(snapshot_required)
        self._reset_text_state()
        self.update_selection_display_cache()
        self.message = "已撤销，Ctrl+Y 可重做"
        self.update()

    def redo(self) -> None:
        if not self.redo_stack:
            self.message = "没有可重做的操作"
            self.update()
            return
        self.history.append((
            self.edit_pixmap.copy(),
            self.copy_annotations(),
            bool(getattr(self, "selection_snapshot_required", False)),
        ))
        pixmap, annotations, snapshot_required = self.redo_stack.pop()
        self.edit_pixmap = pixmap
        self.edit_pixmap.setDevicePixelRatio(1.0)
        self.annotations = annotations
        self.selection_snapshot_required = bool(snapshot_required)
        self._reset_text_state()
        self.update_selection_display_cache()
        self.message = "已重做"
        self.update()
