"""hotkey_util — 快捷键字符串解析、格式化、VK 码映射。"""

from typing import Dict, List, Optional, Tuple

# ── 修饰键映射 ──

MODIFIER_MAP: Dict[str, Tuple[int, List[int]]] = {
    "Ctrl":  (0x0002, [0x11, 0xA2, 0xA3]),
    "Shift": (0x0004, [0x10, 0xA0, 0xA1]),
    "Alt":   (0x0001, [0x12, 0xA4, 0xA5]),
    "Win":   (0x0008, [0x5B, 0x5C]),
}

MOD_FLAG_TO_NAME: Dict[int, str] = {v[0]: k for k, v in MODIFIER_MAP.items()}

# ── VK 码 ↔ 名称 ──

def _build_vk_maps() -> Tuple[Dict[int, str], Dict[str, int]]:
    vk_to_name: Dict[int, str] = {}
    name_to_vk: Dict[str, int] = {}

    # A-Z
    for i in range(26):
        vk = 0x41 + i
        name = chr(65 + i)
        vk_to_name[vk] = name
        name_to_vk[name] = vk

    # 0-9
    for i in range(10):
        vk = 0x30 + i
        name = str(i)
        vk_to_name[vk] = name
        name_to_vk[name] = vk

    # F1-F12
    for i in range(12):
        vk = 0x70 + i
        name = f"F{i + 1}"
        vk_to_name[vk] = name
        name_to_vk[name] = vk

    # 特殊键
    specials = [
        (0x20, "Space"), (0x2D, "Insert"), (0x2E, "Delete"),
        (0x24, "Home"), (0x23, "End"), (0x21, "PgUp"), (0x22, "PgDn"),
        (0x09, "Tab"), (0x0D, "Enter"), (0x1B, "Esc"),
        (0x25, "Left"), (0x26, "Up"), (0x27, "Right"), (0x28, "Down"),
        (0x60, "Num0"), (0x61, "Num1"), (0x62, "Num2"), (0x63, "Num3"),
        (0x64, "Num4"), (0x65, "Num5"), (0x66, "Num6"), (0x67, "Num7"),
        (0x68, "Num8"), (0x69, "Num9"),
        (0x6A, "Num*"), (0x6B, "Num+"), (0x6D, "Num-"), (0x6E, "Num."),
        (0x6F, "Num/"),
        (0x14, "Caps"), (0x90, "NumLock"), (0x91, "ScrollLock"),
        (0xBA, ";"), (0xBB, "="), (0xBC, ","), (0xBD, "-"), (0xBE, "."),
        (0xBF, "/"), (0xC0, "`"), (0xDB, "["), (0xDC, "\\"), (0xDD, "]"),
        (0xDE, "'"),
    ]
    for vk, name in specials:
        vk_to_name[vk] = name
        name_to_vk[name] = vk

    return vk_to_name, name_to_vk


VK_NAME_MAP, NAME_VK_MAP = _build_vk_maps()

# ── Qt 按键码 → VK 名称 ──

_QT_KEY_TO_VK: Dict[int, int] = {}

def _build_qt_map() -> Dict[int, int]:
    mapping: Dict[int, int] = {}
    # Qt.Key.Key_A (0x41) 到 Key_Z — 与 VK 码相同
    for i in range(26):
        mapping[0x41 + i] = 0x41 + i
    # Qt.Key.Key_0 (0x30) 到 Key_9 — 与 VK 码相同
    for i in range(10):
        mapping[0x30 + i] = 0x30 + i
    # F1-F12 — Qt 与 VK 码相同
    for i in range(12):
        mapping[0x01000030 + i] = 0x70 + i  # Qt.Key.Key_F1 = 0x01000030
    # 特殊键
    qt_specials = [
        (0x20, 0x20),    # Space
        (0x01000006, 0x2D),  # Insert
        (0x01000007, 0x2E),  # Delete
        (0x01000010, 0x24),  # Home
        (0x01000011, 0x23),  # End
        (0x01000016, 0x21),  # PgUp
        (0x01000017, 0x22),  # PgDn
        (0x01000001, 0x25),  # Left
        (0x01000013, 0x26),  # Up
        (0x01000002, 0x27),  # Right
        (0x01000015, 0x28),  # Down
        (0x09, 0x09),    # Tab
        (0x01000004, 0x0D),  # Return/Enter
        (0x01000000, 0x1B),  # Esc
    ]
    for qt_key, vk in qt_specials:
        mapping[qt_key] = vk
    return mapping

_QT_KEY_TO_VK = _build_qt_map()


def qt_key_to_name(qt_key: int) -> Optional[str]:
    """将 Qt.Key 枚举值转换为快捷键显示名称。"""
    vk = _QT_KEY_TO_VK.get(qt_key)
    if vk is not None:
        return VK_NAME_MAP.get(vk)
    return None

# ── 解析 / 格式化 ──

def parse_hotkey_string(text: str) -> Optional[Tuple[int, int]]:
    """解析 'Ctrl+Shift+A' 为 (modifier_flags, vk_code)，失败返回 None。"""
    if not text:
        return None
    parts = [p.strip() for p in text.split("+") if p.strip()]
    if len(parts) < 2:
        return None

    mod_flags = 0
    vk_code = 0
    mod_count = 0
    key_count = 0

    for part in parts:
        if part in MODIFIER_MAP:
            flag, _ = MODIFIER_MAP[part]
            mod_flags |= flag
            mod_count += 1
        elif part.upper() in NAME_VK_MAP:
            vk_code = NAME_VK_MAP[part.upper()]
            key_count += 1
        elif part in NAME_VK_MAP:
            vk_code = NAME_VK_MAP[part]
            key_count += 1
        else:
            return None

    if key_count != 1 or mod_count < 1 or mod_count > 2:
        return None
    return (mod_flags, vk_code)


def format_hotkey_string(modifiers: int, vk: int) -> str:
    """将 (modifier_flags, vk_code) 格式化为 'Ctrl+Shift+A'。"""
    parts: List[str] = []
    for name in ("Ctrl", "Shift", "Alt", "Win"):
        flag = MODIFIER_MAP[name][0]
        if modifiers & flag:
            parts.append(name)
    parts.append(VK_NAME_MAP.get(vk, f"VK(0x{vk:02X})"))
    return "+".join(parts)


def get_vk_poll_codes(text: str) -> Optional[Tuple[List[int], int]]:
    """获取用于 GetAsyncKeyState 轮询的 VK 码列表。

    返回 ([所有修饰键 VK 码...], 按键 VK 码)。
    例如 'Ctrl+Shift+A' → ([0x11, 0xA2, 0xA3, 0x10, 0xA0, 0xA1], 0x41)
    """
    parsed = parse_hotkey_string(text)
    if parsed is None:
        return None
    mod_flags, vk = parsed
    poll_mods: List[int] = []
    for name in ("Ctrl", "Shift", "Alt", "Win"):
        flag = MODIFIER_MAP[name][0]
        if mod_flags & flag:
            poll_mods.extend(MODIFIER_MAP[name][1])
    return (poll_mods, vk)


def validate_hotkey(text: str) -> Tuple[bool, str]:
    """验证快捷键字符串是否有效。返回 (是否有效, 错误信息)。"""
    if not text:
        return False, "快捷键不能为空"
    parsed = parse_hotkey_string(text)
    if parsed is None:
        return False, "快捷键格式无效，需要修饰键+按键（如 Ctrl+Shift+A）"
    return True, ""
