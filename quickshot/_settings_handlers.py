"""SettingsHandlers — 设置回调：on_*_changed、快捷键、导入导出、帮助文本。"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from .hotkey_util import validate_hotkey
from .workflow_presets import (
    WORKFLOW_PRESET_DEFAULT,
    apply_workflow_preset,
    normalize_workflow_preset,
    reset_workflow_defaults,
    workflow_capture_hint,
    workflow_preset_label,
)


class SettingsHandlers:
    """SettingsWindow 的回调方法 mixin。"""

    @staticmethod
    def _set_combo_data(combo, value) -> None:
        """将 QComboBox 设置为 itemData 匹配 value 的项。"""
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return

    def _set_combo_data_silently(self, combo, value) -> None:
        combo.blockSignals(True)
        try:
            self._set_combo_data(combo, value)
        finally:
            combo.blockSignals(False)

    @staticmethod
    def _set_check_silently(checkbox, checked: bool) -> None:
        checkbox.blockSignals(True)
        try:
            checkbox.setChecked(bool(checked))
        finally:
            checkbox.blockSignals(False)

    # ── 通用设置回调 ──

    def choose_save_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择保存目录", self.config.save_dir)
        if folder:
            self.config.save_dir = folder
            self.config.save()
            self.save_dir_edit.setText(folder)

    def on_auto_copy_changed(self, state: int) -> None:
        self.config.auto_copy = state == self.Qt_CHECKED
        self._mark_workflow_custom()
        self._refresh_workflow_summary()
        self._schedule_save()
        self.workflow_changed.emit()

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

    @staticmethod
    def _screenshot_dim_preset_values(style: str) -> tuple[int, int]:
        presets = {
            "system": (132, 16),
            "clear": (104, 12),
            "deep": (172, 20),
        }
        return presets.get(style, presets["system"])

    def _refresh_screenshot_dim_controls(self) -> None:
        combo = getattr(self, "screenshot_dim_style_combo", None)
        alpha_spin = getattr(self, "screenshot_dim_alpha_spin", None)
        blur_spin = getattr(self, "screenshot_dim_blur_spin", None)
        if combo is None or alpha_spin is None or blur_spin is None:
            return
        style = getattr(self.config, "screenshot_dim_style", "system")
        if style != "custom":
            alpha, blur = self._screenshot_dim_preset_values(style)
        else:
            alpha = int(getattr(self.config, "screenshot_dim_alpha", 132))
            blur = int(getattr(self.config, "screenshot_dim_blur", 16))

        combo.blockSignals(True)
        alpha_spin.blockSignals(True)
        blur_spin.blockSignals(True)
        try:
            self._set_combo_data(combo, style)
            alpha_spin.setValue(alpha)
            blur_spin.setValue(blur)
            alpha_spin.setEnabled(style == "custom")
            blur_spin.setEnabled(style == "custom")
        finally:
            blur_spin.blockSignals(False)
            alpha_spin.blockSignals(False)
            combo.blockSignals(False)

    def on_screenshot_dim_style_changed(self, index: int) -> None:
        style = self.screenshot_dim_style_combo.itemData(index) or "system"
        self.config.screenshot_dim_style = style
        if style != "custom":
            alpha, blur = self._screenshot_dim_preset_values(style)
            self.config.screenshot_dim_alpha = alpha
            self.config.screenshot_dim_blur = blur
        self._refresh_screenshot_dim_controls()
        self._schedule_save()

    def on_screenshot_dim_alpha_changed(self, value: int) -> None:
        self.config.screenshot_dim_style = "custom"
        self.config.screenshot_dim_alpha = int(value)
        self._refresh_screenshot_dim_controls()
        self._schedule_save()

    def on_screenshot_dim_blur_changed(self, value: int) -> None:
        self.config.screenshot_dim_style = "custom"
        self.config.screenshot_dim_blur = int(value)
        self._refresh_screenshot_dim_controls()
        self._schedule_save()

    def on_snap_changed(self, state: int) -> None:
        self.config.snap_to_windows = state == self.Qt_CHECKED
        self._schedule_save()

    def on_snap_threshold_changed(self, value: int) -> None:
        self.config.snap_threshold_px = value
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

    def _workflow_summary_text(self) -> str:
        preset = normalize_workflow_preset(getattr(self.config, "workflow_preset", WORKFLOW_PRESET_DEFAULT))
        return f"当前：{workflow_preset_label(preset)}；{workflow_capture_hint(self.config)}"

    def _refresh_workflow_summary(self) -> None:
        label = getattr(self, "workflow_summary_label", None)
        if label is not None:
            label.setText(self._workflow_summary_text())

    def _refresh_workflow_controls(self) -> None:
        self._syncing_workflow_controls = True
        try:
            self._set_combo_data_silently(
                self.workflow_preset_combo,
                normalize_workflow_preset(getattr(self.config, "workflow_preset", WORKFLOW_PRESET_DEFAULT)),
            )
            self._set_check_silently(self.auto_copy_check, getattr(self.config, "auto_copy", True))
            self._set_check_silently(
                self.workflow_auto_save_check,
                getattr(self.config, "workflow_auto_save", False),
            )
            self._set_check_silently(self.workflow_ocr_check, getattr(self.config, "workflow_auto_ocr", False))
            self._set_check_silently(
                self.workflow_upload_check,
                getattr(self.config, "workflow_auto_upload", False),
            )
            self._set_check_silently(
                self.workflow_md_check,
                getattr(self.config, "workflow_copy_markdown", False),
            )
            self._set_check_silently(
                self.workflow_privacy_check,
                getattr(self.config, "workflow_privacy_first", False),
            )
            self._set_combo_data_silently(self.uploader_combo, getattr(self.config, "workflow_uploader", "local"))
            self._refresh_workflow_summary()
        finally:
            self._syncing_workflow_controls = False

    def _mark_workflow_custom(self) -> None:
        if getattr(self, "_syncing_workflow_controls", False):
            return
        if getattr(self.config, "workflow_preset", WORKFLOW_PRESET_DEFAULT) == WORKFLOW_PRESET_DEFAULT:
            return
        self.config.workflow_preset = WORKFLOW_PRESET_DEFAULT
        combo = getattr(self, "workflow_preset_combo", None)
        if combo is not None:
            self._set_combo_data_silently(combo, WORKFLOW_PRESET_DEFAULT)

    def on_workflow_preset_changed(self, index: int) -> None:
        preset = normalize_workflow_preset(self.workflow_preset_combo.itemData(index))
        self.config.workflow_preset = preset
        if preset != WORKFLOW_PRESET_DEFAULT:
            apply_workflow_preset(self.config, preset)
            self._refresh_workflow_controls()
        else:
            self._refresh_workflow_summary()
        self._schedule_save()
        self.workflow_changed.emit()

    def on_workflow_auto_save_changed(self, state: int) -> None:
        self.config.workflow_auto_save = state == self.Qt_CHECKED
        self._mark_workflow_custom()
        self._refresh_workflow_summary()
        self._schedule_save()
        self.workflow_changed.emit()

    def on_workflow_ocr_changed(self, state: int) -> None:
        self.config.workflow_auto_ocr = state == self.Qt_CHECKED
        self._mark_workflow_custom()
        self._refresh_workflow_summary()
        self._schedule_save()
        self.workflow_changed.emit()

    def on_workflow_upload_changed(self, state: int) -> None:
        self.config.workflow_auto_upload = state == self.Qt_CHECKED
        self._mark_workflow_custom()
        self._refresh_workflow_summary()
        self._schedule_save()
        self.workflow_changed.emit()

    def on_workflow_md_changed(self, state: int) -> None:
        self.config.workflow_copy_markdown = state == self.Qt_CHECKED
        self._mark_workflow_custom()
        self._refresh_workflow_summary()
        self._schedule_save()
        self.workflow_changed.emit()

    def on_workflow_privacy_changed(self, state: int) -> None:
        self.config.workflow_privacy_first = state == self.Qt_CHECKED
        self._mark_workflow_custom()
        self._refresh_workflow_summary()
        self._schedule_save()
        self.workflow_changed.emit()

    def on_uploader_changed(self, index: int) -> None:
        value = self.uploader_combo.itemData(index)
        if value:
            self.config.workflow_uploader = str(value)
            self._refresh_github_status()
            self._schedule_save()
            self.workflow_changed.emit()

    def restore_workflow_defaults(self) -> None:
        reset_workflow_defaults(self.config)
        self._refresh_workflow_controls()
        self._schedule_save()
        self.workflow_changed.emit()

    # ── GitHub 设置回调 ──

    def on_github_owner_changed(self) -> None:
        self.config.github_owner = self.github_owner_edit.text().strip()
        self._refresh_github_token_placeholder()
        self._refresh_github_status()
        self._schedule_save()

    def on_github_repo_changed(self) -> None:
        self.config.github_repo = self.github_repo_edit.text().strip()
        self._refresh_github_token_placeholder()
        self._refresh_github_status()
        self._schedule_save()

    def on_github_branch_changed(self) -> None:
        branch = self.github_branch_edit.text().strip() or "main"
        self.config.github_branch = branch
        self.github_branch_edit.setText(branch)
        self._refresh_github_status()
        self._schedule_save()

    def on_github_prefix_changed(self) -> None:
        prefix = self.github_prefix_edit.text().strip().strip("/") or "screenshots"
        self.config.github_path_prefix = prefix
        self.github_prefix_edit.setText(prefix)
        self._refresh_github_status()
        self._schedule_save()

    def _github_account_key(self) -> str:
        owner = self.config.github_owner.strip()
        repo = self.config.github_repo.strip()
        return f"{owner}/{repo}" if owner and repo else "default"

    def _github_token_present(self) -> bool:
        from .secrets import get_github_token
        return bool(get_github_token(self._github_account_key()))

    def _refresh_github_token_placeholder(self) -> bool:
        """检测 keyring 中是否已有 token，仅用占位符提示，不回显明文。"""
        existing = self._github_token_present()
        if existing:
            self.github_token_edit.setPlaceholderText("Token 已保存（输入新值可覆盖）")
        else:
            self.github_token_edit.setPlaceholderText("Personal Access Token（保存到系统凭据，不存配置文件）")
        self._github_token_loaded = existing
        return existing

    def _load_github_token_into_field(self) -> bool:
        return self._refresh_github_token_placeholder()

    def _github_status_text(self) -> str:
        from .uploader import GitHubUploader
        token_present = self._github_token_present()
        uploader = GitHubUploader(
            owner=getattr(self.config, "github_owner", ""),
            repo=getattr(self.config, "github_repo", ""),
            branch=getattr(self.config, "github_branch", "main"),
            path_prefix=getattr(self.config, "github_path_prefix", "screenshots"),
            token_provider=lambda: "configured-token" if token_present else "",
        )
        selected = getattr(self.config, "workflow_uploader", "local") == "github"
        if uploader.is_configured():
            destination = (
                f"{uploader.owner}/{uploader.repo}@{uploader.branch}/"
                f"{uploader.path_prefix}"
            )
            if selected:
                return f"GitHub 上传器已就绪：截图会上传到 {destination}。"
            return "GitHub 上传器已配置；当前上传器不是 GitHub，发布模式会使用当前选择的上传器。"

        missing = "、".join(uploader.missing_config_items())
        if selected:
            return (
                f"GitHub 上传器未就绪：缺少：{missing}。"
                "发布模式会先完成本地保存，但上传和 Markdown 链接会失败。"
            )
        return f"当前未选择 GitHub；若要上传到 GitHub，还需补齐：{missing}。"

    def _refresh_github_status(self) -> None:
        label = getattr(self, "github_status_label", None)
        if label is not None:
            label.setText(self._github_status_text())

    def on_github_token_save(self) -> None:
        from .secrets import set_github_token
        token = self.github_token_edit.text().strip()
        if not token:
            QMessageBox.warning(self, "Token 为空", "请先输入 Personal Access Token。")
            return
        ok = set_github_token(token, self._github_account_key())
        if ok:
            self.github_token_edit.clear()
            self._refresh_github_token_placeholder()
            self._refresh_github_status()
            QMessageBox.information(self, "保存成功", "Token 已保存到 Windows 凭据管理器。")
        else:
            QMessageBox.warning(self, "保存失败", "无法写入系统凭据存储，请检查 keyring 后端。")

    def on_github_token_clear(self) -> None:
        from .secrets import delete_github_token
        delete_github_token(self._github_account_key())
        self.github_token_edit.clear()
        self._refresh_github_token_placeholder()
        self._refresh_github_status()
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
                self.config.history_hotkey, self.config.pin_hotkey,
                self.config.ocr_hotkey]
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
        from .config import StartupManager
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
        self._refresh_workflow_controls()
        self.github_owner_edit.setText(self.config.github_owner)
        self.github_repo_edit.setText(self.config.github_repo)
        self.github_branch_edit.setText(self.config.github_branch)
        self.github_prefix_edit.setText(self.config.github_path_prefix)
        self._refresh_github_token_placeholder()
        self._refresh_github_status()
        self.notification_check.setChecked(self.config.show_notifications)
        self.hdr_accurate_check.setChecked(self.config.hdr_color_accurate)
        self._refresh_screenshot_dim_controls()
        self.snap_check.setChecked(self.config.snap_to_windows)
        self.snap_threshold_spin.setValue(self.config.snap_threshold_px)
        self.history_check.setChecked(self.config.auto_history)
        self.history_limit_spin.setValue(self.config.history_limit)
        self.watermark_edit.setText(self.config.watermark_text)
        self._set_combo_data(self.watermark_color_combo, self.config.watermark_color)
        self._set_combo_data(self.grid_color_combo, self.config.grid_color)
        self.region_hotkey_edit.set_hotkey(self.config.region_hotkey)
        self.window_hotkey_edit.set_hotkey(self.config.window_hotkey)
        self.history_hotkey_edit.set_hotkey(self.config.history_hotkey)
        self.pin_hotkey_edit.set_hotkey(self.config.pin_hotkey)
        self.ocr_hotkey_edit.set_hotkey(self.config.ocr_hotkey)
        self.hotkeys_changed.emit()
        self.update_help_text()
        QMessageBox.information(self, "导入成功", "设置已导入并生效。")

    def copy_diagnostic_info(self) -> None:
        from .diagnostics import build_diagnostic_report
        from .utils import copy_text_to_clipboard, debug_log

        try:
            copy_text_to_clipboard(build_diagnostic_report(self.config))
            QMessageBox.information(self, "已复制", "诊断信息已复制到剪贴板。反馈问题时请快速检查后粘贴。")
        except Exception as exc:
            debug_log(f"copy diagnostic info failed: {exc}")
            QMessageBox.warning(self, "复制失败", f"无法复制诊断信息：{exc}")
