# QuickShot V5.3.0

QuickShot 是一款 Windows 截图工具，包含区域截图、当前窗口截图、标注、贴图、OCR、历史库、上传、复制、保存、托盘和设置功能。

标准入口是 `launcher.py`，打包配置是 `QuickShot.spec`。

## 运行

```bash
python launcher.py
```

也可以使用模块入口：

```bash
python -m quickshot
```

## 快捷键

### 全局快捷键
- Ctrl + Shift + A：区域截图
- Ctrl + Shift + W：当前窗口截图

### 编辑模式快捷键
- A：箭头 | R：矩形 | U：椭圆 | D：虚线框
- B：画笔 | H：高亮 | T：文字 | N：序号
- M：马赛克 | L：模糊打码 | O：OCR 识文 | I：取色器
- G：网格辅助 | Tab：切换上一工具 | 方向键：微调选区
- Ctrl + C：复制 | Ctrl + S：保存 | Ctrl + Z：撤销 | Ctrl + Y：重做
- Enter：完成 | Esc：取消

## 主要功能

### 截图功能
- 高清区域截图和窗口截图
- DPI 缩放适配和 HDR 支持
- 延迟截图（0-10 秒可配置）
- 键盘微调选区（方向键 1px，Shift+10px）

### 标注工具
- 箭头、矩形、椭圆、虚线框、画笔、高亮
- 文字、序号、马赛克、模糊打码
- 智能隐私打码（手机号、身份证、邮箱、银行卡）
- 标注颜色和线宽快速切换
- 图形填充模式和样式预设

### 编辑效率
- 取色器（I 键，点击取色并自动应用到标注颜色）
- 网格辅助（G 键，三分法构图）
- 工具快速切换（Tab 键）
- 多格式保存（PNG / JPEG / WebP / BMP）
- 键盘微调选区（方向键 1px，Shift+10px）

### OCR 功能
- 文字识别（RapidOCR + 系统 OCR 双引擎）
- 结果自动清洗和深度清洗
- 导出 CSV、Markdown 表格
- 提取数字、提取中文

### 历史管理
- 自动截图历史库
- 标签和收藏筛选
- 批量操作和导出压缩包
- 一键回到编辑态

### 截图后工作流（v5.2.0）
- 截图完成后自动上传（本地存档 / GitHub 仓库）
- 上传成功后自动复制 Markdown 链接
- 截图完成后自动 OCR 写剪贴板
- GitHub Personal Access Token 走系统凭据管理器（keyring）

### 贴图增强（v5.2.0）
- 滚轮以光标位置为锚点缩放（0.12x ~ 4.0x）
- 水平/垂直翻转
- 透明度调节（35% ~ 100%）
- 锁定、置顶、重命名
- 方向键微调位置（1px / Shift+10px）
- 完整右键菜单

### 其他功能
- 贴图和贴图管理
- 托盘图标和设置窗口
- 开机启动
- 自定义网格和水印颜色

## 打包

推荐使用一键构建脚本：

```powershell
.\build.ps1
```

如果依赖已经安装，只想重新打包：

```powershell
.\build.ps1 -SkipInstall
```

也可以直接调用 PyInstaller：

```bash
pyinstaller QuickShot.spec
```

生成的可执行文件位于 `dist/QuickShot.exe`。

## 自动化检查

提交前可以跑一遍静态扫描和测试套件：

```bash
python -m pyflakes quickshot launcher.py build_config.py
python -m unittest discover tests
```

`tests/` 下共 195 个用例，覆盖 config、ocr、overlay、hotkey、history、settings、utils、pin、uploader、github_uploader、pipeline 等模块。`tests/test_overlay_smoke.py` 覆盖所有标注工具的 `select_tool` 和 paint 路径，能在源头拦住"漏导入符号导致 paintEvent 闪退"这类低级错误。

## 建议测试

1. Ctrl + Shift + A 后框选区域
2. 悬停工具栏按钮，检查提示是否正常
3. 测试复制、保存、完成、取消
4. 测试箭头、矩形框、画笔、高亮、文字、马赛克、颜色、线宽、清空、撤销
5. 测试 OCR 识别、复制结果和结果窗口
6. 测试 OCR 整理空行、合并一行、转 Markdown 表格
7. 测试截图历史库的搜索、复制、导出、删除
8. 测试贴图：滚轮缩放、翻转、透明度、锁定、置顶、Esc 关闭
9. 测试贴图管理，确认可以取消置顶并再次置顶
10. 测试设置 → 上传卡片：填写 GitHub owner/repo，保存 Token，开启「截图完成后自动上传」+「上传后复制 Markdown」
11. 测试移动选区和调整选区大小
12. 确认截图画质没有变化
