import json
import os
import sys
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Callable, Dict, List

from .utils import APP_NAME, REG_NAME, REG_RUN_PATH, debug_log


def _clamp_int(low: int, high: int) -> Callable[[Any], int]:
    """返回一个 loader，将输入值转为 int 并钳制在 [low, high] 范围内。"""
    def _convert(v: Any) -> int:
        return max(low, min(high, int(v)))
    return _convert


def _str_or_default(default: str) -> Callable[[Any], str]:
    """返回一个 loader，将输入转为 str，空字符串则用 default。"""
    def _convert(v: Any) -> str:
        return str(v) if v else default
    return _convert


def _presets_loader(v: Any) -> List[dict]:
    """annotation_presets 的 loader：空列表或非列表则返回 None（表示不覆盖默认值）。"""
    if isinstance(v, list) and v:
        return v
    return None


# 不参与序列化的运行时字段名
_RUNTIME_FIELDS = frozenset({"app_dir", "config_path"})


@dataclass
class Config:
    """应用配置，声明式定义字段 + 自动 load/save。

    所有字段均有类型注解和默认值。需要范围约束的字段通过 metadata["loader"]
    指定转换函数。新增字段只需在此处加一行，load/save/export/import 自动覆盖。
    """

    # 默认样式预设（类级别常量，不参与 dataclass，不加类型注解）
    DEFAULT_PRESETS = [
        {"name": "红色标注", "color": "#ff4646", "width": 5},
        {"name": "蓝色细线", "color": "#1488ff", "width": 3},
        {"name": "绿色粗线", "color": "#18a058", "width": 8},
    ]

    # ── 可序列化配置字段 ──

    save_dir: str = field(default_factory=lambda: str(Path.home() / "Pictures" / APP_NAME))
    save_dir_mode: str = "flat"  # flat / date / subdir
    save_format: str = "png"  # png / jpg / webp / bmp
    jpeg_quality: int = field(default=90, metadata={"loader": _clamp_int(1, 100)})
    auto_copy: bool = True
    show_notifications: bool = True
    hdr_color_accurate: bool = False
    auto_history: bool = True
    history_limit: int = field(default=200, metadata={"loader": _clamp_int(20, 1000)})
    watermark_text: str = ""
    region_hotkey: str = "Ctrl+Shift+A"
    window_hotkey: str = "Ctrl+Shift+W"
    history_hotkey: str = ""
    pin_hotkey: str = ""
    ocr_hotkey: str = ""
    delay_seconds: int = field(default=0, metadata={"loader": _clamp_int(0, 10)})
    grid_color: str = "#ffffff80"
    watermark_color: str = "#ffffff40"
    # 工作流配置
    workflow_auto_ocr: bool = False
    workflow_auto_upload: bool = False
    workflow_copy_markdown: bool = False
    workflow_uploader: str = "local"
    # GitHub 上传器配置（token 不存这里，存 keyring）
    github_owner: str = ""
    github_repo: str = ""
    github_branch: str = field(default="main", metadata={"loader": _str_or_default("main")})
    github_path_prefix: str = field(default="screenshots", metadata={"loader": _str_or_default("screenshots")})
    annotation_presets: List[dict] = field(default_factory=lambda: list(Config.DEFAULT_PRESETS))

    # ── 运行时字段（不序列化）──

    app_dir: Path = field(init=False, repr=False)
    config_path: Path = field(init=False, repr=False)

    def __post_init__(self) -> None:
        base = os.environ.get("APPDATA") or str(Path.home())
        self.app_dir = Path(base) / APP_NAME
        self.config_path = self.app_dir / "config.json"
        self.load()

    # ── 通用 load/save ──

    def _serializable_fields(self):
        """返回参与序列化的字段（排除运行时字段和 DEFAULT_PRESETS）。"""
        for f in fields(self):
            if f.name in _RUNTIME_FIELDS or f.name == "DEFAULT_PRESETS":
                continue
            yield f

    def load(self) -> None:
        try:
            if not self.config_path.exists():
                return
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
            for f in self._serializable_fields():
                key = f.metadata.get("json_key") or f.name
                if key not in data:
                    continue
                raw = data[key]
                loader = f.metadata.get("loader")
                if loader:
                    value = loader(raw)
                    # loader 返回 None 表示不覆盖（如 annotation_presets 空列表）
                    if value is None:
                        continue
                else:
                    value = raw
                setattr(self, f.name, value)
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
            debug_log(f"config load failed: {exc}")

    def save(self) -> None:
        try:
            self.app_dir.mkdir(parents=True, exist_ok=True)
            data = {}
            for f in self._serializable_fields():
                key = f.metadata.get("json_key") or f.name
                data[key] = getattr(self, f.name)
            self.config_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            debug_log(f"config save failed: {exc}")

    # ── 导入导出 ──

    def to_dict(self) -> Dict[str, Any]:
        """导出为 dict（供 settings.py export_settings 使用）。"""
        data = {}
        for f in self._serializable_fields():
            key = f.metadata.get("json_key") or f.name
            data[key] = getattr(self, f.name)
        return data

    def import_from_dict(self, data: Dict[str, Any]) -> None:
        """从 dict 导入（供 settings.py import_settings 使用）。"""
        for f in self._serializable_fields():
            key = f.metadata.get("json_key") or f.name
            if key not in data:
                continue
            raw = data[key]
            loader = f.metadata.get("loader")
            if loader:
                value = loader(raw)
                if value is None:
                    continue
            else:
                value = raw
            setattr(self, f.name, value)
        self.save()

    # ── 路径辅助 ──

    def ensure_save_dir(self) -> str:
        try:
            path = Path(self.save_dir)
            if self.save_dir_mode == "date":
                import datetime
                today = datetime.date.today()
                path = path / today.strftime("%Y") / today.strftime("%m-%d")
            path.mkdir(parents=True, exist_ok=True)
            return str(path)
        except OSError as exc:
            debug_log(f"ensure_save_dir failed: {exc}")
            return self.save_dir

    def history_dir(self) -> Path:
        return self.app_dir / "history"

    def history_index_path(self) -> Path:
        return self.history_dir() / "index.json"

    def ensure_history_dir(self) -> Path:
        try:
            path = self.history_dir()
            path.mkdir(parents=True, exist_ok=True)
            return path
        except OSError as exc:
            debug_log(f"ensure_history_dir failed: {exc}")
            return self.history_dir()


class StartupManager:
    @staticmethod
    def command() -> str:
        if getattr(sys, "frozen", False):
            return f'"{sys.executable}"'
        script = Path(__file__).resolve().parent.parent / "launcher.py"
        return f'"{sys.executable}" "{script}"'

    @staticmethod
    def is_enabled() -> bool:
        if not sys.platform.startswith("win"):
            return False
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_PATH, 0, winreg.KEY_READ) as key:
                winreg.QueryValueEx(key, REG_NAME)
            return True
        except (FileNotFoundError, OSError):
            # 注册表 Run 项缺失即"未启用开机自启"，是正常分支
            return False

    @staticmethod
    def set_enabled(enabled: bool) -> None:
        if not sys.platform.startswith("win"):
            return
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REG_RUN_PATH,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            if enabled:
                winreg.SetValueEx(key, REG_NAME, 0, winreg.REG_SZ, StartupManager.command())
            else:
                try:
                    winreg.DeleteValue(key, REG_NAME)
                except FileNotFoundError:
                    pass
