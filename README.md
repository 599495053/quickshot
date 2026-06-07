# QuickShot V5.3.0

QuickShot 是一款 Windows 截图工具，支持区域截图、当前窗口截图、标注、贴图、OCR、翻译、历史库、自动上传、复制、保存、托盘和设置管理。

标准源码入口是 `launcher.py`，PyInstaller 打包配置是 `QuickShot.spec`，安装包配置是 `QuickShot.iss`。

## 运行

```powershell
python launcher.py
```

也可以使用模块入口：

```powershell
python -m quickshot
```

如需在源码环境启用本地 RapidOCR 引擎和智能隐私自动识别：

```powershell
pip install -e .[ocr]
```

## 快捷键

### 全局快捷键

- `Ctrl+Shift+A`：区域截图
- `Ctrl+Shift+W`：当前窗口截图

### 编辑模式快捷键

- `A`：箭头
- `R`：矩形
- `U`：椭圆
- `D`：虚线框
- `B`：画笔
- `H`：高亮
- `T`：文字
- `N`：序号
- `M`：马赛克
- `L`：模糊打码
- `O`：OCR 识文
- `I`：取色器
- `G`：网格辅助
- `Tab`：切换上一个工具
- `方向键`：微调选区，按住 `Shift` 可每次移动 10px
- `Ctrl+C`：复制
- `Ctrl+S`：保存
- `Ctrl+Z`：撤销
- `Ctrl+Y`：重做
- `Enter`：完成
- `Esc`：取消

## 主要功能

### 截图

- 高清区域截图和当前窗口截图
- DPI 缩放适配和 HDR 支持
- 延迟截图，0-10 秒可配置
- 选区自动吸附窗口边缘
- 键盘微调选区位置和尺寸

### 标注

- 箭头、矩形、椭圆、虚线框、画笔、高亮
- 文字、序号、马赛克、模糊打码、取色器
- 智能隐私打码，安装 RapidOCR 可选组件后支持手机号、身份证、邮箱、银行卡等常见文本
- 标注颜色、线宽和样式预设

### OCR 与翻译

- 默认使用 Windows 系统 OCR；源码和定制构建可安装 RapidOCR 可选组件启用本地 OCR 引擎
- OCR 结果清洗、复制、导出 CSV、导出 Markdown 表格
- 提取数字、提取中文
- 翻译 OCR 结果
- 截图完成后可自动 OCR 并写入剪贴板

### 历史库

- 自动保存截图历史
- 搜索、收藏、批量删除
- 复制、导出、压缩包导出
- 从历史截图重新进入编辑

### 贴图

- 从截图创建贴图窗口
- 鼠标滚轮缩放，支持以光标位置为锚点
- 水平/垂直翻转
- 透明度调节
- 锁定、置顶、重命名
- 方向键微调位置
- 贴图管理窗口

### 截图后工作流

- 截图完成后自动上传到本地归档或 GitHub 仓库
- 上传成功后自动复制 Markdown 链接
- GitHub Personal Access Token 走系统凭据管理器保存

## 测试

提交前建议运行：

```powershell
python -m pyflakes quickshot launcher.py build_config.py
python -m compileall -q quickshot launcher.py build_config.py
python -m pytest -q
```

当前测试规模：

- `475 passed`
- `37 subtests passed`

## 打包

如果只是构建可执行文件：

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1 -SkipInstall -Clean
```

输出文件：

- `dist\QuickShot.exe`

## 发布

发布前先同步版本号：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\set-version.ps1 -Version 5.3.0
```

只检查版本号是否一致：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\set-version.ps1 -Version 5.3.0 -CheckOnly
```

一键发布构建：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean
```

发布脚本会自动执行：

- 版本号一致性检查
- `pyflakes`
- `compileall`
- `pytest`
- PyInstaller 打包
- Inno Setup 安装包构建
- exe 和安装包 SHA256 计算
- release manifest 生成

输出文件：

- `dist\QuickShot.exe`
- `installer_output\QuickShot-5.3.0-Setup.exe`
- `installer_output\QuickShot-5.3.0-release.txt`

可选的打包后冒烟测试：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipBuild -SkipInstaller -SmokeTest
```

### 可选代码签名

发布脚本支持用 Windows SignTool 对 `QuickShot.exe` 和安装包签名。没有证书时不要传 `-Sign`，现有构建流程不受影响。

使用证书存储中的代码签名证书：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean -Sign -CertificateThumbprint <thumbprint>
```

使用 `.pfx` / `.p12` 证书文件：

```powershell
$env:QUICKSHOT_SIGNING_PASSWORD = "<certificate-password>"
powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean -Sign -CertificateFile C:\path\to\certificate.pfx
```

可选参数：

- `-SignToolPath <path>`：指定 `signtool.exe` 路径；默认会尝试从 PATH 和 Windows SDK 中查找。
- `-TimestampUrl <url>`：指定 RFC 3161 时间戳服务；默认是 `http://timestamp.digicert.com`。
- `-CertificatePasswordEnvVar <name>`：指定读取证书密码的环境变量名；默认是 `QUICKSHOT_SIGNING_PASSWORD`。

## 安装包

安装包由 Inno Setup 6 构建，脚本为 `QuickShot.iss`。

默认安装行为：

- 不创建桌面快捷方式
- 不添加开机启动
- 支持简体中文安装界面
- 卸载时尝试关闭正在运行的 QuickShot

## 手动冒烟测试建议

1. 启动 `dist\QuickShot.exe`，确认托盘图标正常出现。
2. 按 `Ctrl+Shift+A` 框选区域，确认可以复制、保存、完成和取消。
3. 测试箭头、矩形、画笔、高亮、文字、马赛克、模糊、取色器。
4. 测试 OCR 识别、复制结果、翻译结果和结果窗口；安装 RapidOCR 可选组件时再测试智能隐私打码。
5. 测试历史库的搜索、复制、导出、删除和重新编辑。
6. 测试贴图的缩放、翻转、透明度、锁定、置顶和关闭。
7. 测试设置页保存、导入、导出和全局快捷键变更。
8. 确认截图画质和剪贴板格式正常。
