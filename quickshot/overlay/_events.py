"""EventMixin — 鼠标/键盘事件处理、工具栏命令分发。"""

from __future__ import annotations

import time
from typing import Dict

from PyQt6.QtCore import QPoint, QRect, QSize, Qt

from ._toolbar import DRAW_TOOLS
from ._tool_strategies import TOOL_STRATEGIES, ToolContext


# ── 命令分发表 ──
# keyPressEvent 和 handle_toolbar_action 共用，消除两处重复的 if-elif 链。
# 格式: command_id -> method_name
# 特殊前缀: "tool:xxx" 表示调用 select_tool("xxx")

_COMMAND_METHODS: Dict[str, str] = {
    "copy": "copy_current",
    "save": "save_current",
    "pin": "pin_current",
    "ocr": "recognize_current_text",
    "undo": "undo",
    "redo": "redo",
    "clear": "clear_annotations",
    "done": "finish",
    "cancel": "close",
    "shadow": "apply_shadow",
    "border": "apply_border",
    "watermark": "apply_watermark",
    "color": "toggle_style_panel",
    "width": "toggle_style_panel",
    "fill": "cycle_fill_mode",
    "grid": "toggle_grid",
    "blur_all": "apply_mosaic_to_selection",
}

_TOOL_KEYS = {
    "arrow", "rect", "ellipse", "dashed_rect",
    "pen", "highlight", "text", "number", "mosaic", "blur",
    "picker",
}

# 键盘键 -> 命令映射（Ctrl 修饰符）
_CTRL_KEY_COMMANDS = {
    Qt.Key.Key_C: "copy",
    Qt.Key.Key_S: "save",
    Qt.Key.Key_Z: "undo",
    Qt.Key.Key_Y: "redo",
}

# 无修饰符键 -> 工具名映射（默认值，可被 config.edit_tool_hotkeys 覆盖）
_DEFAULT_TOOL_KEY_MAP = {
    Qt.Key.Key_A: "arrow",
    Qt.Key.Key_R: "rect",
    Qt.Key.Key_B: "pen",
    Qt.Key.Key_H: "highlight",
    Qt.Key.Key_T: "text",
    Qt.Key.Key_M: "mosaic",
    Qt.Key.Key_U: "ellipse",
    Qt.Key.Key_D: "dashed_rect",
    Qt.Key.Key_N: "number",
    Qt.Key.Key_L: "blur",
    Qt.Key.Key_I: "picker",
}

# 工具名 -> 默认键名（用于 settings UI 展示和反向查找）
TOOL_DEFAULT_KEYS = {v: k for k, v in _DEFAULT_TOOL_KEY_MAP.items()}

# 键名字符串 -> Qt.Key 映射（用于从 config 字符串还原 Qt 键码）
_NAME_TO_QT_KEY: Dict[str, int] = {
    "A": Qt.Key.Key_A, "B": Qt.Key.Key_B, "C": Qt.Key.Key_C,
    "D": Qt.Key.Key_D, "E": Qt.Key.Key_E, "F": Qt.Key.Key_F,
    "G": Qt.Key.Key_G, "H": Qt.Key.Key_H, "I": Qt.Key.Key_I,
    "J": Qt.Key.Key_J, "K": Qt.Key.Key_K, "L": Qt.Key.Key_L,
    "M": Qt.Key.Key_M, "N": Qt.Key.Key_N, "O": Qt.Key.Key_O,
    "P": Qt.Key.Key_P, "Q": Qt.Key.Key_Q, "R": Qt.Key.Key_R,
    "S": Qt.Key.Key_S, "T": Qt.Key.Key_T, "U": Qt.Key.Key_U,
    "V": Qt.Key.Key_V, "W": Qt.Key.Key_W, "X": Qt.Key.Key_X,
    "Y": Qt.Key.Key_Y, "Z": Qt.Key.Key_Z,
}


def build_tool_key_map(config) -> Dict[int, str]:
    """从 config.edit_tool_hotkeys 构建 Qt.Key -> tool_name 映射。

    config.edit_tool_hotkeys 格式: {"arrow": "A", "rect": "R", ...}
    未配置的工具使用默认映射。
    """
    custom = getattr(config, "edit_tool_hotkeys", None) or {}
    result = dict(_DEFAULT_TOOL_KEY_MAP)
    # 先移除被自定义覆盖的工具对应的旧键
    for tool_name, key_name in custom.items():
        if tool_name not in _TOOL_KEYS:
            continue
        key_name_u = str(key_name).strip().upper()
        if not key_name_u:
            continue
        qt_key = _NAME_TO_QT_KEY.get(key_name_u)
        if qt_key is None:
            continue
        # 移除该键对应的旧工具（避免冲突）
        old_tool = result.get(qt_key)
        if old_tool and old_tool != tool_name:
            continue  # 保留旧工具，不覆盖（自定义优先级低于冲突检测）
        # 移除该工具在默认映射中的旧键
        old_key = TOOL_DEFAULT_KEYS.get(tool_name)
        if old_key is not None:
            result.pop(old_key, None)
        result[qt_key] = tool_name
    return result


class EventMixin:
    """事件处理：鼠标按下/移动/释放、键盘、双击、工具栏命令。"""

    _last_cursor_shape: int = -1

    # ── 命令执行 ──

    def _execute_command(self, command: str) -> None:
        """统一的命令执行入口。"""
        if command in _TOOL_KEYS:
            self.select_tool(command)
            return
        method_name = _COMMAND_METHODS.get(command)
        if method_name:
            method = getattr(self, method_name, None)
            if method:
                if command in ("color", "width"):
                    method("style")
                else:
                    method()

    # ── 鼠标事件 ──

    def _handle_mouse_press_select_mode(self, pos: QPoint) -> None:
        """处理选择模式下的鼠标点击。"""
        self.start = pos
        self.end = pos
        self.selecting = True
        self._snap_edges = []
        # 吸附窗口列表由覆盖层空闲预热；鼠标按下保持轻量，避免第一帧拖动卡顿。
        if getattr(self.config, 'snap_to_windows', True) and not self._snap_windows_loaded:
            self._schedule_snap_prewarm(80)
        self.request_frame_update()

    def _handle_ocr_running_click(self, pos: QPoint) -> bool:
        """OCR运行中时的点击处理。返回True表示已处理。"""
        key = self.button_at(pos)
        if key == "cancel":
            self.close()
            return True
        self.message = "正在识别当前截图，请稍候..."
        self.update()
        return True

    def _handle_text_panel_click(self, pos: QPoint, event) -> bool:
        """文本面板区域的点击处理。返回True表示已处理。"""
        if self.text_editor_panel.geometry().contains(pos):
            return True
        if event.button() == Qt.MouseButton.LeftButton:
            self.settle_inline_text()
            if self.active_tool == "text" and self.selection_rect.contains(pos):
                image_pos = self.widget_to_image(pos)
                if image_pos is not None:
                    self.open_inline_text_editor(image_pos)
                return True
        return False

    def _handle_text_drag_start(self, pos: QPoint) -> bool:
        """文本标注拖拽开始。返回True表示已处理。"""
        text_index = self.text_annotation_at(pos)
        if text_index >= 0:
            self.text_drag.selected_index = text_index
            image_pos = self.widget_to_image(pos)
            if image_pos is not None:
                self.push_history()
                self.text_drag.begin_drag(
                    text_index,
                    QPoint(int(self.annotations[text_index].get("x", 0)),
                           int(self.annotations[text_index].get("y", 0))),
                    image_pos,
                )
                self.text_drag.hover_index = text_index
                self.close_style_panel()
                self.setCursor(Qt.CursorShape.SizeAllCursor)
                self.update()
                return True
        elif self.text_drag.selected_index >= 0:
            self.text_drag.selected_index = -1
            self.update()
        return False

    def _handle_selection_area_click(self, pos: QPoint, image_pos: QPoint) -> bool:
        """选区内点击处理（OCR区域模式、文本、取色器、序号、标注工具）。返回True表示已处理。"""
        if self.active_tool == "none":
            if getattr(self, "ocr_region_mode", False):
                self.drag_start = image_pos
                self.drag_end = image_pos
                self.dragging_annotation = True
                self.update()
                return True
            return False
        if self.active_tool == "text":
            self.open_inline_text_editor(image_pos)
        elif self.active_tool == "picker":
            self._pick_color_at(image_pos)
        elif self.active_tool == "number":
            self.push_history()
            self.draw_number_on_pixmap(QPoint(image_pos))
            self.message = f"已添加序号 #{self.number_counter - 1}，点击继续"
            self.update()
        elif self.active_tool in DRAW_TOOLS:
            self.drag_start = image_pos
            self.drag_end = image_pos
            if self.active_tool in ("pen", "highlight"):
                self.drag_path = [image_pos]
            self.dragging_annotation = True
            self.update()
        return True

    def _handle_mouse_press_edit_mode(self, pos: QPoint, event) -> None:
        """处理编辑模式下的鼠标点击。"""
        if self.ocr_running():
            if self._handle_ocr_running_click(pos):
                return

        key = self.button_at(pos)
        if key:
            self.handle_toolbar_action(key)
            return

        style_option = self.style_panel_option_at(pos)
        if style_option:
            if event.button() == Qt.MouseButton.LeftButton:
                self.apply_style_panel_option(style_option)
            return
        if self.style_panel_kind and not self.style_panel_rect.contains(pos):
            self.close_style_panel()

        if self.privacy_preview_active():
            if event.button() == Qt.MouseButton.LeftButton:
                self.begin_privacy_preview_drag(pos)
            return

        if self.text_panel_visible():
            if self._handle_text_panel_click(pos, event):
                return

        if event.button() == Qt.MouseButton.LeftButton:
            if self.active_tool == "none":
                if self._handle_text_drag_start(pos):
                    return
                handle = self.selection_handle_at(pos)
                if handle:
                    if self.annotations or self.history:
                        self.message = "已有标注，先清空/撤销标注或重新截图后再调整选区"
                        self.update()
                        return
                    self.begin_selection_adjust(handle, pos)
                    return

            if self.selection_rect.contains(pos):
                image_pos = self.widget_to_image(pos)
                if image_pos is None:
                    return
                self._handle_selection_area_click(pos, image_pos)

    def _handle_mouse_press(self, event) -> None:
        """鼠标按下事件入口。"""
        if event.button() == Qt.MouseButton.RightButton:
            self.close()
            return

        pos = self.clamp_point(event.position().toPoint())
        if self.mode == "select":
            if event.button() != Qt.MouseButton.LeftButton:
                return
            self._handle_mouse_press_select_mode(pos)
            return

        if self.mode == "edit":
            self._handle_mouse_press_edit_mode(pos, event)

    def _handle_mouse_move(self, event) -> None:
        pos = self.clamp_point(event.position().toPoint())
        if self.mode == "select" and self.selecting:
            old_rect = QRect(self.current_select_rect())
            old_edges = list(self._snap_edges)
            new_end = QPoint(pos)
            new_edges = []
            if (
                getattr(self.config, 'snap_to_windows', True)
                and not self._snap_windows_loaded
                and not getattr(self, "_snap_refresh_pending", False)
            ):
                self._schedule_snap_prewarm(80)
            # 应用窗口吸附
            if self._snap_window_logical_rects:
                raw_rect = QRect(self.start, pos).normalized()
                snapped_rect, snap_edges = self._apply_snap(raw_rect)
                new_edges = snap_edges
                if snapped_rect.width() > 0 and snapped_rect.height() > 0:
                    # 根据鼠标拖拽方向选择吸附矩形的对应角点作为 end
                    if pos.x() >= self.start.x():
                        if pos.y() >= self.start.y():
                            new_end = snapped_rect.bottomRight()
                        else:
                            new_end = snapped_rect.topRight()
                    else:
                        if pos.y() >= self.start.y():
                            new_end = snapped_rect.bottomLeft()
                        else:
                            new_end = snapped_rect.topLeft()
            if new_end == self.end and new_edges == old_edges:
                return
            self.end = new_end
            self._snap_edges = new_edges
            new_rect = self.current_select_rect()
            if new_rect == old_rect and new_edges == old_edges:
                return
            dirty = self.selection_frame_dirty_rect(old_rect, new_rect)
            self.request_frame_update(dirty)
            return

        if self.mode == "edit":
            if self.ocr_running():
                self.setCursor(Qt.CursorShape.BusyCursor)
                return

            if self.adjusting_selection:
                self.update_selection_adjust(pos)
                return

            if self.privacy_preview_active():
                if self.update_privacy_preview_drag(pos):
                    return

            hover = self.button_at(pos)
            hover_style = self.style_panel_option_at(pos) if self.style_panel_kind else ""
            hover_text = self.text_annotation_at(pos) if self.active_tool == "none" and not self.text_panel_visible() else -1
            if hover != self.hover_button or hover_style != self.hover_style_option:
                self.hover_button = hover
                self.hover_style_option = hover_style
                self.hover_drag_button = False
                self.update()
            elif self.active_tool == "picker" and self.selection_rect.contains(pos):
                self.request_frame_update()  # 取色器需要持续刷新以显示放大镜
            if hover_text != self.text_drag.hover_index and not self.text_drag.is_dragging:
                self.text_drag.hover_index = hover_text
                self.update()

            if self.dragging_annotation:
                image_pos = self.widget_to_image(pos, clamped=True)
                if image_pos is not None:
                    dirty = self.edit_repaint_rect()
                    self.drag_end = image_pos
                    if self.active_tool in ("pen", "highlight"):
                        path = getattr(self, "drag_path", [])
                        if not path or (path[-1] - image_pos).manhattanLength() >= 2:
                            path.append(image_pos)
                            self.drag_path = path
                    dirty = dirty.united(self.edit_repaint_rect()).adjusted(-12, -12, 12, 12)
                    self.request_frame_update(dirty)
                return
            if self.text_drag.is_dragging:
                image_pos = self.widget_to_image(pos, clamped=True)
                if image_pos is not None:
                    dirty = self.edit_repaint_rect()
                    self.text_drag.update_drag(image_pos)
                    dirty = dirty.united(self.edit_repaint_rect()).adjusted(-12, -12, 12, 12)
                    self.request_frame_update(dirty)
                return

            if hover:
                cursor = Qt.CursorShape.PointingHandCursor
            elif hover_style:
                cursor = Qt.CursorShape.PointingHandCursor
            elif hover_text >= 0:
                cursor = Qt.CursorShape.SizeAllCursor
            elif self.active_tool == "none":
                handle = self.selection_handle_at(pos)
                cursor = self.cursor_for_handle(handle)
            elif self.selection_rect.contains(pos) and self.active_tool in DRAW_TOOLS:
                cursor = Qt.CursorShape.CrossCursor
            elif self.selection_rect.contains(pos) and self.active_tool == "number":
                cursor = Qt.CursorShape.CrossCursor
            elif self.selection_rect.contains(pos) and self.active_tool == "picker":
                cursor = Qt.CursorShape.CrossCursor
            elif self.selection_rect.contains(pos) and getattr(self, "ocr_region_mode", False):
                cursor = Qt.CursorShape.CrossCursor
            elif self.selection_rect.contains(pos) and self.active_tool == "text":
                cursor = Qt.CursorShape.IBeamCursor
            else:
                cursor = Qt.CursorShape.ArrowCursor
            if cursor != self._last_cursor_shape:
                self._last_cursor_shape = cursor
                self.setCursor(cursor)

    def _handle_mouse_release(self, event) -> None:
        pos = self.clamp_point(event.position().toPoint())
        if self.mode == "select":
            if event.button() != Qt.MouseButton.LeftButton or not self.selecting:
                return
            # 清除吸附参考线（self.end 已在拖拽时设为吸附位置，不要覆盖）
            self._snap_edges = []
            logical_rect = self.current_select_rect()
            self.selecting = False
            self._snap_windows_loaded = False
            self._snap_refresh_pending = False
            self._snap_window_logical_rects = []
            physical_rect = self.logical_to_physical_rect(logical_rect)
            if physical_rect.width() < 8 or physical_rect.height() < 8:
                self.close()
                return
            self.enter_edit_mode(logical_rect, physical_rect)
            return

        if self.mode == "edit" and event.button() == Qt.MouseButton.LeftButton and self.adjusting_selection:
            self.update_selection_adjust(pos)
            self.finish_selection_adjust()
            return

        if self.mode == "edit" and event.button() == Qt.MouseButton.LeftButton and self.privacy_preview_active():
            if self.finish_privacy_preview_drag(pos):
                return

        if self.mode == "edit" and event.button() == Qt.MouseButton.LeftButton and self.dragging_annotation:
            image_pos = self.widget_to_image(pos)
            if image_pos is not None:
                self.drag_end = image_pos
            start = self.drag_start
            end = self.drag_end
            self.dragging_annotation = False
            self.drag_start = None
            self.drag_end = None
            if start is not None and end is not None and getattr(self, "ocr_region_mode", False):
                self.ocr_region_mode = False
                region = QRect(start, end).normalized()
                if region.width() >= 8 and region.height() >= 8:
                    self.recognize_region(region)
                else:
                    self.message = "选区太小，请拖动更大的区域"
                    self.update()
                self.drag_path = []
                return
            if start is not None and end is not None:
                self._commit_annotation(start, end)
            self.drag_path = []
            self.update()
            return

        if self.mode == "edit" and event.button() == Qt.MouseButton.LeftButton and self.text_drag.is_dragging:
            self._commit_text_drag(pos)

    def _build_tool_context(self) -> ToolContext:
        """构建工具策略上下文。"""
        return ToolContext(
            start=self.drag_start,
            end=self.drag_end,
            path=list(getattr(self, "drag_path", [])),
            active_tool=self.active_tool,
            push_history=self.push_history,
            draw_arrow_on_pixmap=self.draw_arrow_on_pixmap,
            draw_rect_on_pixmap=self.draw_rect_on_pixmap,
            draw_ellipse_on_pixmap=self.draw_ellipse_on_pixmap,
            draw_dashed_rect_on_pixmap=self.draw_dashed_rect_on_pixmap,
            draw_freehand_on_pixmap=self.draw_freehand_on_pixmap,
            draw_highlight_on_pixmap=self.draw_highlight_on_pixmap,
            apply_mosaic=self.apply_mosaic,
            apply_blur=self.apply_blur,
            draw_arrow_preview=self.draw_arrow_preview,
            draw_rect_preview=self.draw_rect_preview,
            draw_ellipse_preview=self.draw_ellipse_preview,
            draw_dashed_rect_preview=self.draw_dashed_rect_preview,
            draw_freehand_preview=self.draw_freehand_preview,
            draw_mosaic_preview=self.draw_mosaic_preview,
            draw_blur_preview=self.draw_blur_preview,
        )

    _TOOL_MESSAGES = {
        "arrow": "已添加箭头",
        "rect": "已添加矩形框",
        "ellipse": "已添加椭圆标注",
        "dashed_rect": "已添加虚线框",
        "pen": "已添加画笔标注",
        "highlight": "已添加高亮",
        "mosaic": "已添加马赛克",
        "blur": "已添加模糊打码",
    }

    def _commit_annotation(self, start: QPoint, end: QPoint) -> None:
        """提交标注绘制（由 mouseRelease 调用）。"""
        strategy = TOOL_STRATEGIES.get(self.active_tool)
        if strategy:
            ctx = self._build_tool_context()
            ctx.start = start
            ctx.end = end
            strategy.commit(ctx)
            self.message = self._TOOL_MESSAGES.get(self.active_tool, "")

    def _commit_text_drag(self, pos: QPoint) -> None:
        """提交文字拖拽（由 mouseRelease 调用）。"""
        image_pos = self.widget_to_image(pos)
        if image_pos is not None:
            self.text_drag.update_drag(image_pos)
        td = self.text_drag
        idx = td.dragging_index
        item = self.annotations[idx] if 0 <= idx < len(self.annotations) else None
        origin, start, current = td.end_drag()
        if item is not None and origin is not None and start is not None and current is not None:
            delta = current - start
            new_x = int(max(0, min(self.edit_pixmap.width() - 1, origin.x() + delta.x())))
            new_y = int(max(0, min(self.edit_pixmap.height() - 1, origin.y() + delta.y())))
            if new_x == origin.x() and new_y == origin.y():
                if self.history:
                    self.history.pop()
            else:
                item["x"] = new_x
                item["y"] = new_y
                self.text_drag.selected_index = idx
                self.rebuild_edit_pixmap()
                self.message = "已移动文字标注"
        else:
            if self.history:
                self.history.pop()
        self.update()

    # ── 双击 ──

    def _handle_mouse_double_click(self, event) -> None:
        """双击选区完成截图复制。带防误触保护：选区创建后短时间内不响应双击。"""
        if self.mode == "edit" and event.button() == Qt.MouseButton.LeftButton:
            pos = self.clamp_point(event.position().toPoint())
            if self.active_tool == "none" and not self.text_panel_visible():
                text_index = self.text_annotation_at(pos)
                if text_index >= 0:
                    item = self.annotations[text_index]
                    if item.get("type") == "text":
                        self.text_drag.selected_index = text_index
                        self.text_font_size = int(item.get("size", self.text_font_size))
                        self.text_color_name = str(item.get("color", self.text_color_name))
                        self.select_text_color(self.text_color_name)
                        self.open_inline_text_editor(
                            QPoint(int(item.get("x", 0)), int(item.get("y", 0))),
                            existing_text=str(item.get("text", "")),
                            editing_index=text_index,
                        )
                        return
            if self.selection_rect.contains(pos) and self.active_tool == "none":
                elapsed_ms = (time.monotonic() - self._edit_entered_at) * 1000
                if elapsed_ms < self.DOUBLE_CLICK_GUARD_MS:
                    return
                self.finish()
                return

    # ── 键盘事件 ──

    def _handle_escape_key(self) -> bool:
        """Escape键处理。返回True表示已处理。"""
        if self.adjusting_selection:
            self.selection_rect = QRect(self.adjust_origin_rect)
            self.recapture_current_selection()
            self.adjusting_selection = False
            self.adjust_mode = ""
            self.adjust_handle = ""
            self.adjust_start = QPoint()
            self.adjust_origin_rect = QRect()
            self.message = "已取消选区调整"
            self.update_toolbar_layout()
            self.update()
            return True
        if self.privacy_preview_active():
            self.cancel_privacy_preview()
            return True
        self.close()
        return True

    def _handle_select_mode_key(self, key) -> bool:
        """选择模式下的按键处理。返回True表示已处理。"""
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            logical_rect = self.current_select_rect()
            physical_rect = self.logical_to_physical_rect(logical_rect)
            if physical_rect.width() >= 8 and physical_rect.height() >= 8:
                self.enter_edit_mode(logical_rect, physical_rect)
            return True
        return False

    def _handle_text_panel_key(self, key, ctrl: bool) -> bool:
        """文本面板打开时的按键处理。返回True表示已处理。"""
        if key == Qt.Key.Key_Escape:
            self.cancel_inline_text()
            return True
        if ctrl and key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.commit_inline_text()
            return True
        return False

    def _handle_ocr_running_key(self, key) -> bool:
        """OCR运行中的按键处理。返回True表示已处理。"""
        if key == Qt.Key.Key_Escape:
            self.close()
            return True
        self.message = "正在识别当前截图，请稍候..."
        self.update()
        return True

    def _handle_ctrl_key(self, key) -> bool:
        """Ctrl组合键处理。返回True表示已处理。"""
        command = _CTRL_KEY_COMMANDS.get(key)
        if command:
            self._execute_command(command)
            return True
        return False

    def _handle_delete_backspace_key(self) -> bool:
        """Delete/Backspace键处理。返回True表示已处理。"""
        if self.text_drag.selected_index >= 0:
            self.delete_selected_text()
        else:
            self.clear_annotations()
        return True

    def _handle_enter_key(self) -> bool:
        """Enter键处理。返回True表示已处理。"""
        if getattr(self, "ocr_region_mode", False):
            self.ocr_region_mode = False
            self.recognize_current_text()
        else:
            self.finish()
        return True

    def _handle_ocr_toggle_key(self) -> bool:
        """O键OCR区域模式切换。返回True表示已处理。"""
        if getattr(self, "ocr_region_mode", False):
            self.ocr_region_mode = False
            self.recognize_current_text()
        else:
            self.ocr_region_mode = True
            self.message = "拖动选择 OCR 区域，或按 Enter 识别全部"
            self.update()
        return True

    def _handle_function_keys(self, key, event) -> bool:
        """功能键处理（G、Tab、方向键）。返回True表示已处理。"""
        if key == Qt.Key.Key_G:
            self.toggle_grid()
            return True
        elif key == Qt.Key.Key_Tab:
            self.switch_to_last_tool()
            return True
        elif key in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right):
            self.nudge_selection(event)
            return True
        return False

    def _handle_key_press(self, event) -> None:
        """键盘按下事件入口。"""
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        key = event.key()

        # Escape: 取消调整 / 关闭
        if key == Qt.Key.Key_Escape:
            self._handle_escape_key()
            return

        # select 模式: Enter 进入编辑
        if self.mode == "select":
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._handle_select_mode_key(key)
            return

        if self.mode != "edit":
            return

        # 文字面板打开时的特殊处理
        if self.text_panel_visible():
            if self._handle_text_panel_key(key, ctrl):
                return

        # OCR 运行中
        if self.ocr_running():
            self._handle_ocr_running_key(key)
            return

        if self.privacy_preview_active():
            self.handle_privacy_preview_key(key, event.modifiers())
            return

        # Ctrl 组合键
        if ctrl:
            if self._handle_ctrl_key(key):
                return

        # Delete/Backspace
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._handle_delete_backspace_key()
            return

        # Enter
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._handle_enter_key()
            return

        # O 键: OCR 区域模式切换
        if key == Qt.Key.Key_O:
            self._handle_ocr_toggle_key()
            return

        # 工具快捷键（从 config 动态构建）
        tool = build_tool_key_map(self.config).get(key)
        if tool:
            self.select_tool(tool)
            return

        # 功能键
        self._handle_function_keys(key, event)

    # ── 工具栏命令 ──

    def handle_toolbar_action(self, key: str) -> None:
        if self.ocr_running() and key != "cancel":
            self.message = "正在识别当前截图，请稍候..."
            self.update()
            return
        if self.privacy_preview_active():
            if key == "done":
                self.apply_privacy_preview()
            elif key == "cancel":
                self.cancel_privacy_preview()
            elif key == "clear":
                self.delete_selected_privacy_preview_rect()
            else:
                self.message = "请先按 Enter 应用智能打码预览，或按 Esc 取消"
                self.update()
            return
        if self.text_panel_visible() and key not in ("text", "cancel"):
            self.commit_inline_text()
        self._execute_command(key)

    # ── 辅助方法 ──

    FILL_MODES = ("none", "half", "full")
    FILL_LABELS = {"none": "无填充", "half": "半透明填充", "full": "完全填充"}

    def cycle_fill_mode(self) -> None:
        """循环切换矩形/椭圆的填充模式。"""
        idx = self.FILL_MODES.index(self.fill_mode) if self.fill_mode in self.FILL_MODES else 0
        self.fill_mode = self.FILL_MODES[(idx + 1) % len(self.FILL_MODES)]
        label = self.FILL_LABELS.get(self.fill_mode, self.fill_mode)
        self.message = f"图形填充：{label}"
        self.update()

    def toggle_grid(self) -> None:
        """切换网格辅助显示。"""
        self.grid_visible = not self.grid_visible
        self.message = "网格辅助：开" if self.grid_visible else "网格辅助：关"
        self.update()

    def _pick_color_at(self, image_pos) -> None:
        """取色器：采样像素颜色，应用到标注颜色并复制到剪贴板。"""
        from ..utils import copy_text_to_clipboard
        x, y = int(image_pos.x()), int(image_pos.y())
        if self.edit_pixmap.isNull():
            return
        if x < 0 or y < 0 or x >= self.edit_pixmap.width() or y >= self.edit_pixmap.height():
            return
        # 使用缓存的 QImage，避免每次取色都做全量 toImage() 转换
        cached_image = self._get_cached_edit_image()
        if cached_image is None:
            return
        color = cached_image.pixelColor(x, y)
        hex_str = color.name().upper()
        rgb_str = f"rgb({color.red()}, {color.green()}, {color.blue()})"
        # 应用到标注颜色
        self.stroke_color_name = hex_str
        copy_text_to_clipboard(hex_str)
        self.message = f"已取色 {hex_str} ({rgb_str})，已设为标注颜色并复制到剪贴板"
        self.update()

    def toggle_size_lock(self) -> None:
        """切换选区尺寸锁定。"""
        if self.size_locked:
            self.size_locked = False
            self.message = "尺寸锁定：关"
        else:
            if self.selection_rect.isNull():
                self.message = "请先选择区域"
            else:
                self.size_locked = True
                self.locked_size = QSize(self.selection_rect.width(), self.selection_rect.height())
                self.message = f"尺寸锁定：{self.locked_size.width()} × {self.locked_size.height()}"
        self.update()

    def reuse_last_selection(self) -> None:
        """复用上次选区区域。"""
        cls = self.__class__
        if cls._last_selection_rect is None or cls._last_selection_rect.isNull():
            self.message = "没有可复用的历史选区"
            self.update()
            return
        logical_rect = QRect(cls._last_selection_rect)
        physical_rect = QRect(cls._last_selection_physical_rect)
        logical_rect = logical_rect.intersected(self.rect())
        if logical_rect.width() < 8 or logical_rect.height() < 8:
            self.message = "历史选区超出当前屏幕范围"
            self.update()
            return
        self.enter_edit_mode(logical_rect, physical_rect)

    def apply_mosaic_to_selection(self) -> None:
        """智能打码：识别隐私信息并应用马赛克。"""
        if self.selection_rect.isNull() or self.edit_pixmap.isNull():
            self.message = "请先选择截图区域"
            self.update()
            return
        if self.privacy_preview_active():
            self.message = "已有智能打码预览；请先按 Enter 应用或 Esc 取消"
            self.update()
            return
        if getattr(self, '_privacy_blur_running', False):
            self.message = "正在识别隐私信息，请稍候..."
            self.update()
            return
        self._privacy_blur_running = True
        self.message = "正在识别隐私信息..."
        self.update()
        from ..ocr import create_privacy_blur_job
        self._privacy_blur_job = create_privacy_blur_job(self.edit_pixmap.toImage())
        self._privacy_blur_job.succeeded.connect(self._on_privacy_blur_succeeded)
        self._privacy_blur_job.failed.connect(self._on_privacy_blur_failed)
        self._privacy_blur_job.finished.connect(self._on_privacy_blur_finished)
        self._privacy_blur_job.start()

    def _on_privacy_blur_succeeded(self, rects) -> None:
        if not rects:
            self.message = "未检测到隐私信息（手机号、身份证、邮箱、银行卡）"
            self.update()
            return
        if not self.start_privacy_preview(rects):
            self.message = "检测结果太小或超出截图区域，未生成可用打码框"
            self.update()

    def _on_privacy_blur_failed(self, error: str) -> None:
        from ..feedback import compact_error_message

        self.message = compact_error_message("智能隐私打码失败", error, max_length=180)
        self.update()

    def _on_privacy_blur_finished(self) -> None:
        self._privacy_blur_running = False
        if hasattr(self, '_privacy_blur_job') and self._privacy_blur_job:
            self._privacy_blur_job.cleanup()
            self._privacy_blur_job = None

    def nudge_selection(self, event) -> None:
        """方向键微调选区位置：普通 1px，Shift+方向键 10px。"""
        if self.selection_rect.isNull() or self.active_tool != "none":
            return
        if self.text_panel_visible():
            return
        delta = 10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
        dx, dy = 0, 0
        if event.key() == Qt.Key.Key_Up:
            dy = -delta
        elif event.key() == Qt.Key.Key_Down:
            dy = delta
        elif event.key() == Qt.Key.Key_Left:
            dx = -delta
        elif event.key() == Qt.Key.Key_Right:
            dx = delta
        else:
            return
        new_rect = QRect(self.selection_rect)
        new_rect.translate(dx, dy)
        new_rect = self.move_rect_within_screen(new_rect)
        if new_rect == self.selection_rect:
            return
        if self.annotations or self.history:
            self.history.clear()
            self.annotations.clear()
        self.selection_rect = new_rect
        self.recapture_current_selection()
        self.message = f"选区微调 ({dx:+d}, {dy:+d})"
        self.update_toolbar_layout()
        self.update()
