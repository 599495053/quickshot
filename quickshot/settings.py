from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


def _disable_wheel(widget: QWidget) -> None:
    """忽略 QSpinBox/QComboBox 的滚轮事件，避免滚动设置页时误改值。"""
    widget.wheelEvent = lambda event: event.ignore()

from .config import Config, StartupManager
from .history import CaptureHistoryStore
from .theme import settings_extras_stylesheet
from .ui import APP_STYLE, make_card, set_button_role
from .utils import APP_NAME, APP_VERSION, CUSTOM_FOR_NAME, load_app_icon


class HotkeyCaptureEdit(QLineEdit):
    """点击后捕获键盘组合键的输入框。"""

    hotkey_captured = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("点击设置快捷键")
        self._capturing = False
        self._current_value = ""

    def set_hotkey(self, text: str) -> None:
        self._current_value = text
        self.setText(text)

    def hotkey(self) -> str:
        return self._current_value

    def mousePressEvent(self, event) -> None:
        self._capturing = True
        self._current_value = self.text()
        self.setText("")
        self.setPlaceholderText("请按下快捷键组合...")
        self.setProperty("capturing", True)
        self.style().unpolish(self)
        self.style().polish(self)
        super().mousePressEvent(event)

    def focusOutEvent(self, event) -> None:
        if self._capturing:
            self._capturing = False
            if not self.text():
                self.setText(self._current_value)
            self.setPlaceholderText("点击设置快捷键")
            self.setProperty("capturing", False)
            self.style().unpolish(self)
            self.style().polish(self)
        super().focusOutEvent(event)

    def keyPressEvent(self, event) -> None:
        if not self._capturing:
            return
        key = event.key()
        # 忽略纯修饰键
        if key in (
            Qt.Key.Key_Control, Qt.Key.Key_Shift,
            Qt.Key.Key_Alt, Qt.Key.Key_Meta,
        ):
            return
        from .hotkey_util import qt_key_to_name, validate_hotkey

        mods = event.modifiers()
        parts = []
        if mods & Qt.KeyboardModifier.ControlModifier:
            parts.append("Ctrl")
        if mods & Qt.KeyboardModifier.ShiftModifier:
            parts.append("Shift")
        if mods & Qt.KeyboardModifier.AltModifier:
            parts.append("Alt")
        if mods & Qt.KeyboardModifier.MetaModifier:
            parts.append("Win")

        vk_name = qt_key_to_name(key)
        if not vk_name:
            return
        parts.append(vk_name)

        combo = "+".join(parts)
        valid, _ = validate_hotkey(combo)
        if valid:
            self._current_value = combo
            self.setText(combo)
            self.hotkey_captured.emit(combo)
        self._capturing = False
        self.setPlaceholderText("点击设置快捷键")
        self.setProperty("capturing", False)
        self.style().unpolish(self)
        self.style().polish(self)
        self.clearFocus()


class SettingsWindow(QWidget):
    hotkeys_changed = pyqtSignal()

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config
        self.history_store = CaptureHistoryStore(config)
        self._nav_buttons = []
        self.setWindowTitle(f"{APP_NAME} V{APP_VERSION} 设置 - for {CUSTOM_FOR_NAME}")
        self.resize(1040, 720)
        self.setMinimumSize(920, 640)
        self.setWindowIcon(load_app_icon())
        self._create_controls()
        self._build_settings_layout()
        self.apply_style()

    def _create_controls(self) -> None:
        self.save_dir_edit = QLineEdit(self.config.save_dir)
        self.save_dir_edit.setReadOnly(True)
        self.choose_save_dir_btn = set_button_role(QPushButton("选择文件夹"))
        self.choose_save_dir_btn.clicked.connect(self.choose_save_dir)

        self.save_mode_combo = QComboBox()
        _disable_wheel(self.save_mode_combo)
        self.save_mode_combo.addItem("平铺（所有文件在同一目录）", "flat")
        self.save_mode_combo.addItem("按日期（年/月日 子目录）", "date")
        for i in range(self.save_mode_combo.count()):
            if self.save_mode_combo.itemData(i) == self.config.save_dir_mode:
                self.save_mode_combo.setCurrentIndex(i)
                break
        self.save_mode_combo.currentIndexChanged.connect(self.on_save_mode_changed)

        self.auto_copy_check = QCheckBox("截图完成后自动复制到剪贴板")
        self.auto_copy_check.setChecked(self.config.auto_copy)
        self.auto_copy_check.stateChanged.connect(self.on_auto_copy_changed)

        self.workflow_ocr_check = QCheckBox("截图完成后自动 OCR 并把文本写入剪贴板（会覆盖图片）")
        self.workflow_ocr_check.setChecked(getattr(self.config, "workflow_auto_ocr", False))
        self.workflow_ocr_check.stateChanged.connect(self.on_workflow_ocr_changed)

        self.workflow_upload_check = QCheckBox("截图完成后自动上传")
        self.workflow_upload_check.setChecked(getattr(self.config, "workflow_auto_upload", False))
        self.workflow_upload_check.stateChanged.connect(self.on_workflow_upload_changed)

        self.workflow_md_check = QCheckBox("上传成功后自动复制 Markdown 链接")
        self.workflow_md_check.setChecked(getattr(self.config, "workflow_copy_markdown", False))
        self.workflow_md_check.stateChanged.connect(self.on_workflow_md_changed)

        self.uploader_combo = QComboBox()
        _disable_wheel(self.uploader_combo)
        self.uploader_combo.addItem("本地存档", "local")
        self.uploader_combo.addItem("GitHub 仓库", "github")
        current_uploader = getattr(self.config, "workflow_uploader", "local")
        for i in range(self.uploader_combo.count()):
            if self.uploader_combo.itemData(i) == current_uploader:
                self.uploader_combo.setCurrentIndex(i)
                break
        self.uploader_combo.currentIndexChanged.connect(self.on_uploader_changed)

        self.github_owner_edit = QLineEdit()
        self.github_owner_edit.setPlaceholderText("GitHub 用户名或组织名")
        self.github_owner_edit.setText(getattr(self.config, "github_owner", ""))
        self.github_owner_edit.editingFinished.connect(self.on_github_owner_changed)

        self.github_repo_edit = QLineEdit()
        self.github_repo_edit.setPlaceholderText("仓库名（如 screenshots）")
        self.github_repo_edit.setText(getattr(self.config, "github_repo", ""))
        self.github_repo_edit.editingFinished.connect(self.on_github_repo_changed)

        self.github_branch_edit = QLineEdit()
        self.github_branch_edit.setPlaceholderText("分支（默认 main）")
        self.github_branch_edit.setText(getattr(self.config, "github_branch", "main"))
        self.github_branch_edit.editingFinished.connect(self.on_github_branch_changed)

        self.github_prefix_edit = QLineEdit()
        self.github_prefix_edit.setPlaceholderText("路径前缀（默认 screenshots）")
        self.github_prefix_edit.setText(getattr(self.config, "github_path_prefix", "screenshots"))
        self.github_prefix_edit.editingFinished.connect(self.on_github_prefix_changed)

        self.github_token_edit = QLineEdit()
        self.github_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.github_token_edit.setPlaceholderText("Personal Access Token（保存到系统凭据，不存配置文件）")
        # 不在 UI 中回显已存的 token，避免泄露
        self._github_token_loaded = self._load_github_token_into_field()

        self.github_token_save_btn = set_button_role(QPushButton("保存 Token"), "primary")
        self.github_token_save_btn.clicked.connect(self.on_github_token_save)

        self.github_token_clear_btn = set_button_role(QPushButton("清除 Token"), "secondary")
        self.github_token_clear_btn.clicked.connect(self.on_github_token_clear)

        self.startup_check = QCheckBox("开机自动启动")
        self.startup_check.setChecked(StartupManager.is_enabled())
        self.startup_check.stateChanged.connect(self.on_startup_changed)

        self.notification_check = QCheckBox("复制、保存、完成后显示右下角提示")
        self.notification_check.setChecked(self.config.show_notifications)
        self.notification_check.stateChanged.connect(self.on_notification_changed)

        self.hdr_accurate_check = QCheckBox("HDR 截图优先色彩准确（会出现 Windows 录制边框）")
        self.hdr_accurate_check.setChecked(self.config.hdr_color_accurate)
        self.hdr_accurate_check.stateChanged.connect(self.on_hdr_color_accurate_changed)

        self.watermark_edit = QLineEdit(self.config.watermark_text)
        self.watermark_edit.setPlaceholderText("留空则使用当前日期时间")
        self.watermark_edit.textChanged.connect(self.on_watermark_changed)

        self.watermark_color_combo = QComboBox()
        _disable_wheel(self.watermark_color_combo)
        watermark_colors = [
            ("白色半透明（默认）", "#ffffff40"),
            ("白色较明显", "#ffffff80"),
            ("白色完全不透明", "#ffffffff"),
            ("黑色半透明", "#00000080"),
            ("黑色较明显", "#000000b0"),
            ("红色半透明", "#ff000060"),
            ("蓝色半透明", "#0000ff60"),
        ]
        for name, color in watermark_colors:
            self.watermark_color_combo.addItem(name, color)
        for i in range(self.watermark_color_combo.count()):
            if self.watermark_color_combo.itemData(i) == self.config.watermark_color:
                self.watermark_color_combo.setCurrentIndex(i)
                break
        self.watermark_color_combo.currentIndexChanged.connect(self.on_watermark_color_changed)

        self.grid_color_combo = QComboBox()
        _disable_wheel(self.grid_color_combo)
        grid_colors = [
            ("白色半透明（默认）", "#ffffff80"),
            ("白色较明显", "#ffffffb0"),
            ("白色完全不透明", "#ffffffff"),
            ("黄色半透明", "#ffff0080"),
            ("红色半透明", "#ff000080"),
            ("蓝色半透明", "#0000ff80"),
            ("黑色半透明", "#00000080"),
        ]
        for name, color in grid_colors:
            self.grid_color_combo.addItem(name, color)
        for i in range(self.grid_color_combo.count()):
            if self.grid_color_combo.itemData(i) == self.config.grid_color:
                self.grid_color_combo.setCurrentIndex(i)
                break
        self.grid_color_combo.currentIndexChanged.connect(self.on_grid_color_changed)

        self.delay_spin = QSpinBox()
        _disable_wheel(self.delay_spin)
        self.delay_spin.setRange(0, 10)
        self.delay_spin.setValue(self.config.delay_seconds)
        self.delay_spin.setSuffix(" 秒")
        self.delay_spin.setSpecialValueText("不延迟")
        self.delay_spin.valueChanged.connect(self.on_delay_changed)

        self.region_hotkey_edit = HotkeyCaptureEdit()
        self.region_hotkey_edit.set_hotkey(self.config.region_hotkey)
        self.region_hotkey_edit.hotkey_captured.connect(self.on_region_hotkey_changed)
        self.region_reset_btn = set_button_role(QPushButton("重置"), compact=True)
        self.region_reset_btn.clicked.connect(lambda: self.reset_hotkey("region"))

        self.window_hotkey_edit = HotkeyCaptureEdit()
        self.window_hotkey_edit.set_hotkey(self.config.window_hotkey)
        self.window_hotkey_edit.hotkey_captured.connect(self.on_window_hotkey_changed)
        self.window_reset_btn = set_button_role(QPushButton("重置"), compact=True)
        self.window_reset_btn.clicked.connect(lambda: self.reset_hotkey("window"))

        self.history_hotkey_edit = HotkeyCaptureEdit()
        self.history_hotkey_edit.set_hotkey(self.config.history_hotkey)
        self.history_hotkey_edit.hotkey_captured.connect(self.on_history_hotkey_changed)
        self.history_reset_btn = set_button_role(QPushButton("清除"), compact=True)
        self.history_reset_btn.clicked.connect(lambda: self.reset_hotkey("history"))

        self.pin_hotkey_edit = HotkeyCaptureEdit()
        self.pin_hotkey_edit.set_hotkey(self.config.pin_hotkey)
        self.pin_hotkey_edit.hotkey_captured.connect(self.on_pin_hotkey_changed)
        self.pin_reset_btn = set_button_role(QPushButton("清除"), compact=True)
        self.pin_reset_btn.clicked.connect(lambda: self.reset_hotkey("pin"))

        self.ocr_hotkey_edit = HotkeyCaptureEdit()
        self.ocr_hotkey_edit.set_hotkey(self.config.ocr_hotkey)
        self.ocr_hotkey_edit.hotkey_captured.connect(self.on_ocr_hotkey_changed)
        self.ocr_reset_btn = set_button_role(QPushButton("清除"), compact=True)
        self.ocr_reset_btn.clicked.connect(lambda: self.reset_hotkey("ocr"))

        self.history_check = QCheckBox("自动保存截图到历史库")
        self.history_check.setChecked(self.config.auto_history)
        self.history_check.stateChanged.connect(self.on_history_changed)

        self.history_limit_spin = QSpinBox()
        _disable_wheel(self.history_limit_spin)
        self.history_limit_spin.setRange(20, 1000)
        self.history_limit_spin.setSingleStep(20)
        self.history_limit_spin.setValue(self.config.history_limit)
        self.history_limit_spin.valueChanged.connect(self.on_history_limit_changed)

        self.hotkey_help_label = QLabel(self._build_help_text())
        self.hotkey_help_label.setObjectName("helper")
        self.hotkey_help_label.setWordWrap(True)

        self.export_btn = set_button_role(QPushButton("导出设置"))
        self.export_btn.clicked.connect(self.export_settings)
        self.import_btn = set_button_role(QPushButton("导入设置"))
        self.import_btn.clicked.connect(self.import_settings)
        self.close_btn = set_button_role(QPushButton("关闭"), "primary")
        self.close_btn.clicked.connect(self.close)

    def _build_settings_layout(self) -> None:
        header_card = make_card("heroCard")
        icon_label = QLabel()
        icon_label.setObjectName("headerIcon")
        icon_label.setPixmap(load_app_icon().pixmap(40, 40))
        icon_label.setFixedSize(56, 56)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel(f"QuickShot V{APP_VERSION} 设置")
        title.setObjectName("heroTitle")
        subtitle = QLabel("常用配置即时生效；高级项收纳在对应分类。")
        subtitle.setObjectName("heroSubtitle")

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(2)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(22, 16, 22, 16)
        header_row.setSpacing(16)
        header_row.addWidget(icon_label)
        header_row.addLayout(title_box, 1)
        header_card.setLayout(header_row)

        nav = QFrame()
        nav.setObjectName("settingsSidebar")
        nav_layout = QVBoxLayout()
        nav_layout.setContentsMargins(10, 14, 10, 14)
        nav_layout.setSpacing(2)
        nav.setLayout(nav_layout)

        nav_title = QLabel("设置")
        nav_title.setObjectName("sidebarTitle")
        nav_layout.addWidget(nav_title)
        nav_layout.addSpacing(4)

        self.settings_stack = QStackedWidget()
        pages = [
            ("常用", "保存、启动、提示与延迟截图", self._build_general_page()),
            ("截图外观", "HDR、网格、水印与辅助显示", self._build_visual_page()),
            ("自动化", "截图后的 OCR、上传和链接复制", self._build_workflow_page()),
            ("快捷键", "全局快捷键与截图后快捷操作", self._build_hotkey_page()),
            ("历史库", "历史保存策略和容量控制", self._build_history_page()),
            ("操作说明", "工具键位、鼠标操作和窗口快捷键", self._build_help_page()),
        ]
        for index, (name, desc, page) in enumerate(pages):
            button = set_button_role(QPushButton(name), "nav")
            button.setCheckable(True)
            button.setMinimumSize(190, 40)
            button.setToolTip(desc)
            button.clicked.connect(lambda _checked=False, i=index: self.switch_settings_page(i))
            self._nav_buttons.append(button)
            nav_layout.addWidget(button)
            self.settings_stack.addWidget(page)
        nav_layout.addStretch(1)

        body = QHBoxLayout()
        body.setContentsMargins(20, 12, 20, 12)
        body.setSpacing(16)
        body.addWidget(nav, 0)
        body.addWidget(self.settings_stack, 1)

        footer = QFrame()
        footer.setObjectName("footer")
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(22, 12, 22, 14)
        footer_layout.setSpacing(12)
        footer_hint = self._helper("修改即时保存。Token 存于系统凭据，不写入配置文件。")
        footer_hint.setObjectName("footerHelper")
        footer_layout.addWidget(footer_hint, 1)
        footer_layout.addWidget(self.close_btn)
        footer.setLayout(footer_layout)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header_card)
        layout.addLayout(body, 1)
        layout.addWidget(footer)
        self.setLayout(layout)
        self.switch_settings_page(0)

    def _build_general_page(self) -> QScrollArea:
        page, layout = self._page()
        save_card, save_layout = self._card("保存位置", "保存目录和文件组织方式。")
        save_row = QHBoxLayout()
        save_row.setContentsMargins(0, 0, 0, 0)
        save_row.setSpacing(8)
        save_row.addWidget(self.save_dir_edit, 1)
        save_row.addWidget(self.choose_save_dir_btn)
        self._add_field(save_layout, "保存目录", save_row)
        self._add_field(save_layout, "目录组织方式", self.save_mode_combo)
        page.addWidget(save_card)

        behavior_card, behavior_layout = self._card("常用行为", "这些是日常最常改的开关。")
        behavior_layout.addWidget(self.auto_copy_check)
        behavior_layout.addWidget(self.notification_check)
        behavior_layout.addWidget(self.startup_check)
        self._add_field(behavior_layout, "延迟截图", self.delay_spin, "用于捕获菜单、悬浮提示等瞬时状态，0 秒表示不延迟。")
        page.addWidget(behavior_card)

        backup_card, backup_layout = self._card("配置备份", "导入导出不包含 GitHub Token。")
        backup_row = QHBoxLayout()
        backup_row.setContentsMargins(0, 0, 0, 0)
        backup_row.setSpacing(8)
        backup_row.addWidget(self.export_btn)
        backup_row.addWidget(self.import_btn)
        backup_row.addStretch(1)
        backup_layout.addLayout(backup_row)
        page.addWidget(backup_card)
        page.addStretch(1)
        return layout

    def _build_visual_page(self) -> QScrollArea:
        page, layout = self._page()
        capture_card, capture_layout = self._card("截图行为", "影响截图捕获质量和系统提示。")
        capture_layout.addWidget(self.hdr_accurate_check)
        capture_layout.addWidget(self._helper("默认关闭：HDR 截图无边框，适合日常截图。开启后色彩更准确，但 Windows 会显示金色录制边框。"))
        page.addWidget(capture_card)

        assist_card, assist_layout = self._card("辅助显示", "网格用于构图参考，可在编辑模式按 G 切换。")
        self._add_field(assist_layout, "网格辅助线颜色", self.grid_color_combo)
        page.addWidget(assist_card)

        watermark_card, watermark_layout = self._card("水印", "点击工具栏水印按钮时使用这里的内容和颜色。")
        self._add_field(watermark_layout, "自定义水印", self.watermark_edit, "留空则使用当前日期时间。")
        self._add_field(watermark_layout, "水印颜色", self.watermark_color_combo)
        page.addWidget(watermark_card)
        page.addStretch(1)
        return layout

    def _build_workflow_page(self) -> QScrollArea:
        page, layout = self._page()
        workflow_card, workflow_layout = self._card("截图后自动化", "把高频后续动作交给 QuickShot。")
        workflow_layout.addWidget(self.workflow_ocr_check)
        workflow_layout.addWidget(self.workflow_upload_check)
        workflow_layout.addWidget(self.workflow_md_check)
        self._add_field(workflow_layout, "上传到", self.uploader_combo)
        workflow_layout.addWidget(self._helper("自动 OCR 会把识别文本写入剪贴板；自动上传开启后才会使用上传器配置。"))
        page.addWidget(workflow_card)

        github_card, github_layout = self._card("GitHub 上传器", "仅在上传器选择 GitHub 仓库时生效。")
        self._add_field(github_layout, "用户名或组织", self.github_owner_edit)
        self._add_field(github_layout, "仓库名", self.github_repo_edit)
        self._add_field(github_layout, "分支", self.github_branch_edit)
        self._add_field(github_layout, "路径前缀", self.github_prefix_edit)
        self._add_field(github_layout, "Personal Access Token", self.github_token_edit)
        token_row = QHBoxLayout()
        token_row.setContentsMargins(0, 0, 0, 0)
        token_row.setSpacing(8)
        token_row.addWidget(self.github_token_save_btn)
        token_row.addWidget(self.github_token_clear_btn)
        token_row.addStretch(1)
        github_layout.addLayout(token_row)
        github_layout.addWidget(self._helper("Token 需要 repo 权限，保存在 Windows 凭据管理器，不会写入设置文件。"))
        page.addWidget(github_card)
        page.addStretch(1)
        return layout

    def _build_hotkey_page(self) -> QScrollArea:
        page, layout = self._page()
        global_card, global_layout = self._card("全局快捷键", "点击输入框后按下组合键即可设置，修改后立即生效。")
        self._add_hotkey_row(global_layout, "区域截图", self.region_hotkey_edit, self.region_reset_btn)
        self._add_hotkey_row(global_layout, "当前窗口截图", self.window_hotkey_edit, self.window_reset_btn)
        self._add_hotkey_row(global_layout, "截图历史", self.history_hotkey_edit, self.history_reset_btn)
        self._add_hotkey_row(global_layout, "贴图管理", self.pin_hotkey_edit, self.pin_reset_btn)
        self._add_hotkey_row(global_layout, "文字识别", self.ocr_hotkey_edit, self.ocr_reset_btn)
        global_layout.addWidget(self._helper("建议使用最多两个修饰键，例如 Ctrl+Shift。空值表示不注册该全局快捷键。"))
        page.addWidget(global_card)
        page.addStretch(1)
        return layout

    def _build_history_page(self) -> QScrollArea:
        page, layout = self._page()
        history_card, history_layout = self._card("历史库", "控制截图历史是否自动保存，以及最多保留数量。")
        history_layout.addWidget(self.history_check)
        limit_row = QHBoxLayout()
        limit_row.setContentsMargins(0, 0, 0, 0)
        limit_row.setSpacing(8)
        limit_row.addWidget(self._field_label("最多保留"))
        limit_row.addWidget(self.history_limit_spin)
        limit_row.addWidget(self._field_label("张"))
        limit_row.addStretch(1)
        history_layout.addLayout(limit_row)
        history_layout.addWidget(self._helper("当上限调小后，旧截图会立即按新限制清理。"))
        page.addWidget(history_card)
        page.addStretch(1)
        return layout

    def _build_help_page(self) -> QScrollArea:
        page, layout = self._page()
        help_card, help_layout = self._card("操作说明", "截图后常用按键和窗口操作。")
        help_layout.addWidget(self.hotkey_help_label)
        page.addWidget(help_card)
        page.addStretch(1)
        return layout

    def _page(self):
        content = QWidget()
        page = QVBoxLayout()
        page.setContentsMargins(22, 20, 22, 20)
        page.setSpacing(16)
        content.setLayout(page)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        return page, scroll

    def _card(self, title: str, subtitle: str = ""):
        card = make_card()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        layout.addWidget(title_label)
        if subtitle:
            sub = self._helper(subtitle)
            layout.addWidget(sub)
            # 在副标题后留一点呼吸空间，再开始字段区
            layout.addSpacing(2)
        card.setLayout(layout)
        return card, layout

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def _helper(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("helper")
        label.setWordWrap(True)
        return label

    def _add_field(self, layout: QVBoxLayout, label_text: str, widget_or_layout, hint: str = "") -> None:
        label = self._field_label(label_text)
        layout.addWidget(label)
        # 字段标签与控件之间的紧凑间距
        if isinstance(widget_or_layout, QHBoxLayout):
            layout.addLayout(widget_or_layout)
        else:
            layout.addWidget(widget_or_layout)
        if hint:
            hint_label = self._helper(hint)
            layout.addWidget(hint_label)
        # 字段之间留更明显的呼吸空间
        layout.addSpacing(4)

    def _add_hotkey_row(self, layout: QVBoxLayout, label_text: str, editor: HotkeyCaptureEdit, reset_btn: QPushButton) -> None:
        label = self._field_label(label_text)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(editor, 1)
        row.addWidget(reset_btn)
        layout.addWidget(label)
        layout.addLayout(row)

    def switch_settings_page(self, index: int) -> None:
        self.settings_stack.setCurrentIndex(index)
        for i, button in enumerate(self._nav_buttons):
            button.setChecked(i == index)

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()

    def apply_style(self) -> None:
        self.setStyleSheet(APP_STYLE + settings_extras_stylesheet())

    def choose_save_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择保存目录", self.config.save_dir)
        if folder:
            self.config.save_dir = folder
            self.config.save()
            self.save_dir_edit.setText(folder)

    def on_auto_copy_changed(self, state: int) -> None:
        self.config.auto_copy = state == Qt.CheckState.Checked.value
        self.config.save()

    def on_save_mode_changed(self, index: int) -> None:
        mode = self.save_mode_combo.itemData(index)
        if mode:
            self.config.save_dir_mode = mode
            self.config.save()

    def on_notification_changed(self, state: int) -> None:
        self.config.show_notifications = state == Qt.CheckState.Checked.value
        self.config.save()

    def on_hdr_color_accurate_changed(self, state: int) -> None:
        self.config.hdr_color_accurate = state == Qt.CheckState.Checked.value
        self.config.save()

    def on_watermark_changed(self, text: str) -> None:
        self.config.watermark_text = text.strip()
        self.config.save()

    def on_delay_changed(self, value: int) -> None:
        self.config.delay_seconds = value
        self.config.save()

    def on_watermark_color_changed(self, index: int) -> None:
        color = self.watermark_color_combo.itemData(index)
        if color:
            self.config.watermark_color = color
            self.config.save()

    def on_grid_color_changed(self, index: int) -> None:
        color = self.grid_color_combo.itemData(index)
        if color:
            self.config.grid_color = color
            self.config.save()

    def on_workflow_ocr_changed(self, state: int) -> None:
        self.config.workflow_auto_ocr = state == Qt.CheckState.Checked.value
        self.config.save()

    def on_workflow_upload_changed(self, state: int) -> None:
        self.config.workflow_auto_upload = state == Qt.CheckState.Checked.value
        self.config.save()

    def on_workflow_md_changed(self, state: int) -> None:
        self.config.workflow_copy_markdown = state == Qt.CheckState.Checked.value
        self.config.save()

    def on_uploader_changed(self, index: int) -> None:
        value = self.uploader_combo.itemData(index)
        if value:
            self.config.workflow_uploader = str(value)
            self.config.save()

    def on_github_owner_changed(self) -> None:
        self.config.github_owner = self.github_owner_edit.text().strip()
        self.config.save()

    def on_github_repo_changed(self) -> None:
        self.config.github_repo = self.github_repo_edit.text().strip()
        self.config.save()

    def on_github_branch_changed(self) -> None:
        branch = self.github_branch_edit.text().strip() or "main"
        self.config.github_branch = branch
        self.github_branch_edit.setText(branch)
        self.config.save()

    def on_github_prefix_changed(self) -> None:
        prefix = self.github_prefix_edit.text().strip().strip("/") or "screenshots"
        self.config.github_path_prefix = prefix
        self.github_prefix_edit.setText(prefix)
        self.config.save()

    def _github_account_key(self) -> str:
        owner = self.config.github_owner.strip()
        repo = self.config.github_repo.strip()
        return f"{owner}/{repo}" if owner and repo else "default"

    def _load_github_token_into_field(self) -> bool:
        """检测 keyring 中是否已有 token，仅用占位符提示，不回显明文。"""
        from .secrets import get_github_token
        existing = get_github_token(self._github_account_key())
        if existing:
            self.github_token_edit.setPlaceholderText("Token 已保存（输入新值可覆盖）")
            return True
        return False

    def on_github_token_save(self) -> None:
        from .secrets import set_github_token
        token = self.github_token_edit.text().strip()
        if not token:
            QMessageBox.warning(self, "Token 为空", "请先输入 Personal Access Token。")
            return
        ok = set_github_token(token, self._github_account_key())
        if ok:
            self.github_token_edit.clear()
            self.github_token_edit.setPlaceholderText("Token 已保存（输入新值可覆盖）")
            QMessageBox.information(self, "保存成功", "Token 已保存到 Windows 凭据管理器。")
        else:
            QMessageBox.warning(self, "保存失败", "无法写入系统凭据存储，请检查 keyring 后端。")

    def on_github_token_clear(self) -> None:
        from .secrets import delete_github_token
        delete_github_token(self._github_account_key())
        self.github_token_edit.clear()
        self.github_token_edit.setPlaceholderText("Personal Access Token（保存到系统凭据，不存配置文件）")
        QMessageBox.information(self, "已清除", "Token 已从系统凭据中删除。")

    def _build_help_text(self) -> str:
        r = self.config.region_hotkey or "Ctrl+Shift+A"
        w = self.config.window_hotkey or "Ctrl+Shift+W"
        return f"""
        <style>
        table {{ border-collapse: collapse; width: 100%; }}
        td {{ padding: 4px 8px; }}
        .section {{ font-weight: bold; color: #1e3a5f; padding-top: 10px; }}
        .key {{ background: #f0f3f7; border: 1px solid #d7deea; border-radius: 4px;
               padding: 2px 8px; font-family: Consolas, monospace; font-size: 12px; }}
        .desc {{ color: #475569; }}
        </style>
        <div class="section">全局快捷键</div>
        <table>
        <tr><td class="key">{r}</td><td class="desc">区域截图</td></tr>
        <tr><td class="key">{w}</td><td class="desc">当前窗口截图</td></tr>
        </table>
        <div class="section">编辑模式（截图后）</div>
        <table>
        <tr><td class="key">A</td><td class="desc">箭头</td>
            <td class="key">R</td><td class="desc">矩形</td>
            <td class="key">U</td><td class="desc">椭圆</td></tr>
        <tr><td class="key">D</td><td class="desc">虚线框</td>
            <td class="key">B</td><td class="desc">画笔</td>
            <td class="key">H</td><td class="desc">高亮</td></tr>
        <tr><td class="key">T</td><td class="desc">文字</td>
            <td class="key">N</td><td class="desc">序号</td>
            <td class="key">M</td><td class="desc">马赛克</td></tr>
        <tr><td class="key">L</td><td class="desc">模糊打码</td>
            <td class="key">O</td><td class="desc">OCR 识文</td>
            <td class="key">G</td><td class="desc">网格辅助</td></tr>
        <tr><td class="key">K</td><td class="desc">尺寸锁定</td>
            <td class="key">P</td><td class="desc">复用选区</td>
            <td class="key">Tab</td><td class="desc">切换上一工具</td></tr>
        <tr><td class="key">Ctrl+C</td><td class="desc">复制到剪贴板</td>
            <td class="key">Ctrl+S</td><td class="desc">保存文件</td>
            <td class="key">Ctrl+Z</td><td class="desc">撤销标注</td></tr>
        <tr><td class="key">Ctrl+Y</td><td class="desc">重做标注</td>
            <td class="key">Enter</td><td class="desc">完成截图</td>
            <td class="key">Esc</td><td class="desc">取消</td></tr>
        </table>
        <div class="section">鼠标操作</div>
        <table>
        <tr><td class="key">拖动</td><td class="desc">移动选区 / 绘制标注</td></tr>
        <tr><td class="key">滚轮</td><td class="desc">预览区缩放（截图历史）</td></tr>
        <tr><td class="key">双击</td><td class="desc">完成截图</td></tr>
        <tr><td class="key">右键</td><td class="desc">取消截图</td></tr>
        </table>
        <div class="section">窗口快捷键（历史 / 贴图管理）</div>
        <table>
        <tr><td class="key">Ctrl+A</td><td class="desc">全选</td>
            <td class="key">Delete</td><td class="desc">删除 / 关闭</td></tr>
        <tr><td class="key">Enter</td><td class="desc">打开 / 贴图</td>
            <td class="key">Esc</td><td class="desc">关闭窗口</td></tr>
        </table>
        <div class="section">自定义设置</div>
        <table>
        <tr><td class="desc" colspan="2">可在上方设置网格辅助线颜色和水印颜色</td></tr>
        </table>
        """

    def update_help_text(self) -> None:
        self.hotkey_help_label.setText(self._build_help_text())

    def on_region_hotkey_changed(self, combo: str) -> None:
        if combo == self.config.window_hotkey:
            QMessageBox.warning(self, "快捷键冲突", "该快捷键已用于窗口截图，请换一个。")
            self.region_hotkey_edit.set_hotkey(self.config.region_hotkey)
            return
        self.config.region_hotkey = combo
        self.config.save()
        self.hotkeys_changed.emit()
        self.update_help_text()

    def on_window_hotkey_changed(self, combo: str) -> None:
        if combo == self.config.region_hotkey:
            QMessageBox.warning(self, "快捷键冲突", "该快捷键已用于区域截图，请换一个。")
            self.window_hotkey_edit.set_hotkey(self.config.window_hotkey)
            return
        self.config.window_hotkey = combo
        self.config.save()
        self.hotkeys_changed.emit()
        self.update_help_text()

    def _check_hotkey_conflict(self, combo: str, exclude: str = "") -> bool:
        """检查快捷键是否与已有快捷键冲突，返回 True 表示有冲突。"""
        used = [self.config.region_hotkey, self.config.window_hotkey,
                self.config.history_hotkey, self.config.pin_hotkey]
        if exclude:
            used = [h for h in used if h != exclude]
        return combo in used

    def on_history_hotkey_changed(self, combo: str) -> None:
        if self._check_hotkey_conflict(combo, exclude=self.config.history_hotkey):
            QMessageBox.warning(self, "快捷键冲突", "该快捷键已被占用，请换一个。")
            self.history_hotkey_edit.set_hotkey(self.config.history_hotkey)
            return
        self.config.history_hotkey = combo
        self.config.save()
        self.hotkeys_changed.emit()

    def on_pin_hotkey_changed(self, combo: str) -> None:
        if self._check_hotkey_conflict(combo, exclude=self.config.pin_hotkey):
            QMessageBox.warning(self, "快捷键冲突", "该快捷键已被占用，请换一个。")
            self.pin_hotkey_edit.set_hotkey(self.config.pin_hotkey)
            return
        self.config.pin_hotkey = combo
        self.config.save()
        self.hotkeys_changed.emit()

    def on_ocr_hotkey_changed(self, combo: str) -> None:
        if self._check_hotkey_conflict(combo, exclude=self.config.ocr_hotkey):
            QMessageBox.warning(self, "快捷键冲突", "该快捷键已被占用，请换一个。")
            self.ocr_hotkey_edit.set_hotkey(self.config.ocr_hotkey)
            return
        self.config.ocr_hotkey = combo
        self.config.save()
        self.hotkeys_changed.emit()

    def reset_hotkey(self, which: str) -> None:
        defaults = {"region": "Ctrl+Shift+A", "window": "Ctrl+Shift+W", "history": "", "pin": "", "ocr": ""}
        default = defaults.get(which, "")
        if which == "region":
            self.region_hotkey_edit.set_hotkey(default)
            self.config.region_hotkey = default
        elif which == "window":
            self.window_hotkey_edit.set_hotkey(default)
            self.config.window_hotkey = default
        elif which == "history":
            self.history_hotkey_edit.set_hotkey(default)
            self.config.history_hotkey = default
        elif which == "pin":
            self.pin_hotkey_edit.set_hotkey(default)
            self.config.pin_hotkey = default
        elif which == "ocr":
            self.ocr_hotkey_edit.set_hotkey(default)
            self.config.ocr_hotkey = default
        self.config.save()
        self.hotkeys_changed.emit()
        self.update_help_text()

    def on_history_changed(self, state: int) -> None:
        self.config.auto_history = state == Qt.CheckState.Checked.value
        self.config.save()

    def on_history_limit_changed(self, value: int) -> None:
        self.config.history_limit = int(value)
        self.config.save()
        removed = self.history_store.apply_history_limit()
        if removed > 0:
            QMessageBox.information(self, "历史库已整理", f"已按新上限清理 {removed} 张旧截图。")

    def on_startup_changed(self, state: int) -> None:
        try:
            StartupManager.set_enabled(state == Qt.CheckState.Checked.value)
        except Exception as exc:
            QMessageBox.warning(self, "设置失败", f"开机启动设置失败：{exc}")
            self.startup_check.blockSignals(True)
            self.startup_check.setChecked(StartupManager.is_enabled())
            self.startup_check.blockSignals(False)

    # 导出时排除的字段（可选快捷键 + 延迟截图 + save_dir_mode）
    _EXPORT_EXCLUDE = frozenset({
        "history_hotkey", "pin_hotkey", "ocr_hotkey",
        "delay_seconds", "save_dir_mode",
        "annotation_presets",
    })

    def export_settings(self) -> None:
        import json
        default_path = str(Path(self.config.ensure_save_dir()) / "quickshot_settings.json")
        filepath, _ = QFileDialog.getSaveFileName(self, "导出设置", default_path, "JSON 文件 (*.json)")
        if not filepath:
            return
        if not filepath.lower().endswith(".json"):
            filepath += ".json"
        try:
            data = {k: v for k, v in self.config.to_dict().items()
                    if k not in self._EXPORT_EXCLUDE}
            Path(filepath).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            QMessageBox.information(self, "导出成功", f"设置已导出到：\n{filepath}")
        except Exception as exc:
            QMessageBox.warning(self, "导出失败", f"导出设置失败：{exc}")

    def import_settings(self) -> None:
        import json
        filepath, _ = QFileDialog.getOpenFileName(self, "导入设置", "", "JSON 文件 (*.json)")
        if not filepath:
            return
        try:
            raw = Path(filepath).read_text(encoding="utf-8")
            data = json.loads(raw)
        except Exception as exc:
            QMessageBox.warning(self, "导入失败", f"读取设置文件失败：{exc}")
            return

        # 快捷键需要验证后再导入，其余字段走通用导入
        from .hotkey_util import validate_hotkey
        hotkey_fields = {"region_hotkey", "window_hotkey"}
        hotkey_data = {}
        for key in hotkey_fields:
            if key in data:
                valid, _ = validate_hotkey(str(data[key]))
                if valid:
                    hotkey_data[key] = str(data[key])

        # 通用字段导入（排除快捷键，由上面单独处理）
        bulk_data = {k: v for k, v in data.items() if k not in hotkey_fields}
        bulk_data.update(hotkey_data)
        self.config.import_from_dict(bulk_data)
        self.save_dir_edit.setText(self.config.save_dir)
        self.auto_copy_check.setChecked(self.config.auto_copy)
        self.workflow_ocr_check.setChecked(self.config.workflow_auto_ocr)
        self.workflow_upload_check.setChecked(self.config.workflow_auto_upload)
        self.workflow_md_check.setChecked(self.config.workflow_copy_markdown)
        for i in range(self.uploader_combo.count()):
            if self.uploader_combo.itemData(i) == self.config.workflow_uploader:
                self.uploader_combo.setCurrentIndex(i)
                break
        self.github_owner_edit.setText(self.config.github_owner)
        self.github_repo_edit.setText(self.config.github_repo)
        self.github_branch_edit.setText(self.config.github_branch)
        self.github_prefix_edit.setText(self.config.github_path_prefix)
        self.notification_check.setChecked(self.config.show_notifications)
        self.hdr_accurate_check.setChecked(self.config.hdr_color_accurate)
        self.history_check.setChecked(self.config.auto_history)
        self.history_limit_spin.setValue(self.config.history_limit)
        self.watermark_edit.setText(self.config.watermark_text)
        # 刷新水印颜色下拉框
        for i in range(self.watermark_color_combo.count()):
            if self.watermark_color_combo.itemData(i) == self.config.watermark_color:
                self.watermark_color_combo.setCurrentIndex(i)
                break
        # 刷新网格颜色下拉框
        for i in range(self.grid_color_combo.count()):
            if self.grid_color_combo.itemData(i) == self.config.grid_color:
                self.grid_color_combo.setCurrentIndex(i)
                break
        self.region_hotkey_edit.set_hotkey(self.config.region_hotkey)
        self.window_hotkey_edit.set_hotkey(self.config.window_hotkey)
        self.hotkeys_changed.emit()
        self.update_help_text()
        QMessageBox.information(self, "导入成功", "设置已导入并生效。")
