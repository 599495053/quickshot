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

TEXT_PRIMARY = "#0f172a"
TEXT_BODY = "#1f2937"
TEXT_SECONDARY = "#475569"
TEXT_MUTED = "#64748b"

SURFACE_APP = "#f4f7fb"
SURFACE_CARD = "#ffffff"
SURFACE_INPUT = "#fbfcfe"
SURFACE_SUBTLE = "#f8fafc"
SURFACE_HERO = "#f8fbff"
SURFACE_BTN = "#eef2f7"
SURFACE_BTN_HOVER = "#e7edf5"
SURFACE_HEADER_ICON = "#eff6ff"

BORDER_LIGHT = "#e3e8f0"
BORDER_REGULAR = "#d7deea"
BORDER_STRONG = "#cbd5e1"
BORDER_BTN = "#d5dde8"

ACCENT_BASE = "#2563eb"
ACCENT_HOVER = "#1d4ed8"
ACCENT_SOFT = "#eaf2ff"
ACCENT_SOFTER = "#f3f8ff"
ACCENT_OUTLINE = "#bfd6ff"
ACCENT_SELECTION = "#dbeafe"

DANGER_BASE = "#be123c"
DANGER_SOFT = "#fff1f2"
DANGER_SOFT_HOVER = "#ffe4e6"
DANGER_OUTLINE = "#fecdd3"

SUCCESS_BASE = "#1b844a"
SUCCESS_SOFT = "#f6fdf9"
SUCCESS_SOFT_HOVER = "#f0fcf6"
SUCCESS_OUTLINE = "#bce8cd"

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


def qc(token: str, alpha: int = 255) -> QColor:
    """按 token 名取 QColor。``alpha`` 范围 0-255。"""
    hex_color = _COLOR_TOKENS.get(token)
    if hex_color is None:
        raise KeyError(f"unknown color token: {token!r}")
    color = QColor(hex_color)
    if alpha < 255:
        color.setAlpha(alpha)
    return color


# ── 半透明 / 绘制专用 QColor 工厂 ──
# 这些颜色带 alpha 通道，无法用十六进制表达，直接以函数形式提供，
# 让调用方含义清晰。

def overlay_dim() -> QColor:
    """框选阶段的灰色遮罩。"""
    return QColor(0, 0, 0, 100)


def overlay_solid() -> QColor:
    """调整选区时的纯黑外圈。"""
    return QColor(0, 0, 0, 255)


def floating_bg() -> QColor:
    """工具栏 / 消息条等悬浮 panel 的深色背景。"""
    return QColor(18, 24, 33, 232)


def floating_border() -> QColor:
    """floating panel 的高光描边。"""
    return QColor(255, 255, 255, 28)


def floating_text() -> QColor:
    return QColor(244, 247, 251)


def panel_bg() -> QColor:
    """白底悬浮 panel（颜色/线宽样式面板）的背景。"""
    return QColor(255, 255, 255, 248)


def panel_border() -> QColor:
    return QColor(219, 226, 236, 248)


def handle_fill() -> QColor:
    """选区把手填色。"""
    return QColor(255, 255, 255, 240)


# ── 几何 token ──

RADIUS_SM = 6
RADIUS_MD = 8
RADIUS_LG = 12

SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16

# 阴影：(offset_px, alpha_0_255) 元组数组，调用方按 offset 由外向内画。
SHADOW_CARD = ((5, 18), (2, 28))
SHADOW_FLOATING = ((6, 18), (2, 35))


# ── 字体 token ──

FONT_FAMILY = "Microsoft YaHei, Segoe UI, sans-serif"

FONT_SIZE_CAPTION = 12
FONT_SIZE_BODY = 13
FONT_SIZE_SECTION = 15
FONT_SIZE_HERO = 22


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
        background: {SURFACE_HERO};
        border-color: {ACCENT_OUTLINE};
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
        color: {TEXT_MUTED};
        padding: 0 2px;
    }}
    QLineEdit, QPlainTextEdit, QComboBox {{
        border: 1px solid {BORDER_REGULAR};
        border-radius: {RADIUS_MD}px;
        padding: 8px 10px;
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
        width: 22px;
    }}
    QListWidget {{
        border: 1px solid {BORDER_LIGHT};
        border-radius: {RADIUS_MD}px;
        background: {SURFACE_INPUT};
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
        background: {SURFACE_BTN};
        color: {TEXT_BODY};
        border: 1px solid {BORDER_BTN};
        border-radius: {RADIUS_MD}px;
        padding: 8px 14px;
    }}
    QPushButton:hover {{
        background: {SURFACE_BTN_HOVER};
    }}
    QPushButton[role="primary"] {{
        background: {ACCENT_BASE};
        color: #ffffff;
        border-color: {ACCENT_BASE};
    }}
    QPushButton[role="primary"]:hover {{
        background: {ACCENT_HOVER};
        border-color: {ACCENT_HOVER};
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
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER_STRONG};
        border-radius: 4px;
        min-height: 30px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {TEXT_MUTED};
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
        border: 1px solid rgba(214, 223, 237, 250);
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
    }}
    QToolButton {{
        background: {SURFACE_BTN};
        color: {TEXT_BODY};
        border: 1px solid {BORDER_BTN};
        border-radius: {RADIUS_MD}px;
        padding: 8px 14px;
        font-weight: normal;
    }}
    QToolButton:hover {{
        background: {SURFACE_BTN_HOVER};
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
        padding: 4px;
    }}
    QMenu::item {{
        padding: 6px 16px;
        border-radius: {RADIUS_SM}px;
    }}
    QMenu::item:hover {{
        background: {SURFACE_SUBTLE};
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
        background: {SURFACE_SUBTLE};
        border: 1px solid {BORDER_LIGHT};
        border-radius: {RADIUS_MD}px;
        color: {TEXT_MUTED};
    }}
    """


def settings_extras_stylesheet() -> str:
    """设置窗口的补充样式：headerIcon、字段标签、SpinBox、CheckBox、分区线。"""
    return f"""
    QLabel#headerIcon {{
        background: {SURFACE_HEADER_ICON};
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
        padding: 4px 2px;
        min-height: 22px;
    }}
    QCheckBox:hover {{
        color: {TEXT_PRIMARY};
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border: 2px solid {BORDER_STRONG};
        border-radius: 5px;
        background: {SURFACE_CARD};
    }}
    QCheckBox::indicator:hover {{
        border-color: {ACCENT_BASE};
        background: {ACCENT_SOFTER};
    }}
    QCheckBox::indicator:checked {{
        background: {ACCENT_BASE};
        border-color: {ACCENT_BASE};
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
        background: {SURFACE_CARD};
        border-top: 1px solid {BORDER_LIGHT};
    }}
    QLabel#footerHelper {{
        color: {TEXT_MUTED};
        font-size: {FONT_SIZE_CAPTION}px;
    }}
    QFrame#settingsSidebar {{
        background: {SURFACE_CARD};
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
        padding: 10px 12px 10px 14px;
        line-height: 1.4;
        font-size: {FONT_SIZE_BODY}px;
    }}
    QPushButton[role="nav"]:hover {{
        background: {SURFACE_SUBTLE};
        color: {TEXT_PRIMARY};
    }}
    QPushButton[role="nav"]:checked {{
        background: {ACCENT_SOFTER};
        color: {TEXT_PRIMARY};
        border-color: {ACCENT_OUTLINE};
        border-left: 3px solid {ACCENT_BASE};
        font-weight: 700;
    }}
    QPushButton[role="nav"]:checked:hover {{
        background: {ACCENT_SOFT};
    }}
    """
