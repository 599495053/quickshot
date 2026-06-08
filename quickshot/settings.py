from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ._settings_handlers import SettingsHandlers


def _disable_wheel(widget: QWidget) -> None:
    """忽略 QSpinBox/QComboBox 的滚轮事件，避免滚动设置页时误改值。"""
    widget.wheelEvent = lambda event: event.ignore()

from .config import Config, StartupManager
from .history import CaptureHistoryStore
from .theme import settings_extras_stylesheet
from .ui import APP_STYLE, make_card, set_button_role
from .utils import APP_NAME, APP_VERSION, load_app_icon
from .workflow_presets import WORKFLOW_PRESET_LABELS, normalize_workflow_preset


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


class SettingsWindow(SettingsHandlers, QWidget):
    hotkeys_changed = pyqtSignal()
    workflow_changed = pyqtSignal()
    Qt_CHECKED = Qt.CheckState.Checked.value

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config
        self.history_store = CaptureHistoryStore(config)
        self._nav_buttons = []
        # config.save() debounce：避免高频输入（如 watermark textChanged）每字符写磁盘
        self._save_debounce = QTimer(self)
        self._save_debounce.setSingleShot(True)
        self._save_debounce.setInterval(300)
        self._save_debounce.timeout.connect(self.config.save)
        self.setWindowTitle(f"{APP_NAME} V{APP_VERSION} 设置")
        self.resize(1040, 720)
        self.setMinimumSize(920, 640)
        self.setWindowIcon(load_app_icon())
        self._create_controls()
        self._build_settings_layout()
        self.apply_style()

    def _schedule_save(self) -> None:
        """延迟 300ms 保存配置，合并短时间内的多次变更。"""
        self._save_debounce.start()

    def _create_save_controls(self) -> None:
        """创建保存路径和格式相关的控件。"""
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

        self.save_format_combo = QComboBox()
        _disable_wheel(self.save_format_combo)
        self.save_format_combo.addItem("PNG", "png")
        self.save_format_combo.addItem("JPEG", "jpg")
        self.save_format_combo.addItem("WebP", "webp")
        self.save_format_combo.addItem("BMP", "bmp")
        current_fmt = getattr(self.config, "save_format", "png")
        for i in range(self.save_format_combo.count()):
            if self.save_format_combo.itemData(i) == current_fmt:
                self.save_format_combo.setCurrentIndex(i)
                break
        self.save_format_combo.currentIndexChanged.connect(self.on_save_format_changed)

        self.jpeg_quality_spin = QSpinBox()
        self.jpeg_quality_spin.setRange(1, 100)
        self.jpeg_quality_spin.setValue(getattr(self.config, "jpeg_quality", 90))
        self.jpeg_quality_spin.setSuffix("%")
        self.jpeg_quality_spin.valueChanged.connect(self.on_jpeg_quality_changed)
        self.jpeg_quality_spin.setEnabled(current_fmt in ("jpg", "jpeg"))

        self.auto_copy_check = QCheckBox("截图完成后自动复制到剪贴板")
        self.auto_copy_check.setChecked(self.config.auto_copy)
        self.auto_copy_check.stateChanged.connect(self.on_auto_copy_changed)

    def _create_workflow_controls(self) -> None:
        """创建工作流自动化相关控件。"""
        self.workflow_preset_combo = QComboBox()
        _disable_wheel(self.workflow_preset_combo)
        for preset, label in WORKFLOW_PRESET_LABELS:
            self.workflow_preset_combo.addItem(label, preset)
        current_preset = normalize_workflow_preset(getattr(self.config, "workflow_preset", "custom"))
        for i in range(self.workflow_preset_combo.count()):
            if self.workflow_preset_combo.itemData(i) == current_preset:
                self.workflow_preset_combo.setCurrentIndex(i)
                break
        self.workflow_preset_combo.currentIndexChanged.connect(self.on_workflow_preset_changed)

        self.workflow_reset_btn = set_button_role(QPushButton("恢复默认"), compact=True)
        self.workflow_reset_btn.setToolTip("恢复默认工作流：截图后复制图片，关闭自动保存、OCR、上传和隐私预览。")
        self.workflow_reset_btn.clicked.connect(self.restore_workflow_defaults)

        self.workflow_summary_label = QLabel()
        self.workflow_summary_label.setObjectName("helper")
        self.workflow_summary_label.setWordWrap(True)

        self.workflow_auto_save_check = QCheckBox("截图完成后自动保存到默认目录")
        self.workflow_auto_save_check.setChecked(getattr(self.config, "workflow_auto_save", False))
        self.workflow_auto_save_check.stateChanged.connect(self.on_workflow_auto_save_changed)

        self.workflow_ocr_check = QCheckBox("截图完成后自动 OCR 并把文本写入剪贴板（会覆盖图片）")
        self.workflow_ocr_check.setChecked(getattr(self.config, "workflow_auto_ocr", False))
        self.workflow_ocr_check.stateChanged.connect(self.on_workflow_ocr_changed)

        self.workflow_upload_check = QCheckBox("截图完成后自动上传")
        self.workflow_upload_check.setChecked(getattr(self.config, "workflow_auto_upload", False))
        self.workflow_upload_check.stateChanged.connect(self.on_workflow_upload_changed)

        self.workflow_md_check = QCheckBox("上传成功后自动复制 Markdown 链接")
        self.workflow_md_check.setChecked(getattr(self.config, "workflow_copy_markdown", False))
        self.workflow_md_check.stateChanged.connect(self.on_workflow_md_changed)

        self.workflow_privacy_check = QCheckBox("截图后优先进入智能隐私打码预览")
        self.workflow_privacy_check.setChecked(getattr(self.config, "workflow_privacy_first", False))
        self.workflow_privacy_check.stateChanged.connect(self.on_workflow_privacy_changed)

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
        self._refresh_workflow_summary()

    def _create_github_controls(self) -> None:
        """创建GitHub上传配置相关控件。"""
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

        self.github_status_label = QLabel()
        self.github_status_label.setObjectName("status")
        self.github_status_label.setWordWrap(True)
        self._refresh_github_status()

    def _create_appearance_controls(self) -> None:
        """创建外观相关控件（水印、网格、HDR）。"""
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

        self.hdr_accurate_check = QCheckBox("HDR 截图优先色彩准确（需可选 HDR 组件，会出现 Windows 录制边框）")
        self.hdr_accurate_check.setChecked(self.config.hdr_color_accurate)
        self.hdr_accurate_check.stateChanged.connect(self.on_hdr_color_accurate_changed)

        self.screenshot_dim_style_combo = QComboBox()
        _disable_wheel(self.screenshot_dim_style_combo)
        self.screenshot_dim_style_combo.addItem("系统风格（推荐）", "system")
        self.screenshot_dim_style_combo.addItem("更清晰", "clear")
        self.screenshot_dim_style_combo.addItem("更深色", "deep")
        self.screenshot_dim_style_combo.addItem("自定义", "custom")
        for i in range(self.screenshot_dim_style_combo.count()):
            if self.screenshot_dim_style_combo.itemData(i) == getattr(self.config, "screenshot_dim_style", "system"):
                self.screenshot_dim_style_combo.setCurrentIndex(i)
                break
        self.screenshot_dim_style_combo.currentIndexChanged.connect(self.on_screenshot_dim_style_changed)

        self.screenshot_dim_alpha_spin = QSpinBox()
        _disable_wheel(self.screenshot_dim_alpha_spin)
        self.screenshot_dim_alpha_spin.setRange(72, 220)
        self.screenshot_dim_alpha_spin.setSingleStep(4)
        self.screenshot_dim_alpha_spin.setValue(getattr(self.config, "screenshot_dim_alpha", 132))
        self.screenshot_dim_alpha_spin.setSuffix(" / 255")
        self.screenshot_dim_alpha_spin.valueChanged.connect(self.on_screenshot_dim_alpha_changed)

        self.screenshot_dim_blur_spin = QSpinBox()
        _disable_wheel(self.screenshot_dim_blur_spin)
        self.screenshot_dim_blur_spin.setRange(4, 32)
        self.screenshot_dim_blur_spin.setSingleStep(2)
        self.screenshot_dim_blur_spin.setValue(getattr(self.config, "screenshot_dim_blur", 16))
        self.screenshot_dim_blur_spin.setSuffix(" x")
        self.screenshot_dim_blur_spin.valueChanged.connect(self.on_screenshot_dim_blur_changed)
        self._refresh_screenshot_dim_controls()

    def _create_behavior_controls(self) -> None:
        """创建行为相关控件（启动、通知、吸附、延迟）。"""
        self.startup_check = QCheckBox("开机自动启动")
        self.startup_check.setChecked(StartupManager.is_enabled())
        self.startup_check.stateChanged.connect(self.on_startup_changed)

        self.notification_check = QCheckBox("复制、保存、完成后显示右下角提示")
        self.notification_check.setChecked(self.config.show_notifications)
        self.notification_check.stateChanged.connect(self.on_notification_changed)

        self.snap_check = QCheckBox("选区自动吸附到窗口边缘")
        self.snap_check.setChecked(self.config.snap_to_windows)
        self.snap_check.stateChanged.connect(self.on_snap_changed)

        self.snap_threshold_spin = QSpinBox()
        _disable_wheel(self.snap_threshold_spin)
        self.snap_threshold_spin.setRange(3, 30)
        self.snap_threshold_spin.setValue(self.config.snap_threshold_px)
        self.snap_threshold_spin.setSuffix(" px")
        self.snap_threshold_spin.valueChanged.connect(self.on_snap_threshold_changed)

        self.delay_spin = QSpinBox()
        _disable_wheel(self.delay_spin)
        self.delay_spin.setRange(0, 10)
        self.delay_spin.setValue(self.config.delay_seconds)
        self.delay_spin.setSuffix(" 秒")
        self.delay_spin.setSpecialValueText("不延迟")
        self.delay_spin.valueChanged.connect(self.on_delay_changed)

    def _create_hotkey_controls(self) -> None:
        """创建热键配置相关控件。"""
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

        self.hotkey_help_label = QLabel(self._build_help_text())
        self.hotkey_help_label.setObjectName("helper")
        self.hotkey_help_label.setWordWrap(True)

    def _create_history_controls(self) -> None:
        """创建历史库相关控件。"""
        self.history_check = QCheckBox("自动保存截图到历史库")
        self.history_check.setChecked(self.config.auto_history)
        self.history_check.stateChanged.connect(self.on_history_changed)

        self.history_limit_spin = QSpinBox()
        _disable_wheel(self.history_limit_spin)
        self.history_limit_spin.setRange(20, 1000)
        self.history_limit_spin.setSingleStep(20)
        self.history_limit_spin.setValue(self.config.history_limit)
        self.history_limit_spin.valueChanged.connect(self.on_history_limit_changed)

    def _create_action_buttons(self) -> None:
        """创建底部操作按钮（导出、导入、关闭）。"""
        self.export_btn = set_button_role(QPushButton("导出设置"))
        self.export_btn.clicked.connect(self.export_settings)
        self.import_btn = set_button_role(QPushButton("导入设置"))
        self.import_btn.clicked.connect(self.import_settings)
        self.copy_diagnostic_btn = set_button_role(QPushButton("复制诊断信息"))
        self.copy_diagnostic_btn.clicked.connect(self.copy_diagnostic_info)
        self.close_btn = set_button_role(QPushButton("关闭"), "primary")
        self.close_btn.clicked.connect(self.close)

    def _create_controls(self) -> None:
        """创建所有设置控件（委托给分组方法）。"""
        self._create_save_controls()
        self._create_workflow_controls()
        self._create_github_controls()
        self._create_appearance_controls()
        self._create_behavior_controls()
        self._create_hotkey_controls()
        self._create_history_controls()
        self._create_action_buttons()

    def _build_settings_layout(self) -> None:
        header_card = make_card("heroCard")
        icon_label = QLabel()
        icon_label.setObjectName("headerIcon")
        icon_label.setPixmap(load_app_icon().pixmap(36, 36))
        icon_label.setFixedSize(52, 52)
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
        header_row.setContentsMargins(22, 14, 22, 14)
        header_row.setSpacing(14)
        header_row.addWidget(icon_label)
        header_row.addLayout(title_box, 1)
        header_card.setLayout(header_row)

        nav = QFrame()
        nav.setObjectName("settingsSidebar")
        nav_layout = QVBoxLayout()
        nav_layout.setContentsMargins(10, 12, 10, 12)
        nav_layout.setSpacing(3)
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
            button.setMinimumSize(186, 38)
            button.setToolTip(desc)
            button.clicked.connect(lambda _checked=False, i=index: self.switch_settings_page(i))
            self._nav_buttons.append(button)
            nav_layout.addWidget(button)
            self.settings_stack.addWidget(page)
        nav_layout.addStretch(1)

        body = QHBoxLayout()
        body.setContentsMargins(18, 14, 18, 14)
        body.setSpacing(16)
        body.addWidget(nav, 0)
        body.addWidget(self.settings_stack, 1)

        footer = QFrame()
        footer.setObjectName("footer")
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(22, 11, 22, 13)
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

        fmt_row = QHBoxLayout()
        fmt_row.setContentsMargins(0, 0, 0, 0)
        fmt_row.setSpacing(8)
        fmt_row.addWidget(self.save_format_combo, 1)
        fmt_row.addWidget(QLabel("JPEG 质量"))
        fmt_row.addWidget(self.jpeg_quality_spin)
        self._add_field(save_layout, "保存格式", fmt_row, "选择默认保存格式，JPEG 可调质量。")

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
        backup_row.addWidget(self.copy_diagnostic_btn)
        backup_row.addStretch(1)
        backup_layout.addLayout(backup_row)
        backup_layout.addWidget(self._helper("诊断信息会尽量脱敏，可用于反馈截图失败、OCR 失败、智能隐私打码异常等问题。粘贴前建议快速检查。"))
        page.addWidget(backup_card)
        page.addStretch(1)
        return layout

    def _build_visual_page(self) -> QScrollArea:
        page, layout = self._page()
        capture_card, capture_layout = self._card("截图行为", "影响截图捕获质量和系统提示。")
        capture_layout.addWidget(self.hdr_accurate_check)
        capture_layout.addWidget(self._helper("默认关闭：HDR 截图无边框，适合日常截图。开启后色彩更准确，但 Windows 会显示金色录制边框。"))
        page.addWidget(capture_card)

        dim_card, dim_layout = self._card("选区外观", "截图时选区外的背景风格，默认接近 Windows / 微信截图。")
        self._add_field(dim_layout, "遮罩风格", self.screenshot_dim_style_combo)
        dim_row = QHBoxLayout()
        dim_row.setContentsMargins(0, 0, 0, 0)
        dim_row.setSpacing(8)
        dim_row.addWidget(self._field_label("暗度"))
        dim_row.addWidget(self.screenshot_dim_alpha_spin)
        dim_row.addWidget(self._field_label("柔化"))
        dim_row.addWidget(self.screenshot_dim_blur_spin)
        dim_row.addStretch(1)
        self._add_field(dim_layout, "自定义参数", dim_row, "数值越大，选区外越暗、越柔和；更能压住细线，但背景会更朦胧。")
        page.addWidget(dim_card)

        snap_card, snap_layout = self._card("选区吸附", "拖拽选区时自动吸附到窗口边缘。")
        snap_layout.addWidget(self.snap_check)
        self._add_field(snap_layout, "吸附阈值", self.snap_threshold_spin, "距离窗口边缘多少像素时触发吸附。")
        page.addWidget(snap_card)

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
        preset_row = QHBoxLayout()
        preset_row.setContentsMargins(0, 0, 0, 0)
        preset_row.setSpacing(8)
        preset_row.addWidget(self.workflow_preset_combo, 1)
        preset_row.addWidget(self.workflow_reset_btn)
        self._add_field(workflow_layout, "工作流预设", preset_row)
        workflow_layout.addWidget(self.workflow_summary_label)
        workflow_layout.addWidget(self.workflow_auto_save_check)
        workflow_layout.addWidget(self.workflow_ocr_check)
        workflow_layout.addWidget(self.workflow_upload_check)
        workflow_layout.addWidget(self.workflow_md_check)
        workflow_layout.addWidget(self.workflow_privacy_check)
        self._add_field(workflow_layout, "上传到", self.uploader_combo)
        workflow_layout.addWidget(self._helper(
            "快速复制只写入剪贴板；自动保存写入默认目录；识文模式复制文本；发布模式保存、上传并复制 Markdown；隐私模式先进入智能打码预览。"
        ))
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
        github_layout.addWidget(self.github_status_label)
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

        # 编辑模式工具快捷键
        edit_card, edit_layout = self._card("编辑模式工具快捷键", "截图后按单键切换工具，可在 config.json 中自定义。")
        summary_label = QLabel(self._edit_tool_hotkey_summary_text())
        summary_label.setObjectName("helper")
        summary_label.setWordWrap(True)
        self.edit_tool_hotkey_summary_label = summary_label
        edit_layout.addWidget(summary_label)
        restore_btn = set_button_role(QPushButton("恢复默认"), "compact")
        restore_btn.setToolTip("清空自定义，恢复默认键位")
        restore_btn.clicked.connect(self._restore_edit_tool_hotkeys)
        edit_layout.addWidget(restore_btn)
        page.addWidget(edit_card)

        page.addStretch(1)
        return layout

    def _edit_tool_hotkey_summary_text(self) -> str:
        from .overlay._events import TOOL_DEFAULT_KEYS
        tool_names = {
            "arrow": "箭头", "rect": "矩形", "ellipse": "椭圆", "dashed_rect": "虚线框",
            "pen": "画笔", "highlight": "高亮", "text": "文字", "number": "序号",
            "mosaic": "马赛克", "blur": "模糊", "picker": "取色器",
        }
        custom = getattr(self.config, "edit_tool_hotkeys", None) or {}
        current_keys = {}
        for tool_id, default_key in TOOL_DEFAULT_KEYS.items():
            current_keys[tool_id] = custom.get(tool_id, chr(default_key) if 0x41 <= default_key <= 0x5A else "")
        summary_parts = []
        for tool_id in ["arrow", "rect", "ellipse", "dashed_rect", "pen", "highlight", "text", "number", "mosaic", "blur", "picker"]:
            display = tool_names.get(tool_id, tool_id)
            key = current_keys.get(tool_id, "")
            summary_parts.append(f"{display}={key}" if key else f"{display}=?")
        return "  |  ".join(summary_parts)

    def _refresh_edit_tool_hotkey_summary(self) -> None:
        label = getattr(self, "edit_tool_hotkey_summary_label", None)
        if label is not None:
            label.setText(self._edit_tool_hotkey_summary_text())

    def _restore_edit_tool_hotkeys(self) -> None:
        """清空自定义编辑模式工具快捷键，恢复默认。"""
        self.config.edit_tool_hotkeys = {}
        self._schedule_save()
        self.hotkeys_changed.emit()
        self._refresh_edit_tool_hotkey_summary()

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
        page.setContentsMargins(20, 18, 20, 20)
        page.setSpacing(14)
        content.setLayout(page)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        return page, scroll

    def _card(self, title: str, subtitle: str = ""):
        card = make_card()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 17, 20, 18)
        layout.setSpacing(10)
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        layout.addWidget(title_label)
        if subtitle:
            sub = self._helper(subtitle)
            layout.addWidget(sub)
            # 在副标题后留一点呼吸空间，再开始字段区
            layout.addSpacing(4)
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
        layout.addSpacing(6)

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
