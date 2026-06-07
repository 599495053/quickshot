"""QuickShot 全局视觉 token。

集中所有颜色、圆角、间距、阴影、字体常量，避免散落在各 widget 里。
其它模块通过 ``from .theme import ...`` 引用即可；不要在外部继续硬编码
十六进制色或圆角数字。
"""

from __future__ import annotations

from PyQt6.QtGui import QColor

# ── 颜色 token ──
# 命名采用 ``<group>_<role>`` 风格，所有键在 _COLOR_TOKENS 字典中统一登记，
# 既可以通过常量直接引用（推荐），也可以用 ``qc("text.primary")`` 按 key 取。

TEXT_PRIMARY = "#111827"
TEXT_BODY = "#1f2937"
TEXT_SECONDARY = "#4b5563"
TEXT_MUTED = "#6b7280"

SURFACE_APP = "#f5f6f8"
SURFACE_CARD = "#ffffff"
SURFACE_INPUT = "#fbfbfc"
SURFACE_SUBTLE = "#f3f4f6"
SURFACE_HERO = "#f8fafc"
SURFACE_BTN = "#f3f4f6"
SURFACE_BTN_HOVER = "#e9ebef"
SURFACE_HEADER_ICON = "#eef2ff"

BORDER_LIGHT = "#e5e7eb"
BORDER_REGULAR = "#d8dce3"
BORDER_STRONG = "#bfc6d1"
BORDER_BTN = "#d5d9e2"

ACCENT_BASE = "#4f46e5"
ACCENT_HOVER = "#4338ca"
ACCENT_SOFT = "#eef2ff"
ACCENT_SOFTER = "#f7f7ff"
ACCENT_OUTLINE = "#c7d2fe"
ACCENT_SELECTION = "#e0e7ff"

DANGER_BASE = "#dc2626"
DANGER_SOFT = "#fef2f2"
DANGER_SOFT_HOVER = "#fee2e2"
DANGER_OUTLINE = "#fecaca"

SUCCESS_BASE = "#10b981"
SUCCESS_SOFT = "#ecfdf5"
SUCCESS_SOFT_HOVER = "#d1fae5"
SUCCESS_OUTLINE = "#a7f3d0"

# 用户内容色（笔触/文字标注），主题不应改变，但仍登记一份默认值
STROKE_DEFAULT = "#ff4646"


_COLOR_TOKENS = {
    "text.primary": TEXT_PRIMARY,
    "text.body": TEXT_BODY,
    "text.secondary": TEXT_SECONDARY,
    "text.muted": TEXT_MUTED,
    "surface.app": SURFACE_APP,
    "surface.card": SURFACE_CARD,
    "surface.input": SURFACE_INPUT,
    "surface.subtle": SURFACE_SUBTLE,
    "surface.hero": SURFACE_HERO,
    "surface.btn": SURFACE_BTN,
    "surface.btn.hover": SURFACE_BTN_HOVER,
    "surface.header.icon": SURFACE_HEADER_ICON,
    "border.light": BORDER_LIGHT,
    "border.regular": BORDER_REGULAR,
    "border.strong": BORDER_STRONG,
    "border.btn": BORDER_BTN,
    "accent.base": ACCENT_BASE,
    "accent.hover": ACCENT_HOVER,
    "accent.soft": ACCENT_SOFT,
    "accent.softer": ACCENT_SOFTER,
    "accent.outline": ACCENT_OUTLINE,
    "accent.selection": ACCENT_SELECTION,
    "danger.base": DANGER_BASE,
    "danger.soft": DANGER_SOFT,
    "danger.soft.hover": DANGER_SOFT_HOVER,
    "danger.outline": DANGER_OUTLINE,
    "success.base": SUCCESS_BASE,
    "success.soft": SUCCESS_SOFT,
    "success.soft.hover": SUCCESS_SOFT_HOVER,
    "success.outline": SUCCESS_OUTLINE,
}


# ── QColor 缓存 ──
# paintEvent 中每帧数百次调用 qc() / floating_*() 等，缓存避免重复构造。
_QC_CACHE: dict[tuple[str, int], QColor] = {}


def qc(token: str, alpha: int = 255) -> QColor:
    """按 token 名取 QColor。``alpha`` 范围 0-255。带缓存。"""
    key = (token, alpha)
    cached = _QC_CACHE.get(key)
    if cached is not None:
        return cached
    hex_color = _COLOR_TOKENS.get(token)
    if hex_color is None:
        raise KeyError(f"unknown color token: {token!r}")
    color = QColor(hex_color)
    if alpha < 255:
        color.setAlpha(alpha)
    _QC_CACHE[key] = color
    return color


def qcolor_from_rgba_hex(value: str, default: str = "#ffffff80") -> QColor:
    """Parse ``#RRGGBBAA`` values stored in config into QColor.

    QColor treats 8-digit hex strings as ``#AARRGGBB`` in this code path, while
    QuickShot settings store colors as the CSS-like ``#RRGGBBAA`` format.
    """
    text = str(value or default).strip()
    if len(text) == 9 and text.startswith("#"):
        try:
            red = int(text[1:3], 16)
            green = int(text[3:5], 16)
            blue = int(text[5:7], 16)
            alpha = int(text[7:9], 16)
            return QColor(red, green, blue, alpha)
        except ValueError:
            pass
    color = QColor(text)
    if color.isValid():
        return color
    fallback = QColor(default)
    if len(default) == 9 and default.startswith("#"):
        return qcolor_from_rgba_hex(default, "#ffffff")
    return fallback if fallback.isValid() else QColor("#ffffff")


# ── 半透明 / 绘制专用 QColor 工厂 ──
# 这些颜色带 alpha 通道，无法用十六进制表达，直接以函数形式提供，
# 让调用方含义清晰。使用模块级缓存单例。

_OVERLAY_DIM = QColor(0, 0, 0, 112)
_OVERLAY_SOLID = QColor(0, 0, 0, 255)
_FLOATING_BG = QColor(17, 24, 39, 238)
_FLOATING_BORDER = QColor(255, 255, 255, 36)
_FLOATING_TEXT = QColor(249, 250, 251)
_PANEL_BG = QColor(255, 255, 255, 248)
_PANEL_BORDER = QColor(229, 231, 235, 248)
_HANDLE_FILL = QColor(255, 255, 255, 240)

# overlay 浅色卡片化工具栏 / 样式面板 token
_OVERLAY_TOOLBAR_BG = QColor(255, 255, 255, 248)
_OVERLAY_TOOLBAR_BORDER = QColor(226, 232, 240, 242)
_OVERLAY_TOOLBAR_TEXT = QColor(51, 65, 85)
_OVERLAY_TOOLBAR_ICON = QColor(71, 85, 105)
_OVERLAY_TOOLBAR_HOVER_BG = QColor(241, 245, 249, 235)
_OVERLAY_TOOLBAR_ACTIVE_BG = QColor(238, 242, 255, 245)
_OVERLAY_TOOLBAR_ACTIVE_BORDER = QColor(199, 210, 254, 235)
_OVERLAY_TOOLBAR_PRIMARY_BG = QColor(79, 70, 229, 236)
_OVERLAY_TOOLBAR_PRIMARY_BG_HOVER = QColor(67, 56, 202, 244)
_OVERLAY_TOOLBAR_PRIMARY_BORDER = QColor(99, 102, 241, 228)
_OVERLAY_TOOLBAR_DANGER_BG = QColor(255, 247, 247, 246)
_OVERLAY_TOOLBAR_DANGER_BG_HOVER = QColor(254, 235, 235, 248)
_OVERLAY_TOOLBAR_DANGER_BORDER = QColor(252, 165, 165, 224)
_OVERLAY_PANEL_BG = QColor(255, 255, 255, 250)
_OVERLAY_PANEL_BORDER = QColor(226, 232, 240, 246)
_OVERLAY_TIP_BG = QColor(255, 255, 255, 250)
_OVERLAY_TIP_BORDER = QColor(226, 232, 240, 246)
_OVERLAY_TIP_TEXT = QColor(51, 65, 85)


def overlay_dim() -> QColor:
    """框选阶段的灰色遮罩。"""
    return _OVERLAY_DIM


def overlay_solid() -> QColor:
    """调整选区时的纯黑外圈。"""
    return _OVERLAY_SOLID


def floating_bg() -> QColor:
    """工具栏 / 消息条等悬浮 panel 的深色背景。"""
    return _FLOATING_BG


def floating_border() -> QColor:
    """floating panel 的高光描边。"""
    return _FLOATING_BORDER


def floating_text() -> QColor:
    return _FLOATING_TEXT


def panel_bg() -> QColor:
    """白底悬浮 panel（颜色/线宽样式面板）的背景。"""
    return _PANEL_BG


def panel_border() -> QColor:
    return _PANEL_BORDER


def handle_fill() -> QColor:
    """选区把手填色。"""
    return _HANDLE_FILL


def overlay_toolbar_bg() -> QColor:
    return _OVERLAY_TOOLBAR_BG


def overlay_toolbar_border() -> QColor:
    return _OVERLAY_TOOLBAR_BORDER


def overlay_toolbar_text() -> QColor:
    return _OVERLAY_TOOLBAR_TEXT


def overlay_toolbar_icon() -> QColor:
    return _OVERLAY_TOOLBAR_ICON


def overlay_toolbar_hover_bg() -> QColor:
    return _OVERLAY_TOOLBAR_HOVER_BG


def overlay_toolbar_active_bg() -> QColor:
    return _OVERLAY_TOOLBAR_ACTIVE_BG


def overlay_toolbar_active_border() -> QColor:
    return _OVERLAY_TOOLBAR_ACTIVE_BORDER


def overlay_toolbar_primary_bg() -> QColor:
    return _OVERLAY_TOOLBAR_PRIMARY_BG


def overlay_toolbar_primary_bg_hover() -> QColor:
    return _OVERLAY_TOOLBAR_PRIMARY_BG_HOVER


def overlay_toolbar_primary_border() -> QColor:
    return _OVERLAY_TOOLBAR_PRIMARY_BORDER


def overlay_toolbar_danger_bg() -> QColor:
    return _OVERLAY_TOOLBAR_DANGER_BG


def overlay_toolbar_danger_bg_hover() -> QColor:
    return _OVERLAY_TOOLBAR_DANGER_BG_HOVER


def overlay_toolbar_danger_border() -> QColor:
    return _OVERLAY_TOOLBAR_DANGER_BORDER


def overlay_panel_bg() -> QColor:
    return _OVERLAY_PANEL_BG


def overlay_panel_border() -> QColor:
    return _OVERLAY_PANEL_BORDER


def overlay_tip_bg() -> QColor:
    return _OVERLAY_TIP_BG


def overlay_tip_border() -> QColor:
    return _OVERLAY_TIP_BORDER


def overlay_tip_text() -> QColor:
    return _OVERLAY_TIP_TEXT


# ── 几何 token ──

RADIUS_SM = 6
RADIUS_MD = 8
RADIUS_LG = 10

SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16

# 阴影：(offset_px, alpha_0_255) 元组数组，调用方按 offset 由外向内画。
SHADOW_CARD = ((5, 12), (2, 18))
SHADOW_FLOATING = ((8, 22), (3, 36))


# ── 字体 token ──

FONT_FAMILY = "Microsoft YaHei, Segoe UI, sans-serif"

FONT_SIZE_CAPTION = 12
FONT_SIZE_BODY = 13
FONT_SIZE_SECTION = 15
FONT_SIZE_HERO = 21


# ── stylesheet 模板 ──

def app_stylesheet() -> str:
    """全局 QSS：所有窗口共享的基础样式。"""
    return f"""
    QWidget {{
        background: {SURFACE_APP};
        color: {TEXT_BODY};
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE_BODY}px;
    }}
    QFrame#card, QFrame#heroCard {{
        background: {SURFACE_CARD};
        border: 1px solid {BORDER_LIGHT};
        border-radius: {RADIUS_LG}px;
    }}
    QFrame#heroCard {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ffffff, stop:0.62 #f8fafc, stop:1 #f5f3ff);
        border-color: #dde3ee;
    }}
    QLabel#heroTitle {{
        font-size: {FONT_SIZE_HERO}px;
        font-weight: 700;
        color: {TEXT_PRIMARY};
    }}
    QLabel#heroSubtitle {{
        color: {TEXT_MUTED};
        font-size: {FONT_SIZE_BODY}px;
    }}
    QLabel#sectionTitle {{
        font-size: {FONT_SIZE_SECTION}px;
        font-weight: 700;
        color: {TEXT_PRIMARY};
    }}
    QLabel#status {{
        color: {TEXT_SECONDARY};
        background: {SURFACE_SUBTLE};
        border: 1px solid {BORDER_LIGHT};
        border-radius: {RADIUS_SM}px;
        padding: 5px 8px;
    }}
    QLineEdit, QPlainTextEdit, QComboBox {{
        border: 1px solid {BORDER_REGULAR};
        border-radius: {RADIUS_MD}px;
        padding: 8px 11px;
        background: {SURFACE_INPUT};
        selection-background-color: {ACCENT_SELECTION};
        min-height: 20px;
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
        border-color: {ACCENT_BASE};
        background: {SURFACE_CARD};
    }}
    QLineEdit:hover, QComboBox:hover {{
        border-color: {BORDER_STRONG};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 26px;
    }}
    QComboBox::down-arrow {{
        image: none;
        border: none;
        width: 0;
        height: 0;
    }}
    QListWidget {{
        border: 1px solid {BORDER_LIGHT};
        border-radius: {RADIUS_MD}px;
        background: #fbfcfe;
        padding: 4px;
        outline: none;
    }}
    QListWidget::item {{
        border: 1px solid transparent;
        border-radius: {RADIUS_MD}px;
        padding: 8px;
        margin: 2px 0;
    }}
    QListWidget::item:hover {{
        background: {SURFACE_SUBTLE};
        border-color: {BORDER_LIGHT};
    }}
    QListWidget::item:selected {{
        background: {ACCENT_SOFT};
        border-color: {ACCENT_OUTLINE};
        color: {TEXT_PRIMARY};
    }}
    QPushButton {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 {SURFACE_BTN});
        color: {TEXT_BODY};
        border: 1px solid {BORDER_BTN};
        border-radius: {RADIUS_MD}px;
        padding: 8px 14px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background: {SURFACE_BTN_HOVER};
        border-color: {BORDER_STRONG};
    }}
    QPushButton:pressed {{
        background: {BORDER_LIGHT};
    }}
    QPushButton[role="primary"] {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #6366f1, stop:1 {ACCENT_BASE});
        color: #ffffff;
        border-color: {ACCENT_BASE};
    }}
    QPushButton[role="primary"]:hover {{
        background: {ACCENT_HOVER};
        border-color: {ACCENT_HOVER};
    }}
    QPushButton[role="primary"]:pressed {{
        background: #3730a3;
        border-color: #3730a3;
    }}
    QPushButton[role="destructive"] {{
        background: {DANGER_SOFT};
        color: {DANGER_BASE};
        border-color: {DANGER_OUTLINE};
    }}
    QPushButton[role="destructive"]:hover {{
        background: {DANGER_SOFT_HOVER};
    }}
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QSplitter::handle {{
        background: transparent;
    }}
    QSplitter::handle:horizontal {{
        width: 8px;
    }}
    QSplitter::handle:vertical {{
        height: 8px;
    }}
    QSplitter::handle:hover {{
        background: {ACCENT_SOFT};
        border-radius: 4px;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: #c8ced8;
        border-radius: 4px;
        min-height: 30px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {TEXT_MUTED};
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 8px;
        margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background: #c8ced8;
        border-radius: 4px;
        min-width: 30px;
        margin: 2px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {TEXT_MUTED};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: none;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: none;
    }}
    """


def text_panel_stylesheet() -> str:
    """文字标注悬浮面板的 stylesheet。"""
    return f"""
    QFrame#textEditorPanel {{
        background: rgba(255, 255, 255, 250);
        border: 1px solid rgba(229, 231, 235, 250);
        border-radius: {RADIUS_MD}px;
    }}
    QLabel#textPanelHint, QLabel#textPanelField {{
        color: {TEXT_SECONDARY};
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE_CAPTION}px;
        font-weight: 700;
    }}
    QLabel#textPanelSubHint {{
        color: {TEXT_MUTED};
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE_CAPTION}px;
    }}
    QPlainTextEdit#textEditor {{
        background: {SURFACE_INPUT};
        border: 1px solid {BORDER_REGULAR};
        border-radius: {RADIUS_SM}px;
        padding: 7px 9px;
        color: {TEXT_PRIMARY};
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE_CAPTION}px;
        selection-background-color: {ACCENT_SELECTION};
    }}
    QSpinBox {{
        background: {SURFACE_INPUT};
        border: 1px solid {BORDER_REGULAR};
        border-radius: {RADIUS_SM}px;
        padding: 3px 6px;
        color: {TEXT_PRIMARY};
        min-height: 22px;
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE_CAPTION}px;
    }}
    QPushButton {{
        background: {SURFACE_BTN};
        color: {TEXT_BODY};
        border: 1px solid {BORDER_BTN};
        border-radius: {RADIUS_SM}px;
        padding: 5px 10px;
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE_CAPTION}px;
    }}
    QPushButton:hover {{
        background: {SURFACE_BTN_HOVER};
    }}
    """


def dialog_extras_stylesheet() -> str:
    """对话框（OCR 结果等）的补充样式：标题、辅助文字、QTextEdit。"""
    return f"""
    QLabel#heroSubtitle, QLabel#helper, QLabel#meta {{
        color: {TEXT_MUTED};
        line-height: 1.45;
    }}
    QLabel#title {{
        font-size: {FONT_SIZE_SECTION}px;
        font-weight: 700;
        color: {TEXT_PRIMARY};
    }}
    QTextEdit {{
        border: 1px solid {BORDER_REGULAR};
        border-radius: {RADIUS_MD}px;
        padding: 10px 12px;
        background: {SURFACE_INPUT};
        selection-background-color: {ACCENT_SELECTION};
        font-size: {FONT_SIZE_BODY}px;
        line-height: 1.5;
    }}
    QTextEdit:focus {{
        border-color: {ACCENT_BASE};
        background: {SURFACE_CARD};
    }}
    QTextEdit[readOnly="true"] {{
        background: {SURFACE_CARD};
        color: {TEXT_PRIMARY};
        font-size: {FONT_SIZE_SECTION}px;
        line-height: 1.6;
    }}
    QToolButton {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 {SURFACE_BTN});
        color: {TEXT_BODY};
        border: 1px solid {BORDER_BTN};
        border-radius: {RADIUS_MD}px;
        padding: 8px 14px;
        font-weight: 600;
    }}
    QToolButton:hover {{
        background: {SURFACE_BTN_HOVER};
        border-color: {BORDER_STRONG};
    }}
    QToolButton::menu-indicator {{
        subcontrol-position: right center;
        subcontrol-origin: padding;
        width: 12px;
        padding-right: 4px;
    }}
    QMenu {{
        background: {SURFACE_CARD};
        border: 1px solid {BORDER_REGULAR};
        border-radius: {RADIUS_MD}px;
        padding: 6px;
    }}
    QMenu::item {{
        padding: 7px 18px;
        border-radius: {RADIUS_SM}px;
        color: {TEXT_BODY};
    }}
    QMenu::item:hover {{
        background: {ACCENT_SOFT};
        color: {TEXT_PRIMARY};
    }}
    QMenu::separator {{
        height: 1px;
        background: {BORDER_LIGHT};
        margin: 5px 8px;
    }}
    """


def manager_extras_stylesheet() -> str:
    """历史库窗口的补充样式：辅助文字、预览块。"""
    return f"""
    QLabel#helper, QLabel#meta {{
        color: {TEXT_MUTED};
        line-height: 1.45;
    }}
    QLabel#preview {{
        background: #eef1f5;
        border: 1px solid #dce2ea;
        border-radius: {RADIUS_MD}px;
        color: {TEXT_MUTED};
    }}
    """


def settings_extras_stylesheet() -> str:
    """设置窗口的补充样式：headerIcon、字段标签、SpinBox、CheckBox、分区线。"""
    return f"""
    QLabel#headerIcon {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #eef2ff, stop:1 #ffffff);
        border: 1px solid {ACCENT_OUTLINE};
        border-radius: {RADIUS_MD}px;
    }}
    QLabel#heroSubtitle {{
        color: {TEXT_MUTED};
        font-size: {FONT_SIZE_BODY}px;
        line-height: 1.45;
    }}
    QLabel#helper {{
        color: {TEXT_MUTED};
        font-size: {FONT_SIZE_CAPTION}px;
        line-height: 1.5;
    }}
    QLabel#fieldLabel {{
        color: {TEXT_SECONDARY};
        font-weight: 700;
        font-size: {FONT_SIZE_BODY}px;
        margin-top: 2px;
    }}
    QLabel#sectionTitle {{
        margin-bottom: 2px;
    }}
    QLabel#sectionDivider {{
        background: {BORDER_LIGHT};
        min-height: 1px;
        max-height: 1px;
    }}
    QSpinBox {{
        border: 1px solid {BORDER_REGULAR};
        border-radius: {RADIUS_MD}px;
        padding: 8px 10px;
        background: {SURFACE_INPUT};
        min-width: 110px;
    }}
    QSpinBox:focus {{
        border-color: {ACCENT_BASE};
        background: {SURFACE_CARD};
    }}
    QCheckBox {{
        spacing: 10px;
        color: {TEXT_BODY};
        padding: 6px 2px;
        min-height: 24px;
    }}
    QCheckBox:hover {{
        color: {TEXT_PRIMARY};
    }}
    QCheckBox::indicator {{
        width: 19px;
        height: 19px;
        border: 2px solid {BORDER_STRONG};
        border-radius: 6px;
        background: {SURFACE_CARD};
    }}
    QCheckBox::indicator:hover {{
        border-color: {ACCENT_BASE};
        background: {ACCENT_SOFTER};
    }}
    QCheckBox::indicator:checked {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #6366f1, stop:1 {ACCENT_BASE});
        border-color: {ACCENT_BASE};
        image: none;
    }}
    QCheckBox::indicator:checked:hover {{
        background: {ACCENT_HOVER};
        border-color: {ACCENT_HOVER};
    }}
    QLineEdit[capturing="true"] {{
        border: 2px solid {ACCENT_BASE};
        background: {ACCENT_SOFTER};
        color: {ACCENT_BASE};
        font-weight: 700;
    }}
    QFrame#footer {{
        background: #fbfcfe;
        border-top: 1px solid {BORDER_LIGHT};
    }}
    QLabel#footerHelper {{
        color: {TEXT_MUTED};
        font-size: {FONT_SIZE_CAPTION}px;
    }}
    QFrame#settingsSidebar {{
        background: #fbfcfe;
        border: 1px solid {BORDER_LIGHT};
        border-radius: {RADIUS_LG}px;
    }}
    QLabel#sidebarTitle {{
        color: {TEXT_MUTED};
        font-size: {FONT_SIZE_CAPTION}px;
        font-weight: 700;
        letter-spacing: 1px;
        padding: 4px 6px 2px 6px;
    }}
    QPushButton[role="nav"] {{
        text-align: left;
        background: transparent;
        border: 1px solid transparent;
        border-left: 3px solid transparent;
        color: {TEXT_SECONDARY};
        padding: 10px 12px 10px 13px;
        line-height: 1.4;
        font-size: {FONT_SIZE_BODY}px;
        font-weight: 600;
    }}
    QPushButton[role="nav"]:hover {{
        background: #ffffff;
        border-color: {BORDER_LIGHT};
        color: {TEXT_PRIMARY};
    }}
    QPushButton[role="nav"]:checked {{
        background: #ffffff;
        color: {TEXT_PRIMARY};
        border-color: {ACCENT_OUTLINE};
        border-left: 3px solid {ACCENT_BASE};
        font-weight: 700;
    }}
    QPushButton[role="nav"]:checked:hover {{
        background: {ACCENT_SOFT};
    }}
    """
