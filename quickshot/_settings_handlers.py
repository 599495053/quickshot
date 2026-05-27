"""SettingsHandlers — 设置回调：on_*_changed、快捷键、导入导出、帮助文本。"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from .hotkey_util import validate_hotkey


class SettingsHandlers:
    """SettingsWindow 的回调方法 mixin。"""

    # ── 通用设置回调 ──

    def choose_save_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择保存目录", self.config.save_dir)
        if folder:
            self.config.save_dir = folder
            self.config.save()
            self.save_dir_edit.setText(folder)

    def on_auto_copy_changed(self, state: int) -> None:
        self.config.auto_copy = state == self.Qt_CHECKED
        self._schedule_save()

    def on_save_mode_changed(self, index: int) -> None:
        mode = self.save_mode_combo.itemData(index)
        if mode:
            self.config.save_dir_mode = mode
            self._schedule_save()

    def on_save_format_changed(self, index: int) -> None:
        fmt = self.save_format_combo.itemData(index)
        if fmt:
            self.config.save_format = fmt
            self.jpeg_quality_spin.setEnabled(fmt in ("jpg", "jpeg"))
            self._schedule_save()

    def on_jpeg_quality_changed(self, value: int) -> None:
        self.config.jpeg_quality = value
        self._schedule_save()

    def on_notification_changed(self, state: int) -> None:
        self.config.show_notifications = state == self.Qt_CHECKED
        self._schedule_save()

    def on_hdr_color_accurate_changed(self, state: int) -> None:
        self.config.hdr_color_accurate = state == self.Qt_CHECKED
        self._schedule_save()

    def on_watermark_changed(self, text: str) -> None:
        self.config.watermark_text = text.strip()
        self._schedule_save()

    def on_delay_changed(self, value: int) -> None:
        self.config.delay_seconds = value
        self._schedule_save()

    def on_watermark_color_changed(self, index: int) -> None:
        color = self.watermark_color_combo.itemData(index)
        if color:
            self.config.watermark_color = color
            self._schedule_save()

    def on_grid_color_changed(self, index: int) -> None:
        color = self.grid_color_combo.itemData(index)
        if color:
            self.config.grid_color = color
            self._schedule_save()

    # ── 工作流回调 ──

    def on_workflow_ocr_changed(self, state: int) -> None:
        self.config.workflow_auto_ocr = state == self.Qt_CHECKED
        self._schedule_save()

    def on_workflow_upload_changed(self, state: int) -> None:
        self.config.workflow_auto_upload = state == self.Qt_CHECKED
        self._schedule_save()

    def on_workflow_md_changed(self, state: int) -> None:
        self.config.workflow_copy_markdown = state == self.Qt_CHECKED
        self._schedule_save()

    def on_uploader_changed(self, index: int) -> None:
        value = self.uploader_combo.itemData(index)
        if value:
            self.config.workflow_uploader = str(value)
            self._schedule_save()

    # ── GitHub 设置回调 ──

    def on_github_owner_changed(self) -> None:
        self.config.github_owner = self.github_owner_edit.text().strip()
        self._schedule_save()

    def on_github_repo_changed(self) -> None:
        self.config.github_repo = self.github_repo_edit.text().strip()
        self._schedule_save()

    def on_github_branch_changed(self) -> None:
        branch = self.github_branch_edit.text().strip() or "main"
        self.config.github_branch = branch
        self.github_branch_edit.setText(branch)
        self._schedule_save()

    def on_github_prefix_changed(self) -> None:
        prefix = self.github_prefix_edit.text().strip().strip("/") or "screenshots"
        self.config.github_path_prefix = prefix
        self.github_prefix_edit.setText(prefix)
        self._schedule_save()

    def _github_account_key(self) -> str:
        owner = self.config.github_owner.strip()
        repo = self.config.github_repo.strip()
        return f"{owner}/{repo}" if owner and repo else "default"

    def _load_github_token_into_field(self) -> bool:
        """检测 keyring 中是否已有 token，仅用占位符提示，不回显明文。"""
        from .secrets import get_github_token
        existing = get_github_token(self._github_account_key())
        if existing:
            self.github_token_edit.setPlaceholderText("Token 已保存（输入新值可覆盖）")
            return True
        return False

    def on_github_token_save(self) -> None:
        from .secrets import set_github_token
        token = self.github_token_edit.text().strip()
        if not token:
            QMessageBox.warning(self, "Token 为空", "请先输入 Personal Access Token。")
            return
        ok = set_github_token(token, self._github_account_key())
        if ok:
            self.github_token_edit.clear()
            self.github_token_edit.setPlaceholderText("Token 已保存（输入新值可覆盖）")
            QMessageBox.information(self, "保存成功", "Token 已保存到 Windows 凭据管理器。")
        else:
            QMessageBox.warning(self, "保存失败", "无法写入系统凭据存储，请检查 keyring 后端。")

    def on_github_token_clear(self) -> None:
        from .secrets import delete_github_token
        delete_github_token(self._github_account_key())
        self.github_token_edit.clear()
        self.github_token_edit.setPlaceholderText("Personal Access Token（保存到系统凭据，不存配置文件）")
        QMessageBox.information(self, "已清除", "Token 已从系统凭据中删除。")

    # ── 帮助文本 ──

    def _build_help_text(self) -> str:
        r = self.config.region_hotkey or "Ctrl+Shift+A"
        w = self.config.window_hotkey or "Ctrl+Shift+W"
        return f"""
        <style>
        table {{ border-collapse: collapse; width: 100%; }}
        td {{ padding: 4px 8px; }}
        .section {{ font-weight: bold; color: #1e3a5f; padding-top: 10px; }}
        .key {{ background: #f0f3f7; border: 1px solid #d7deea; border-radius: 4px;
               padding: 2px 8px; font-family: Consolas, monospace; font-size: 12px; }}
        .desc {{ color: #475569; }}
        </style>
        <div class="section">全局快捷键</div>
        <table>
        <tr><td class="key">{r}</td><td class="desc">区域截图</td></tr>
        <tr><td class="key">{w}</td><td class="desc">当前窗口截图</td></tr>
        </table>
        <div class="section">编辑模式（截图后）</div>
        <table>
        <tr><td class="key">A</td><td class="desc">箭头</td>
            <td class="key">R</td><td class="desc">矩形</td>
            <td class="key">U</td><td class="desc">椭圆</td></tr>
        <tr><td class="key">D</td><td class="desc">虚线框</td>
            <td class="key">B</td><td class="desc">画笔</td>
            <td class="key">H</td><td class="desc">高亮</td></tr>
        <tr><td class="key">T</td><td class="desc">文字</td>
            <td class="key">N</td><td class="desc">序号</td>
            <td class="key">M</td><td class="desc">马赛克</td></tr>
        <tr><td class="key">L</td><td class="desc">模糊打码</td>
            <td class="key">O</td><td class="desc">OCR 识文</td>
            <td class="key">G</td><td class="desc">网格辅助</td></tr>
        <tr><td class="key">Tab</td><td class="desc">切换上一工具</td>
            <td class="key">↑↓←→</td><td class="desc">微调选区</td>
            <td class="key">Shift+方向键</td><td class="desc">大步微调</td></tr>
        <tr><td class="key">Ctrl+C</td><td class="desc">复制到剪贴板</td>
            <td class="key">Ctrl+S</td><td class="desc">保存文件</td>
            <td class="key">Ctrl+Z</td><td class="desc">撤销标注</td></tr>
        <tr><td class="key">Ctrl+Y</td><td class="desc">重做标注</td>
            <td class="key">Enter</td><td class="desc">完成截图</td>
            <td class="key">Esc</td><td class="desc">取消</td></tr>
        </table>
        <div class="section">鼠标操作</div>
        <table>
        <tr><td class="key">拖动</td><td class="desc">移动选区 / 绘制标注</td></tr>
        <tr><td class="key">滚轮</td><td class="desc">预览区缩放（截图历史）</td></tr>
        <tr><td class="key">双击</td><td class="desc">完成截图</td></tr>
        <tr><td class="key">右键</td><td class="desc">取消截图</td></tr>
        </table>
        <div class="section">窗口快捷键（历史 / 贴图管理）</div>
        <table>
        <tr><td class="key">Ctrl+A</td><td class="desc">全选</td>
            <td class="key">Delete</td><td class="desc">删除 / 关闭</td></tr>
        <tr><td class="key">Enter</td><td class="desc">打开 / 贴图</td>
            <td class="key">Esc</td><td class="desc">关闭窗口</td></tr>
        </table>
        <div class="section">自定义设置</div>
        <table>
        <tr><td class="desc" colspan="2">可在上方设置网格辅助线颜色和水印颜色</td></tr>
        </table>
        """

    def update_help_text(self) -> None:
        self.hotkey_help_label.setText(self._build_help_text())

    # ── 快捷键回调 ──

    def on_region_hotkey_changed(self, combo: str) -> None:
        if combo == self.config.window_hotkey:
            QMessageBox.warning(self, "快捷键冲突", "该快捷键已用于窗口截图，请换一个。")
            self.region_hotkey_edit.set_hotkey(self.config.region_hotkey)
            return
        self.config.region_hotkey = combo
        self._schedule_save()
        self.hotkeys_changed.emit()
        self.update_help_text()

    def on_window_hotkey_changed(self, combo: str) -> None:
        if combo == self.config.region_hotkey:
            QMessageBox.warning(self, "快捷键冲突", "该快捷键已用于区域截图，请换一个。")
            self.window_hotkey_edit.set_hotkey(self.config.window_hotkey)
            return
        self.config.window_hotkey = combo
        self._schedule_save()
        self.hotkeys_changed.emit()
        self.update_help_text()

    def _check_hotkey_conflict(self, combo: str, exclude: str = "") -> bool:
        """检查快捷键是否与已有快捷键冲突，返回 True 表示有冲突。"""
        used = [self.config.region_hotkey, self.config.window_hotkey,
                self.config.history_hotkey, self.config.pin_hotkey]
        if exclude:
            used = [h for h in used if h != exclude]
        return combo in used

    def on_history_hotkey_changed(self, combo: str) -> None:
        if self._check_hotkey_conflict(combo, exclude=self.config.history_hotkey):
            QMessageBox.warning(self, "快捷键冲突", "该快捷键已被占用，请换一个。")
            self.history_hotkey_edit.set_hotkey(self.config.history_hotkey)
            return
        self.config.history_hotkey = combo
        self._schedule_save()
        self.hotkeys_changed.emit()

    def on_pin_hotkey_changed(self, combo: str) -> None:
        if self._check_hotkey_conflict(combo, exclude=self.config.pin_hotkey):
            QMessageBox.warning(self, "快捷键冲突", "该快捷键已被占用，请换一个。")
            self.pin_hotkey_edit.set_hotkey(self.config.pin_hotkey)
            return
        self.config.pin_hotkey = combo
        self._schedule_save()
        self.hotkeys_changed.emit()

    def on_ocr_hotkey_changed(self, combo: str) -> None:
        if self._check_hotkey_conflict(combo, exclude=self.config.ocr_hotkey):
            QMessageBox.warning(self, "快捷键冲突", "该快捷键已被占用，请换一个。")
            self.ocr_hotkey_edit.set_hotkey(self.config.ocr_hotkey)
            return
        self.config.ocr_hotkey = combo
        self._schedule_save()
        self.hotkeys_changed.emit()

    def reset_hotkey(self, which: str) -> None:
        defaults = {"region": "Ctrl+Shift+A", "window": "Ctrl+Shift+W", "history": "", "pin": "", "ocr": ""}
        default = defaults.get(which, "")
        if which == "region":
            self.region_hotkey_edit.set_hotkey(default)
            self.config.region_hotkey = default
        elif which == "window":
            self.window_hotkey_edit.set_hotkey(default)
            self.config.window_hotkey = default
        elif which == "history":
            self.history_hotkey_edit.set_hotkey(default)
            self.config.history_hotkey = default
        elif which == "pin":
            self.pin_hotkey_edit.set_hotkey(default)
            self.config.pin_hotkey = default
        elif which == "ocr":
            self.ocr_hotkey_edit.set_hotkey(default)
            self.config.ocr_hotkey = default
        self.config.save()
        self.hotkeys_changed.emit()
        self.update_help_text()

    # ── 历史库回调 ──

    def on_history_changed(self, state: int) -> None:
        self.config.auto_history = state == self.Qt_CHECKED
        self._schedule_save()

    def on_history_limit_changed(self, value: int) -> None:
        self.config.history_limit = int(value)
        self._schedule_save()
        removed = self.history_store.apply_history_limit()
        if removed > 0:
            QMessageBox.information(self, "历史库已整理", f"已按新上限清理 {removed} 张旧截图。")

    def on_startup_changed(self, state: int) -> None:
        from .main import StartupManager
        try:
            StartupManager.set_enabled(state == self.Qt_CHECKED)
        except Exception as exc:
            QMessageBox.warning(self, "设置失败", f"开机启动设置失败：{exc}")
            self.startup_check.blockSignals(True)
            self.startup_check.setChecked(StartupManager.is_enabled())
            self.startup_check.blockSignals(False)

    # ── 导入导出 ──

    _EXPORT_EXCLUDE = frozenset({
        "history_hotkey", "pin_hotkey", "ocr_hotkey",
        "delay_seconds", "save_dir_mode",
        "annotation_presets",
    })

    def export_settings(self) -> None:
        import json
        default_path = str(Path(self.config.ensure_save_dir()) / "quickshot_settings.json")
        filepath, _ = QFileDialog.getSaveFileName(self, "导出设置", default_path, "JSON 文件 (*.json)")
        if not filepath:
            return
        if not filepath.lower().endswith(".json"):
            filepath += ".json"
        try:
            data = {k: v for k, v in self.config.to_dict().items()
                    if k not in self._EXPORT_EXCLUDE}
            Path(filepath).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            QMessageBox.information(self, "导出成功", f"设置已导出到：\n{filepath}")
        except Exception as exc:
            QMessageBox.warning(self, "导出失败", f"导出设置失败：{exc}")

    def import_settings(self) -> None:
        import json
        filepath, _ = QFileDialog.getOpenFileName(self, "导入设置", "", "JSON 文件 (*.json)")
        if not filepath:
            return
        try:
            raw = Path(filepath).read_text(encoding="utf-8")
            data = json.loads(raw)
        except Exception as exc:
            QMessageBox.warning(self, "导入失败", f"读取设置文件失败：{exc}")
            return

        hotkey_fields = {"region_hotkey", "window_hotkey"}
        hotkey_data = {}
        for key in hotkey_fields:
            if key in data:
                valid, _ = validate_hotkey(str(data[key]))
                if valid:
                    hotkey_data[key] = str(data[key])

        bulk_data = {k: v for k, v in data.items() if k not in hotkey_fields}
        bulk_data.update(hotkey_data)
        self.config.import_from_dict(bulk_data)
        self.save_dir_edit.setText(self.config.save_dir)
        self.auto_copy_check.setChecked(self.config.auto_copy)
        self.workflow_ocr_check.setChecked(self.config.workflow_auto_ocr)
        self.workflow_upload_check.setChecked(self.config.workflow_auto_upload)
        self.workflow_md_check.setChecked(self.config.workflow_copy_markdown)
        for i in range(self.uploader_combo.count()):
            if self.uploader_combo.itemData(i) == self.config.workflow_uploader:
                self.uploader_combo.setCurrentIndex(i)
                break
        self.github_owner_edit.setText(self.config.github_owner)
        self.github_repo_edit.setText(self.config.github_repo)
        self.github_branch_edit.setText(self.config.github_branch)
        self.github_prefix_edit.setText(self.config.github_path_prefix)
        self.notification_check.setChecked(self.config.show_notifications)
        self.hdr_accurate_check.setChecked(self.config.hdr_color_accurate)
        self.history_check.setChecked(self.config.auto_history)
        self.history_limit_spin.setValue(self.config.history_limit)
        self.watermark_edit.setText(self.config.watermark_text)
        for i in range(self.watermark_color_combo.count()):
            if self.watermark_color_combo.itemData(i) == self.config.watermark_color:
                self.watermark_color_combo.setCurrentIndex(i)
                break
        for i in range(self.grid_color_combo.count()):
            if self.grid_color_combo.itemData(i) == self.config.grid_color:
                self.grid_color_combo.setCurrentIndex(i)
                break
        self.region_hotkey_edit.set_hotkey(self.config.region_hotkey)
        self.window_hotkey_edit.set_hotkey(self.config.window_hotkey)
        self.hotkeys_changed.emit()
        self.update_help_text()
        QMessageBox.information(self, "导入成功", "设置已导入并生效。")
