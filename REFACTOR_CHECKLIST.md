# QuickShot 最小改动重构清单

> 基于 2026-05-28 整体审查，按"最小改动、最大收益"排序，不改业务逻辑。

---

## 阶段 1：零风险清理（建议立即做，半天内可完成）

- [x] **清 unused imports** ✅
  - `quickshot/hotkey.py:5` — 移除未使用的 `QObject` 导入
  - `quickshot/overlay/_snap.py:9` — 移除未使用的 `Optional` 导入
- [x] **修 README 编码** ✅ (文件本身编码正确，为终端显示问题) — `README.md` 全文 UTF-8 乱码，重新确认文件编码并修复，确保 GitHub/编辑器正常显示
- [x] **统一 .gitignore** ✅ — 当前 `__pycache__/` 和 `*.py[cod]` 已有，建议补充 `*.egg-info/` 和 `.eggs/`

---

## 阶段 2：结构性拆分（建议 1-2 周内完成，每项可独立提交）

### 2a. `quickshot/main.py` 评估（572 行 / 37 函数）⏭️ 已跳过

当前 `QuickShotApp` 类身兼多职：托盘菜单、热键回调、overlay 生命周期、设置窗口、历史窗口、pin 管理器的创建/展示。建议拆为：

| 新模块 | 职责 | 来源 |
|---|---|---|
| `quickshot/tray.py` | `TrayManager`：托盘图标、菜单创建、消息提示 | `create_tray_menu`、`create_icon`、`run_after_tray_menu` |
| `quickshot/window_registry.py` | `WindowRegistry`：设置/历史/pin 窗口的懒加载与 present | `present_window`、`show_settings`、`show_history`、`show_pin_manager` |
| `quickshot/main.py` | 保留 `QuickShotApp` 为薄壳：组合上面两者 + 热键连接 + overlay 生命周期 |

改动范围：`main.py` 内部搬方法，对外接口不变。测试不影响。

### 2b. `quickshot/overlay/widget.py` 瘦身 ✅（661→566 行，文本面板提取到 TextEditorMixin）

`FloatingSnipOverlay` 已经用了 mixin 模式，但 widget 本体依然承载了 `__init__` 超长初始化、内联文本面板 UI 构建、兼容属性等。建议：

| 改动 | 内容 |
|---|---|
| ✅ 提取 `_init_text_panel()` | 把 `__init__` 中 ~80 行文本编辑面板构建代码移到 `TextEditorMixin` 或新方法 |
| ⏭️ 提取 `_init_annotations()` （暂不需要） | 把标注状态（`active_tool`、`drag_*`、`annotations` 等）初始化归入 `DrawingMixin._init_drawing_state()` |
| ✅ 缩短 `__init__` | 目标：从 ~150 行降到 ~60 行，只留核心属性赋值和信号连接 |

### 2c. `quickshot/ocr.py` 整理 ✅（710→495 行，提取 ocr_utils.py + windows_ocr.ps1）

| 改动 | 内容 |
|---|---|
| ✅ PowerShell 脚本外置 | 把 `WINDOWS_OCR_SCRIPT`（~60 行）移到 `assets/windows_ocr.ps1`，用 `Path.read_text()` 加载 |
| ✅ 文本清洗函数归组 | `clean_ocr_text`、`deep_clean_ocr_text`、`format_rapidocr_result` 等提取到 `quickshot/ocr_utils.py` |
| ✅ `quickshot/ocr.py` 瘦身 | 只保留 job 调度、信号、引擎调用，目标从 710 行降到 ~350 行 |

---

## 阶段 3：提升健壮性（建议 2-4 周内渐进完成）

### 3a. 上传链路加固（`quickshot/uploader.py`）

- [x] `GitHubUploader.upload()` 用 `base64` ✅ 已加 10MB 上限检查 编码整个文件到内存，大图（>10MB）有 OOM 风险。建议加 size 上限检查，超限时给出明确提示。
- [x] `_format_error` 中 ✅ 已补 5xx 通用提示 + 重试 `401/403/404/422` 的中文提示已覆盖，建议补 `5xx` 通用提示并重试 1 次（带 backoff）。
- [x] `LocalArchiveUploader.upload()` 中文件名 ✅ 已加 200 字符截断带时间戳+原名，无长度保护；长文件名场景建议截断。

### 3b. 复杂度监控

- [ ] 为 500 行以上的模块（`_paint.py`、`pin.py`、`theme.py`、`_events.py`、`ocr.py`、`widget.py`、`settings.py`、`_manager_history.py`、`main.py`、`_manager_pin.py`）设置行数/函数数上限基线，CI 中用简单脚本告警。
- [ ] 对 `overlay/_paint.py`（919 行 / 25 函数）重点跟踪：paintEvent 相关逻辑最易产生回归。

### 3c. 测试补充建议

- [ ] `tests/test_github_uploader.py` — 补 `_format_error` 对 5xx 响应的行为
- [ ] `tests/test_main.py`（新建）— 对 `QuickShotApp._hotkey_allowed`、`present_window` 等非 GUI 逻辑做单元测试
- [ ] `tests/test_ocr_utils.py` — 如果 2c 拆出 `ocr_utils.py`，为其补独立测试（当前 `test_ocr_utils.py` 已存在但绑定旧路径）

---

## 执行顺序建议

```
阶段1（零风险）→ 2c（ocr 拆分，收益/风险比最高）→ 2a（main 拆分）
→ 2b（overlay 瘦身）→ 3a（上传加固）→ 3b+3c（长期）
```

每项都可独立提 PR，不依赖其他项。
