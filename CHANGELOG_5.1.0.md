# QuickShot v5.1.0 更新日志

## 发布日期：2026-05-25

---

## 新功能

### 颜色自定义
- 网格辅助线颜色可自定义，提供 7 种预设（白色半透、白色高亮、白色不透明、黄色半透、红色半透、蓝色半透、黑色半透）
- 水印颜色可自定义，提供 7 种预设（白色半透、白色高亮、白色不透明、黑色半透、黑色高亮、红色半透、蓝色半透）
- 颜色配置随设置导入/导出

### 工具栏图标
- 新增 5 个 SVG 图标：模糊全部、填充、网格、尺寸锁定、复用选区
- 优化 3 个图标：模糊、高亮、箭头

---

## 体验优化

### 标注拖拽手感
- 鼠标拖到选区框外时标注不再卡住，自动延伸到选区边缘
- 支持工具：箭头、矩形、椭圆、画笔、高亮、文字拖拽
- 起始点击仍需在选区内，仅拖拽过程允许超出

### 网格辅助线
- 选区调整（拖动/缩放）时网格始终可见，不再闪烁消失

### 设置界面
- 修复快捷键帮助列表中的重复项
- 新增自定义设置提示区域

---

## 性能优化

### 冷启动优化
- `concurrent.futures` 延迟导入（节省 ~57ms）
- `shutil`、`subprocess`、`tempfile` 延迟导入（节省 ~25ms）
- OCR 线程池改为懒加载

---

## 打包修复

### RapidOCR 模块缺失
- 补全 `ch_ppocr_v3_det`、`ch_ppocr_v3_rec`、`ch_ppocr_v2_cls` 子模块 hidden imports
- 更新 `collect_data_files` 包含 `**/*.py` 和 `**/*.yaml`

---

## 测试

- 新增 `test_overlay_features.py`：23 个测试（网格、尺寸锁定、工具切换、复用选区、工具栏按钮、样式面板）
- 新增 `test_settings.py`：6 个测试（设置窗口初始化、颜色配置）
- 新增 `test_utils.py`：4 个测试（常量、日志、图标加载）
- `test_config.py` 新增 4 个配置往返测试
- **总计 120 个测试全部通过**

---

## 文件变更清单

| 文件 | 变更内容 |
|------|----------|
| `quickshot/overlay/coords.py` | `widget_to_image` 新增 `clamped` 参数 |
| `quickshot/overlay/widget.py` | 标注/文字拖拽使用 `clamped=True`；网格绘制位置调整 |
| `quickshot/overlay/_paint.py` | 网格颜色使用配置值 |
| `quickshot/overlay/_history.py` | 水印颜色使用配置值 |
| `quickshot/overlay/_selection.py` | 修复 `FloatingSnipOverlay` 引用 |
| `quickshot/config.py` | 新增 `grid_color`、`watermark_color` |
| `quickshot/settings.py` | 颜色选择器、快捷键修复、导入导出更新 |
| `quickshot/ocr.py` | 延迟导入优化 |
| `quickshot/utils.py` | 版本号 → 5.1.0 |
| `QuickShot.spec` | RapidOCR hidden imports |
| `assets/toolbar/*.svg` | 8 个新增/优化图标 |
| `tests/test_overlay_features.py` | 新建，23 个测试 |
| `tests/test_settings.py` | 新建，6 个测试 |
| `tests/test_utils.py` | 新建，4 个测试 |
| `tests/test_config.py` | 新增 4 个测试 |
| `README.md` | 更新至 v5.1.0 |
| `COMPLETION_CHECKLIST.md` | 同步更新 |
