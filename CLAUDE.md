# CLAUDE.md - QuickShot 项目指南

## 项目概述

QuickShot 是一款 Windows 截图工具，基于 PyQt6，支持区域截图、窗口截图、标注、贴图、OCR、历史库、上传等功能。

## 运行与构建

```bash
python launcher.py          # 标准入口
python -m quickshot         # 模块入口
python -m pytest -q         # 运行测试
python -m pyflakes quickshot launcher.py build_config.py  # 静态检查
.\build.ps1                # PyInstaller 打包
```

## 架构

### 入口
- `launcher.py` → 调用 `quickshot.main.main()`
- `quickshot/__main__.py` → 支持 `python -m quickshot`

### 核心模块
- `quickshot/main.py` — 应用主类 `QuickShotApp`：托盘、热键、overlay 生命周期、窗口管理
- `quickshot/config.py` — `Config` dataclass，JSON 自动 load/save，字段级 loader 约束
- `quickshot/hotkey.py` — Windows RegisterHotKey 全局热键（需管理员权限时降级到轮询）
- `quickshot/hotkey_util.py` — 快捷键字符串解析（如 "Ctrl+Shift+A" → VK 码）
- `quickshot/screenshot.py` — 截图：DXcam/WGC/DXGI 多后端，HDR 支持
- `quickshot/pipeline.py` — 截图工作流编排（截图→OCR→上传→复制）

### Overlay（截图编辑器）
- `quickshot/overlay/widget.py` — `FloatingSnipOverlay` 主 widget，通过 mixin 组合功能
- `_events.py` — 鼠标/键盘事件分发
- `_selection.py` — 选区拖拽与调整
- `_paint.py` — paintEvent 渲染（选区/编辑/放大镜）
- `_toolbar.py` — 浮动工具栏
- `_drawing.py` — 标注绘制逻辑
- `_text_editor.py` — 内联文本编辑面板
- `_snap.py` — 选区吸附窗口边缘
- `_undo.py` — 撤销/重做栈
- `_export.py` — 复制/保存/完成导出
- `_ocr.py` — overlay 内 OCR 调用
- `_postprocess.py` — 后处理（水印、网格）
- `annotation_painter.py` — 标注渲染器
- `coords.py` — 逻辑/物理坐标转换

### OCR
- `quickshot/ocr.py` — OCR job 调度、RapidOCR/Windows OCR 引擎调用、隐私检测
- `quickshot/ocr_utils.py` — 文本清洗/格式化工具函数（从 ocr.py 拆出）
- `quickshot/ocr_engine.py` — OCR 引擎抽象层（OcrEngine + OcrEngineRegistry）
- `assets/windows_ocr.ps1` — Windows 系统 OCR PowerShell 脚本

### 上传
- `quickshot/uploader.py` — `Uploader` 抽象 + `LocalArchiveUploader` + `GitHubUploader`
- `quickshot/secrets.py` — keyring 凭据管理（GitHub PAT）

### 其他
- `quickshot/history.py` — 截图历史存储（JSON 索引 + 图片文件）
- `quickshot/pin.py` — 贴图窗口（PinWindow）
- `quickshot/manager.py` — 导入 HistoryWindow/PinManagerWindow
- `_manager_history.py` / `_manager_pin.py` — 历史/贴图管理窗口
- `quickshot/settings.py` — 设置窗口
- `quickshot/dialogs.py` — OCR 结果/导出等对话框
- `quickshot/translator.py` — MyMemory 翻译（截图内文字翻译）
- `quickshot/theme.py` — 暗色主题色板
- `quickshot/utils.py` — 工具函数（图标、日志、剪贴板、HDR 处理）
- `quickshot/window_enum.py` — 枚举可见窗口（用于窗口截图和吸附）
- `quickshot/ui.py` — 通用 UI 组件（卡片、按钮样式）

## 代码约定

- Python 3.10+，类型注解全覆盖
- PyQt6 为唯一 GUI 框架
- 所有模块级副作用代码放在函数/类内，不在模块顶层执行（DPI/标准流除外）
- 配置用 dataclass + JSON，敏感信息走 keyring
- OCR 引擎用注册表模式，新增引擎只需继承 `OcrEngine`
- 上传器用注册表模式，新增后端只需继承 `Uploader`
- 测试在 `tests/` 下，用 pytest，当前 449 用例
- 提交前跑 `pyflakes` + `pytest` 确保零警告零失败
- 换行符统一 LF（见 `.gitattributes`）

## 常见陷阱

- Windows DPI：必须在 Qt 导入前调用 `SetProcessDpiAwarenessContext`
- PyInstaller 无控制台模式：`sys.stdout/stderr` 可能为 None
- overlay mixin 链：`FloatingSnipOverlay` 继承顺序影响 MRO，修改需谨慎
- GitHub Contents API：单文件 base64 编码，大文件（>10MB）会很慢
- keyring：Windows 上用 Windows Credential Manager，需 pywin32
