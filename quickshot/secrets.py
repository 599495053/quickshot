"""敏感信息存储。

封装 keyring 调用，把 token、密码等不应明文持久化的数据存到操作系统的安全凭据存储
（Windows 凭据管理器 / macOS Keychain / Linux Secret Service）。

所有调用都用 try/except 兜底：keyring 可能因为系统问题、后端未安装或权限不足失败，
失败时回退为返回空字符串/无操作，绝不抛到调用方。
"""

from __future__ import annotations

from typing import Optional

from .utils import APP_NAME, debug_log

SERVICE_GITHUB = f"{APP_NAME}.github"


def get_secret(service: str, account: str) -> str:
    """读取 keyring 中保存的密文；失败或不存在时返回空串。"""
    try:
        import keyring
        value = keyring.get_password(service, account)
        return value or ""
    except Exception as exc:  # noqa: BLE001
        debug_log(f"keyring read failed [{service}/{account}]: {exc}")
        return ""


def set_secret(service: str, account: str, value: str) -> bool:
    """写入 keyring；失败返回 False，调用方应提示用户。"""
    try:
        import keyring
        keyring.set_password(service, account, value)
        return True
    except Exception as exc:  # noqa: BLE001
        debug_log(f"keyring write failed [{service}/{account}]: {exc}")
        return False


def delete_secret(service: str, account: str) -> bool:
    """删除 keyring 中的密文；不存在或失败均返回 False，不抛异常。"""
    try:
        import keyring
        keyring.delete_password(service, account)
        return True
    except Exception as exc:  # noqa: BLE001
        debug_log(f"keyring delete failed [{service}/{account}]: {exc}")
        return False


def get_github_token(account: Optional[str] = None) -> str:
    """读取 GitHub PAT。account 通常用 'owner/repo' 区分多账户。"""
    return get_secret(SERVICE_GITHUB, account or "default")


def set_github_token(token: str, account: Optional[str] = None) -> bool:
    """保存 GitHub PAT。"""
    return set_secret(SERVICE_GITHUB, account or "default", token)


def delete_github_token(account: Optional[str] = None) -> bool:
    """删除 GitHub PAT。"""
    return delete_secret(SERVICE_GITHUB, account or "default")
