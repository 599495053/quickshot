"""ToolbarMixin — 工具栏/样式面板布局、点击检测、工具切换。"""

from __future__ import annotations

from typing import List, Optional, Tuple

from PyQt6.QtCore import QPoint, QRect


# 工具分类常量
DRAW_TOOLS = frozenset({"arrow", "rect", "ellipse", "dashed_rect", "pen", "highlight", "mosaic", "blur"})
STYLE_TOOLS = frozenset({"arrow", "rect", "ellipse", "dashed_rect", "pen", "highlight"})


class ToolbarMixin:

    # 样式面板几何常量（颜色/线宽两组选项）
    STYLE_COLOR_OPTION_SIZE = 26
    STYLE_WIDTH_OPTION_W = 32
    STYLE_WIDTH_OPTION_H = 24
    STYLE_PAD_X = 10
    STYLE_PAD_Y = 8
    STYLE_GAP_COLOR = 8
    STYLE_GAP_WIDTH = 6
    STYLE_ROW_GAP = 8

    # ── 工具栏布局 ──

    @staticmethod
    def toolbar_items() -> List[Tuple[str, str, str, str]]:
        return [
            ("arrow", "箭头", "", "箭头标注 A"),
            ("rect", "矩形", "", "矩形框 R"),
            ("ellipse", "椭圆", "", "椭圆标注 U"),
            ("dashed_rect", "虚线框", "", "虚线框 D"),
            ("pen", "画笔", "", "画笔 B"),
            ("highlight", "高亮", "", "高亮 H"),
            ("text", "文字", "", "文字标注 T"),
            ("number", "序号", "", "序号标注 N"),
            ("mosaic", "马赛克", "", "马赛克 M"),
            ("blur", "模糊", "", "模糊打码 L"),
            ("blur_all", "打码", "", "智能识别隐私信息并打码"),
            ("sep", "", "", ""),
            ("color", "颜色", "", "切换颜色"),
            ("width", "粗细", "", "切换线宽"),
            ("fill", "填充", "", "图形填充模式"),
            ("grid", "网格", "", "网格辅助 G"),
            ("size_lock", "锁尺寸", "", "锁定选区尺寸 K"),
            ("reuse", "复用", "", "复用上次选区 P"),
            ("sep", "", "", ""),
            ("ocr", "识文", "", "识别文字 O"),
            ("copy", "复制", "", "复制 Ctrl+C"),
            ("save", "保存", "", "保存 Ctrl+S"),
            ("pin", "贴图", "", "贴到桌面"),
            ("sep", "", "", ""),
            ("shadow", "阴影", "", "添加阴影"),
            ("border", "边框", "", "添加边框"),
            ("watermark", "水印", "", "添加水印"),
            ("sep", "", "", ""),
            ("undo", "撤销", "", "撤销 Ctrl+Z"),
            ("clear", "清空", "", "清空全部标注"),
            ("sep", "", "", ""),
            ("cancel", "取消", "", "取消 Esc"),
            ("done", "完成", "", "完成 Enter"),
        ]

    def _toolbar_cache_key(self) -> Optional[Tuple[int, int, int, int, int, int]]:
        if self.selection_rect.isNull():
            return None
        return (
            self.selection_rect.x(), self.selection_rect.y(),
            self.selection_rect.width(), self.selection_rect.height(),
            self.width(), self.height(),
        )

    def _update_toolbar_layout_if_needed(self) -> None:
        key = self._toolbar_cache_key()
        if key == self._toolbar_layout_geometry and self.toolbar_buttons:
            return
        self._toolbar_layout_geometry = key
        self.update_toolbar_layout()

    def update_toolbar_layout(self) -> None:
        self.toolbar_buttons.clear()
        self.toolbar_rect = QRect()
        if self.selection_rect.isNull():
            return

        items = self.toolbar_items()
        button_size = 42
        sep_w = 10
        pad_x = 10
        pad_y = 5
        spacing = 2

        compact_width = self.width() - 20
        if compact_width < 900:
            button_size = 38
            sep_w = 7
            pad_x = 8
        if compact_width < 760:
            button_size = 34
            sep_w = 5
            pad_x = 7
        if compact_width < 600:
            button_size = 30
            sep_w = 4
            pad_x = 5

        toolbar_w = pad_x * 2
        prev_button = False
        for key, _label, _icon, _tip in items:
            if key == "sep":
                toolbar_w += sep_w
                prev_button = False
            else:
                if prev_button:
                    toolbar_w += spacing
                toolbar_w += button_size
                prev_button = True

        toolbar_h = button_size + pad_y * 2
        x = self.selection_rect.center().x() - toolbar_w // 2
        x = max(10, min(self.width() - toolbar_w - 10, x))
        y = self.selection_rect.bottom() + 12
        if y + toolbar_h > self.height() - 10:
            y = self.selection_rect.top() - toolbar_h - 12
        if y < 10:
            y = 10

        self.toolbar_rect = QRect(x, y, toolbar_w, toolbar_h)
        bx = x + pad_x
        by = y + pad_y
        prev_button = False
        for key, _label, _icon, _tip in items:
            if key == "sep":
                bx += sep_w
                prev_button = False
                continue
            if prev_button:
                bx += spacing
            self.toolbar_buttons[key] = QRect(bx, by, button_size, button_size)
            bx += button_size
            prev_button = True

    def button_at(self, pos: QPoint) -> str:
        self._update_toolbar_layout_if_needed()
        for key, rect in self.toolbar_buttons.items():
            if rect.contains(pos):
                return key
        return ""

    # ── 样式面板布局 ──

    def panel_option_id(self, kind: str, value: str) -> str:
        return f"{kind}:{value}"

    def style_panel_option_at(self, pos: QPoint) -> str:
        self.update_style_panel_layout()
        for option_id, rect in self.style_panel_rects():
            if rect.contains(pos):
                return option_id
        return ""

    def style_panel_rects(self):
        return self.style_option_rects.items()

    def update_style_panel_layout(self) -> None:
        self.style_panel_rect = QRect()
        self.style_option_rects.clear()
        if self.style_panel_kind not in ("color", "width", "style"):
            return

        presets = getattr(self.config, "annotation_presets", []) if self.style_panel_kind == "style" else []

        if self.style_panel_kind == "style":
            anchor = self.toolbar_buttons.get("color")
            width_anchor = self.toolbar_buttons.get("width")
            if anchor is not None and width_anchor is not None:
                anchor = anchor.united(width_anchor)
            elif width_anchor is not None:
                anchor = QRect(width_anchor)
        else:
            anchor = self.toolbar_buttons.get(self.style_panel_kind)
        if anchor is None:
            return

        color_values = list(self.stroke_colors)
        width_values = [str(width) for width in self.stroke_widths]
        pad_x = self.STYLE_PAD_X
        pad_y = self.STYLE_PAD_Y

        if self.style_panel_kind == "color":
            size = self.STYLE_COLOR_OPTION_SIZE
            gap = self.STYLE_GAP_COLOR
            n = len(color_values)
            panel_w = pad_x * 2 + n * size + max(0, n - 1) * gap
            panel_h = pad_y * 2 + size
        elif self.style_panel_kind == "width":
            opt_w = self.STYLE_WIDTH_OPTION_W
            opt_h = self.STYLE_WIDTH_OPTION_H
            gap = self.STYLE_GAP_WIDTH
            n = len(width_values)
            panel_w = pad_x * 2 + n * opt_w + max(0, n - 1) * gap
            panel_h = pad_y * 2 + opt_h
        else:
            color_size = self.STYLE_COLOR_OPTION_SIZE
            opt_w = self.STYLE_WIDTH_OPTION_W
            opt_h = self.STYLE_WIDTH_OPTION_H
            gap = self.STYLE_GAP_COLOR
            row_gap = self.STYLE_ROW_GAP
            color_row_w = len(color_values) * color_size + max(0, len(color_values) - 1) * gap
            width_row_w = len(width_values) * opt_w + max(0, len(width_values) - 1) * gap
            content_w = max(color_row_w, width_row_w)
            panel_w = pad_x * 2 + content_w
            panel_h = pad_y * 2 + color_size + row_gap + opt_h
            # 预设行
            if presets:
                preset_btn_w = 80
                preset_btn_h = 24
                presets_row_w = len(presets) * preset_btn_w + max(0, len(presets) - 1) * gap
                content_w = max(content_w, presets_row_w)
                panel_w = pad_x * 2 + content_w
                panel_h += row_gap + preset_btn_h

        x = anchor.center().x() - panel_w // 2
        y = anchor.top() - panel_h - 8
        if y < 8:
            y = anchor.bottom() + 8
        x = max(8, min(self.width() - panel_w - 8, x))

        self.style_panel_rect = QRect(x, y, panel_w, panel_h)

        if self.style_panel_kind == "color":
            self._lay_out_color_row(color_values, x + pad_x, y + pad_y, self.STYLE_GAP_COLOR)
        elif self.style_panel_kind == "width":
            self._lay_out_width_row(width_values, x + pad_x, y + pad_y, self.STYLE_GAP_WIDTH)
        else:
            color_size = self.STYLE_COLOR_OPTION_SIZE
            opt_w = self.STYLE_WIDTH_OPTION_W
            gap = self.STYLE_GAP_COLOR
            row_gap = self.STYLE_ROW_GAP
            color_row_w = len(color_values) * color_size + max(0, len(color_values) - 1) * gap
            width_row_w = len(width_values) * opt_w + max(0, len(width_values) - 1) * gap
            content_w = max(color_row_w, width_row_w)
            if presets:
                preset_btn_w = 80
                presets_row_w = len(presets) * preset_btn_w + max(0, len(presets) - 1) * gap
                content_w = max(content_w, presets_row_w)
            color_x = x + pad_x + (content_w - color_row_w) // 2
            color_y = y + pad_y
            self._lay_out_color_row(color_values, color_x, color_y, gap)
            width_x = x + pad_x + (content_w - width_row_w) // 2
            width_y = y + pad_y + color_size + row_gap
            self._lay_out_width_row(width_values, width_x, width_y, gap)
            # 预设行
            if presets:
                preset_btn_w = 80
                preset_btn_h = 24
                presets_row_w = len(presets) * preset_btn_w + max(0, len(presets) - 1) * gap
                preset_x = x + pad_x + (content_w - presets_row_w) // 2
                preset_y = width_y + opt_h + row_gap
                self._lay_out_presets_row(presets, preset_x, preset_y, gap, preset_btn_w, preset_btn_h)

    def _lay_out_presets_row(self, presets: list, x: int, y: int, gap: int, btn_w: int, btn_h: int) -> None:
        cx = x
        for i, preset in enumerate(presets):
            self.style_option_rects[self.panel_option_id("preset", str(i))] = QRect(cx, y, btn_w, btn_h)
            cx += btn_w + gap

    def _lay_out_color_row(self, values: List[str], x: int, y: int, gap: int) -> None:
        size = self.STYLE_COLOR_OPTION_SIZE
        cx = x
        for value in values:
            self.style_option_rects[self.panel_option_id("color", value)] = QRect(cx, y, size, size)
            cx += size + gap

    def _lay_out_width_row(self, values: List[str], x: int, y: int, gap: int) -> None:
        opt_w = self.STYLE_WIDTH_OPTION_W
        opt_h = self.STYLE_WIDTH_OPTION_H
        cx = x
        for value in values:
            self.style_option_rects[self.panel_option_id("width", value)] = QRect(cx, y, opt_w, opt_h)
            cx += opt_w + gap

    # ── 交互 ──

    def toggle_style_panel(self, kind: str) -> None:
        target_kind = "style" if kind in ("color", "width") else kind
        if self.style_panel_kind == target_kind:
            self.style_panel_kind = ""
            self.hover_style_option = ""
        else:
            self.style_panel_kind = target_kind
            self.hover_style_option = ""
        self.update_style_panel_layout()
        if self.style_panel_kind:
            self.message = "选择标注样式"
        self.update()

    def close_style_panel(self) -> None:
        if not self.style_panel_kind and not self.hover_style_option:
            return
        self.style_panel_kind = ""
        self.hover_style_option = ""
        self.style_panel_rect = QRect()
        self.style_option_rects.clear()
        self.update()

    def apply_style_panel_option(self, option_id: str) -> None:
        if ":" not in option_id:
            return
        kind, value = option_id.split(":", 1)
        self.hover_style_option = ""
        if kind == "color":
            self.set_stroke_color(value)
        elif kind == "width":
            try:
                self.set_stroke_width(int(value))
            except ValueError:
                return
        elif kind == "preset":
            self.apply_preset(int(value))
            return
        else:
            return
        if self.style_panel_kind != "style":
            self.style_panel_kind = ""
            self.hover_style_option = ""
        self.update_style_panel_layout()
        self.update()

    def apply_preset(self, index: int) -> None:
        """应用指定索引的样式预设。"""
        presets = getattr(self.config, "annotation_presets", [])
        if 0 <= index < len(presets):
            preset = presets[index]
            self.set_stroke_color(preset.get("color", "#ff4646"))
            self.set_stroke_width(preset.get("width", 5))
            self.message = f"已应用预设：{preset.get('name', '未命名')}"
            self.close_style_panel()
            self.update()

    def save_current_as_preset(self) -> None:
        """将当前样式保存为新预设。"""
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(None, "保存样式预设", "预设名称：")
        if ok and name.strip():
            presets = getattr(self.config, "annotation_presets", [])
            presets.append({
                "name": name.strip(),
                "color": self.stroke_color_name,
                "width": self.stroke_width,
            })
            self.config.annotation_presets = presets
            self.config.save()
            self.message = f"已保存预设：{name.strip()}"
            self.update()

    def select_tool(self, tool: str) -> None:
        style_tools = STYLE_TOOLS
        if self.text_panel_visible():
            if tool == "text":
                self.settle_inline_text()
            else:
                self.commit_inline_text()
        if self.active_tool == tool:
            self.last_tool = self.active_tool
            self.active_tool = "none"
            self.close_style_panel()
            self.message = "已退出标注模式"
        else:
            if self.active_tool != "none":
                self.last_tool = self.active_tool
            self.active_tool = tool
            if tool in style_tools:
                self.style_panel_kind = "style"
                self.hover_style_option = ""
                self.update_style_panel_layout()
            else:
                self.close_style_panel()
            tips = {
                "arrow": "箭头模式：在选区内拖动即可画箭头",
                "rect": "矩形模式：在选区内拖动画框",
                "ellipse": "椭圆模式：在选区内拖动画椭圆",
                "dashed_rect": "虚线框模式：在选区内拖动画虚线框",
                "pen": "画笔模式：按住拖动自由标注",
                "highlight": "高亮模式：按住拖动标出重点",
                "text": "文字模式：点击选区内的位置输入文字",
                "number": "序号模式：点击位置放置序号标记",
                "mosaic": "马赛克模式：拖动选择要打码的区域",
                "blur": "模糊模式：拖动选择要模糊的区域",
            }
            self.message = tips.get(tool, "")
        self.dragging_annotation = False
        self.drag_start = None
        self.drag_end = None
        self.drag_path = []
        self.update()

    def switch_to_last_tool(self) -> None:
        """快速切换到上一个使用的工具。"""
        if self.last_tool != "none" and self.last_tool != self.active_tool:
            self.select_tool(self.last_tool)
        elif self.active_tool != "none":
            self.last_tool = self.active_tool
            self.active_tool = "none"
            self.close_style_panel()
            self.message = "已退出标注模式"
            self.update()
        self.update()

    def cycle_stroke_color(self) -> None:
        try:
            index = self.stroke_colors.index(self.stroke_color_name)
        except ValueError:
            index = -1
        self.set_stroke_color(self.stroke_colors[(index + 1) % len(self.stroke_colors)])

    def cycle_stroke_width(self) -> None:
        try:
            index = self.stroke_widths.index(int(self.stroke_width))
        except ValueError:
            index = -1
        self.set_stroke_width(self.stroke_widths[(index + 1) % len(self.stroke_widths)])

    def set_stroke_color(self, color_name: str) -> None:
        self.stroke_color_name = color_name
        self.message = f"标注颜色：{color_name}"
        self.update()

    def set_stroke_width(self, width: int) -> None:
        self.stroke_width = width
        self.message = f"标注线宽：{width}px"
        self.update()
