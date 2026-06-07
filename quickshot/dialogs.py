from typing import Dict, Optional

from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QToolButton,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from .theme import (
    ACCENT_BASE,
    BORDER_BTN,
    RADIUS_MD,
    dialog_extras_stylesheet,
)
from .ui import APP_STYLE, make_card, set_button_role
from .utils import load_app_icon


from ._manager_delegates import build_header_card as build_dialog_header


class OcrResultDialog(QDialog):
    def __init__(
        self,
        text: str,
        parent: Optional[QWidget] = None,
        engine_label: str = "",
        elapsed_seconds: float = 0.0,
        note: str = "",
    ) -> None:
        super().__init__(parent)
        self.text = text
        self.setWindowTitle("文字识别结果")
        self.setWindowIcon(load_app_icon())
        self.resize(900, 720)

        header_card = build_dialog_header(
            "文字识别结果",
            "结果已经复制到剪贴板，你可以在这里校对、清洗或转换格式。",
        )

        self.title_label = QLabel("识别结果已复制，可继续整理后再复制")
        self.title_label.setObjectName("title")

        self.meta_label = QLabel(self.format_meta(engine_label, elapsed_seconds, note))
        self.meta_label.setObjectName("meta")
        self.meta_label.setWordWrap(True)
        self.meta_label.setVisible(bool(self.meta_label.text()))

        info_card = make_card()
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(16, 16, 16, 16)
        info_layout.setSpacing(8)
        info_layout.addWidget(self.title_label)
        info_layout.addWidget(self.meta_label)
        info_card.setLayout(info_layout)

        editor_card = make_card()
        editor_layout = QVBoxLayout()
        editor_layout.setContentsMargins(16, 16, 16, 16)
        editor_layout.setSpacing(10)

        editor_title = QLabel("文本内容")
        editor_title.setObjectName("sectionTitle")
        editor_hint = QLabel("轻清洗会保留分行，强清洗会压成单段文本。")
        editor_hint.setObjectName("helper")

        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(text)
        self.text_edit.setAcceptRichText(False)
        self.text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)

        editor_layout.addWidget(editor_title)
        editor_layout.addWidget(editor_hint)
        editor_layout.addWidget(self.text_edit, 1)

        editor_card.setLayout(editor_layout)

        # 翻译结果区域（独立卡片，默认隐藏）
        self.translate_card = make_card()
        translate_layout = QVBoxLayout()
        translate_layout.setContentsMargins(16, 16, 16, 16)
        translate_layout.setSpacing(10)

        self.translate_title = QLabel("翻译结果")
        self.translate_title.setObjectName("sectionTitle")
        self.translate_title.hide()

        self.translate_edit = QTextEdit()
        self.translate_edit.setAcceptRichText(False)
        self.translate_edit.setReadOnly(True)
        self.translate_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.translate_edit.setMinimumHeight(120)
        self.translate_edit.hide()

        self._translate_btn_copy = set_button_role(QPushButton("复制译文"))
        self._translate_btn_copy.clicked.connect(self.copy_translation)
        self._translate_btn_copy.hide()

        translate_layout.addWidget(self.translate_title)
        translate_layout.addWidget(self.translate_edit, 1)
        translate_layout.addWidget(self._translate_btn_copy)
        self.translate_card.setLayout(translate_layout)
        self.translate_card.hide()

        copy_btn = set_button_role(QPushButton("复制文本"), "primary")
        copy_btn.clicked.connect(self.copy_text)
        search_btn = set_button_role(QPushButton("搜索"))
        search_btn.clicked.connect(self.search_text)
        translate_btn = set_button_role(QPushButton("翻译"))
        translate_btn.clicked.connect(self.translate_text)

        # 更多操作下拉菜单
        more_btn = QToolButton()
        more_btn.setText("更多操作")
        more_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        more_menu = QMenu(more_btn)
        more_menu.addAction("复制原文", self.copy_raw_text)
        more_menu.addAction("复制一行", self.copy_single_line)
        more_menu.addAction("合并成一行", self.merge_to_single_line)
        more_menu.addSeparator()
        more_menu.addAction("整理空行", self.clean_lines)
        more_menu.addAction("轻清洗", self.clean_soft)
        more_menu.addAction("强清洗", self.clean_hard)
        more_menu.addAction("深度清洗", self.clean_deep)
        more_menu.addSeparator()
        more_menu.addAction("提取数字", self.extract_numbers)
        more_menu.addAction("提取中文", self.extract_chinese)
        more_menu.addSeparator()
        more_menu.addAction("转 Markdown 表格", self.convert_to_markdown_table)
        more_menu.addAction("导出 CSV", self.export_csv)
        more_btn.setMenu(more_menu)

        close_btn = set_button_role(QPushButton("关闭"))
        close_btn.clicked.connect(self.accept)

        action_card = make_card()
        action_layout = QVBoxLayout()
        action_layout.setContentsMargins(16, 16, 16, 16)
        action_layout.setSpacing(8)
        action_title = QLabel("快捷操作")
        action_title.setObjectName("sectionTitle")

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(8)
        action_row.addWidget(copy_btn)
        action_row.addWidget(search_btn)
        action_row.addWidget(translate_btn)
        action_row.addWidget(more_btn)
        action_row.addStretch(1)
        action_row.addWidget(close_btn)

        action_layout.addWidget(action_title)
        action_layout.addLayout(action_row)
        action_card.setLayout(action_layout)

        layout = QVBoxLayout()
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.addWidget(header_card)
        layout.addWidget(info_card)
        layout.addWidget(editor_card, 1)
        layout.addWidget(self.translate_card)
        layout.addWidget(action_card)
        self.setLayout(layout)
        self.apply_style()

    @staticmethod
    def format_meta(engine_label: str, elapsed_seconds: float, note: str) -> str:
        parts = []
        if engine_label:
            parts.append(f"引擎：{engine_label}")
        if elapsed_seconds > 0:
            parts.append(f"耗时：{elapsed_seconds:.2f} 秒")
        meta = "  ·  ".join(parts)
        if note:
            return f"{meta}\n{note}" if meta else note
        return meta

    def current_text(self) -> str:
        return self.text_edit.toPlainText()

    def single_line_text(self) -> str:
        return " ".join(self.current_text().split())

    def copy_text(self) -> None:
        QApplication.clipboard().setText(self.current_text())
        self.title_label.setText("已复制校对后的文本")

    def copy_raw_text(self) -> None:
        QApplication.clipboard().setText(self.text)
        self.title_label.setText("已复制原始识别文本")

    def copy_single_line(self) -> None:
        QApplication.clipboard().setText(self.single_line_text())
        self.title_label.setText("已复制为一行")

    def merge_to_single_line(self) -> None:
        self.text_edit.setPlainText(self.single_line_text())
        self.title_label.setText("已合并成一行")

    def clean_lines(self) -> None:
        from .ocr import clean_lines_text
        self.text_edit.setPlainText(clean_lines_text(self.current_text()))
        self.title_label.setText("已整理空行和首尾空格")

    def clean_soft(self) -> None:
        from .ocr import clean_soft_text
        self.text_edit.setPlainText(clean_soft_text(self.current_text()))
        self.title_label.setText("已完成轻清洗")

    def clean_hard(self) -> None:
        from .ocr import clean_hard_text
        self.text_edit.setPlainText(clean_hard_text(self.current_text()))
        self.title_label.setText("已完成强清洗并合并")

    def clean_deep(self) -> None:
        from .ocr import deep_clean_ocr_text
        text = deep_clean_ocr_text(self.current_text())
        self.text_edit.setPlainText(text)
        self.title_label.setText("已完成深度清洗")

    def extract_numbers(self) -> None:
        from .ocr import extract_numbers
        numbers = extract_numbers(self.current_text())
        if numbers:
            self.text_edit.setPlainText("\n".join(numbers))
            self.title_label.setText(f"已提取 {len(numbers)} 个数字")
        else:
            self.title_label.setText("未找到数字")

    def extract_chinese(self) -> None:
        from .ocr import extract_chinese
        chinese = extract_chinese(self.current_text())
        if chinese:
            self.text_edit.setPlainText(chinese)
            self.title_label.setText("已提取中文文本")
        else:
            self.title_label.setText("未找到中文文本")

    def search_text(self) -> None:
        import urllib.parse
        import webbrowser
        text = self.current_text().strip()
        if not text:
            self.title_label.setText("没有可搜索的文本")
            return
        url = f"https://www.baidu.com/s?wd={urllib.parse.quote(text)}"
        webbrowser.open(url)
        self.title_label.setText("已在浏览器中打开搜索")

    def translate_text(self) -> None:
        text = self.current_text().strip()
        if not text:
            self.title_label.setText("没有可翻译的文本")
            return

        # 禁用按钮，显示翻译中状态
        sender = self.sender()
        if sender:
            sender.setEnabled(False)
            sender.setText("翻译中…")
        self.title_label.setText("正在翻译，请稍候…")

        # 启动异步翻译
        from .translator import TranslateJob

        self._translate_job = TranslateJob(text, parent=self)
        self._translate_job.succeeded.connect(self._on_translate_succeeded)
        self._translate_job.failed.connect(self._on_translate_failed)
        self._translate_job.finished.connect(lambda: self._on_translate_finished(sender))
        self._translate_job.start()

    def _on_translate_succeeded(self, result: str) -> None:
        self.translate_edit.setPlainText(result)
        self.translate_card.show()
        self.translate_title.show()
        self.translate_edit.show()
        self._translate_btn_copy.show()
        self.title_label.setText("翻译完成")

    def _on_translate_failed(self, error: str) -> None:
        self.title_label.setText(error)

    def _on_translate_finished(self, button) -> None:
        if button:
            button.setEnabled(True)
            button.setText("翻译")

    def copy_translation(self) -> None:
        text = self.translate_edit.toPlainText().strip()
        if text:
            QApplication.clipboard().setText(text)
            self.title_label.setText("已复制翻译结果")

    def _parse_table_rows(self) -> list:
        """从当前文本解析出表格行（优先 tab 分隔，其次多空格分隔）。"""
        rows = []
        for line in self.current_text().splitlines():
            line = line.strip()
            if not line:
                continue
            if "\t" in line:
                parts = [p.strip() for p in line.split("\t") if p.strip()]
            else:
                parts = [p.strip() for p in line.split("  ") if p.strip()]
                if len(parts) <= 1:
                    parts = [p.strip() for p in line.split() if p.strip()]
            if parts:
                rows.append(parts)
        return rows

    def convert_to_markdown_table(self) -> None:
        rows = self._parse_table_rows()
        if not rows:
            self.title_label.setText("没有可转换的表格文本")
            return
        col_count = max(len(row) for row in rows)
        padded = [row + [""] * (col_count - len(row)) for row in rows]
        header = padded[0]
        table_lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join("---" for _ in range(col_count)) + " |",
        ]
        for row in padded[1:]:
            table_lines.append("| " + " | ".join(row) + " |")
        self.text_edit.setPlainText("\n".join(table_lines))
        self.title_label.setText("已转换为 Markdown 表格")

    def export_csv(self) -> None:
        """将文本按行解析为 CSV 并复制到剪贴板。"""
        import csv
        import io
        rows = self._parse_table_rows()
        if not rows:
            self.title_label.setText("没有可导出的数据")
            return
        buf = io.StringIO()
        writer = csv.writer(buf)
        for row in rows:
            writer.writerow(row)
        QApplication.clipboard().setText(buf.getvalue())
        self.title_label.setText(f"已导出 CSV（{len(rows)} 行）并复制到剪贴板")

    def apply_style(self) -> None:
        self.setStyleSheet(APP_STYLE + dialog_extras_stylesheet())


class TextAnnotationDialog(QDialog):
    COLORS = [
        ("#ffffff", "白"),
        ("#ff4d4f", "红"),
        ("#ffd43b", "黄"),
        ("#40c057", "绿"),
        ("#339af0", "蓝"),
        ("#212529", "黑"),
    ]

    def __init__(
        self,
        default_size: int = 28,
        default_color: str = "#ffffff",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.selected_color = default_color if default_color else "#ffffff"
        self.color_buttons: Dict[str, QPushButton] = {}

        self.setWindowTitle("添加文字")
        self.setWindowIcon(load_app_icon())
        self.resize(520, 360)

        header_card = build_dialog_header(
            "添加文字",
            "输入要标注的内容，设置字号和颜色后直接放到截图上。",
        )

        editor_card = make_card()
        editor_layout = QVBoxLayout()
        editor_layout.setContentsMargins(16, 16, 16, 16)
        editor_layout.setSpacing(10)

        title = QLabel("文字内容")
        title.setObjectName("sectionTitle")

        self.text_edit = QTextEdit()
        self.text_edit.setAcceptRichText(False)
        self.text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.text_edit.setPlaceholderText("支持多行文字")

        options_card = make_card()
        options_layout = QVBoxLayout()
        options_layout.setContentsMargins(16, 16, 16, 16)
        options_layout.setSpacing(10)

        size_label = QLabel("字号")
        size_label.setObjectName("fieldLabel")
        self.size_spin = QSpinBox()
        self.size_spin.setRange(12, 72)
        self.size_spin.setSingleStep(2)
        self.size_spin.setValue(max(12, min(72, int(default_size))))

        color_label = QLabel("颜色")
        color_label.setObjectName("fieldLabel")
        color_row = QHBoxLayout()
        color_row.setContentsMargins(0, 0, 0, 0)
        color_row.setSpacing(8)
        for color, name in self.COLORS:
            button = QPushButton()
            button.setFixedSize(32, 32)
            button.setToolTip(name)
            button.clicked.connect(lambda _checked=False, c=color: self.select_color(c))
            self.color_buttons[color] = button
            color_row.addWidget(button)
        color_row.addStretch(1)

        options_row = QHBoxLayout()
        options_row.setContentsMargins(0, 0, 0, 0)
        options_row.setSpacing(12)
        options_row.addWidget(size_label)
        options_row.addWidget(self.size_spin)
        options_row.addSpacing(12)
        options_row.addWidget(color_label)
        options_row.addLayout(color_row, 1)

        options_layout.addLayout(options_row)
        options_card.setLayout(options_layout)

        ok_btn = set_button_role(QPushButton("添加"), "primary")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        cancel_btn = set_button_role(QPushButton("取消"))
        cancel_btn.clicked.connect(self.reject)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(ok_btn)
        button_row.addWidget(cancel_btn)

        editor_layout.addWidget(title)
        editor_layout.addWidget(self.text_edit, 1)
        editor_card.setLayout(editor_layout)

        layout = QVBoxLayout()
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.addWidget(header_card)
        layout.addWidget(editor_card, 1)
        layout.addWidget(options_card)
        layout.addLayout(button_row)
        self.setLayout(layout)

        self.apply_style()
        self.select_color(self.selected_color)

    def text(self) -> str:
        return self.text_edit.toPlainText().strip()

    def font_size(self) -> int:
        return int(self.size_spin.value())

    def color_name(self) -> str:
        return self.selected_color

    def select_color(self, color: str) -> None:
        self.selected_color = color
        for button_color, button in self.color_buttons.items():
            border = ACCENT_BASE if button_color == color else BORDER_BTN
            width = 2 if button_color == color else 1
            button.setStyleSheet(
                f"""
                QPushButton {{
                    background: {button_color};
                    border: {width}px solid {border};
                    border-radius: {RADIUS_MD}px;
                }}
                QPushButton:hover {{
                    border-color: {ACCENT_BASE};
                }}
                """
            )

    def apply_style(self) -> None:
        self.setStyleSheet(APP_STYLE + dialog_extras_stylesheet())
