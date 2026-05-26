# QuickShot v5.2.0 更新日志

## 发布日期：2026-05-25

---

## 新功能

### 截图后工作流（Pipeline）

新增可插拔的截图后处理流程：截图完成后按配置依次执行「上传 → 复制 Markdown 链接」等步骤，每个步骤独立可开关、单步失败不阻塞后续。

- 设置项：
  - 截图完成后自动上传（`workflow_auto_upload`）
  - 上传成功后自动复制 Markdown 链接（`workflow_copy_markdown`）
  - 截图完成后自动 OCR 并把文本写入剪贴板（`workflow_auto_ocr`）
- 触发点：`quickshot/overlay/_history.py` 在截图保存后调用 `run_post_capture_pipeline`，优先用户主动保存路径，回退到历史库 PNG，再回退到临时文件
- 设计：Step 间通过 `PipelineContext` 传递 `image_path / upload_result / markdown_link / ocr_text`，错误和消息分通道收集

### 上传器抽象

新增统一的上传器接口，支持图床、对象存储、本地存档等多种后端。

- `Uploader` 抽象基类：`identifier()` / `display_name()` / `is_configured()` / `upload()`
- 内置 `LocalArchiveUploader`：把图片复制到 `%APPDATA%/QuickShot/uploads`，返回 `file://` URL，开箱即用
- 内置 `GitHubUploader`：通过 GitHub Contents API 提交到指定仓库分支，路径形如 `{prefix}/{YYYY}/{MM-DD}/{uuid}_{filename}`，返回 `raw.githubusercontent.com` 链接
- `UploaderRegistry`：按 identifier 注册和查询，`build_default_registry` 一键构建包含本地+GitHub 的注册表
- 链接格式化辅助：`format_markdown_link` / `format_html_link`

### GitHub 上传集成

- 设置界面新增上传卡片：选择上传器、填写 owner / repo / branch / path_prefix
- Personal Access Token 通过 keyring 存到系统凭据管理器，不落地到配置文件
- 友好的 HTTP 错误映射：401 Token 无效、403 权限不足/限流、404 仓库不存在、422 文件已存在
- Token 输入框走 `EchoMode.Password`，提供「保存 Token / 清除 Token」按钮

### 凭据存储（keyring）

新增 `quickshot/secrets.py` 封装 keyring 调用：

- 跨平台：Windows 凭据管理器 / macOS Keychain / Linux Secret Service
- 接口：`get_secret / set_secret / delete_secret`、`get_github_token / set_github_token / delete_github_token`
- 失败兜底：keyring 不可用时返回空串而非抛异常，避免污染主流程

### Pin 贴图窗口重写

`quickshot/pin.py` 从基础贴图升级为完整的桌面贴图工作台：

- **缩放**：滚轮以光标位置为锚点缩放（0.12x ~ 4.0x），`+/-` 键步进，`0` 键重置
- **翻转**：水平 / 垂直翻转
- **透明度**：35% ~ 100% 调节，右键菜单 5 档预设
- **锁定**：`L` 键切换，锁定后不可拖动也不响应滚轮
- **置顶**：`T` 键切换，重应用 `WindowStaysOnTopHint` 并保持几何
- **重命名**：`R` 键弹出 `QInputDialog`，名称用于搜索匹配
- **位置微调**：方向键 1px、Shift+方向键 10px
- **Hover 信息条**：左上角圆角胶囊显示「名称 / 缩放 / 置顶或普通 / 锁定或可拖动 / 透明度」
- **右键菜单**：重命名 / 锁定 / 置顶 / 缩放预设 / 翻转 / 透明度 / 复制 / 保存 / 关闭
- **搜索匹配**：`match_keyword` 在贴图管理窗口中按名称、时间、尺寸、状态、透明度匹配

---

## 配置变更

`Config` 新增字段：

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `workflow_auto_ocr` | `False` | 截图后自动 OCR 写剪贴板 |
| `workflow_auto_upload` | `False` | 截图后自动上传 |
| `workflow_copy_markdown` | `False` | 上传后复制 Markdown 链接 |
| `workflow_uploader` | `"local"` | 默认上传器 identifier |
| `github_owner` | `""` | GitHub 用户名/组织 |
| `github_repo` | `""` | 仓库名 |
| `github_branch` | `"main"` | 分支 |
| `github_path_prefix` | `"screenshots"` | 路径前缀 |

设置导入/导出已同步新字段。

---

## 打包变更

`QuickShot.spec` 新增 hidden imports：

- `quickshot.pipeline`、`quickshot.uploader`、`quickshot.secrets`
- `keyring`、`keyring.backends`、`keyring.backends.Windows`、`keyring.backends.fail`、`keyring.backends.null`
- `requests`

`build_config.py` 注释保留了 distutils 排除规则的特殊提示：keyring/pywin32-ctypes 的 PyInstaller hook 会 alias distutils，不能 exclude。

`requirements.txt` 新增：

- `keyring>=25.0.0`
- `requests>=2.32.0`

---

## 测试

新增 4 个测试文件，共 **75 个用例**：

| 文件 | 用例数 | 覆盖 |
|------|--------|------|
| `tests/test_pin.py` | 21 | PinWindow 缩放/翻转/锁定/置顶/透明度/位置/搜索 |
| `tests/test_uploader.py` | 11 | Uploader 接口、LocalArchive、Registry、链接格式化 |
| `tests/test_github_uploader.py` | 20 | GitHub API 调用、Token 管理、错误映射、路径生成 |
| `tests/test_pipeline.py` | 23 | Pipeline 流程、Step 启用判断、上下文传递、异常隔离 |

测试总数 **120 → 195**，全部通过。

---

## 文件变更清单

| 文件 | 变更 |
|------|------|
| `quickshot/uploader.py` | 新建：上传器抽象 + LocalArchive + GitHub |
| `quickshot/pipeline.py` | 新建：Pipeline 引擎和 3 个内置 Step |
| `quickshot/secrets.py` | 新建：keyring 封装 |
| `quickshot/pin.py` | 重写：贴图窗口扩展到工作台级别 |
| `quickshot/config.py` | 新增 4 个 workflow_* 和 4 个 github_* 字段 |
| `quickshot/settings.py` | 新增上传卡片：上传器选择、GitHub 配置、Token 管理 |
| `quickshot/overlay/_history.py` | 截图保存后触发 `run_post_capture_pipeline` |
| `quickshot/utils.py` | APP_VERSION 5.1.0 → 5.2.0 |
| `QuickShot.spec` | 新增 keyring/requests hidden imports |
| `requirements.txt` | 新增 keyring、requests |
| `tests/test_pin.py` | 新建，21 个测试 |
| `tests/test_uploader.py` | 新建，11 个测试 |
| `tests/test_github_uploader.py` | 新建，20 个测试 |
| `tests/test_pipeline.py` | 新建，23 个测试 |

---

## 打包

- 输出：`dist/QuickShot.exe`，约 110 MB（包含 keyring/requests 后体积上升约 5 MB）
- 打包工具：PyInstaller 6.20.0
