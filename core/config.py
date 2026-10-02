"""Unified config: one flat `.env` file, shared by the root app and Sesame.

No JSON config file, no keyring. Everything is a flat string key read via
os.getenv, same pattern as the root app's original `load_config()`.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv, set_key

APP_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = APP_DIR / ".env"

_MIGRATED_MARKER = "SESAME_CONFIG_MIGRATED"

# key -> default value (always strings; callers parse ints/bools/JSON as needed)
_DEFAULTS: dict[str, str] = {
    # -- VPN (shared) --
    "VPN_SERVER": "",
    "VPN_USER": "",
    "VPN_PASS": "",
    "MAC_SUDO_PASS": "",
    "TRUSTED_CERT": "",

    # -- VPN (openconnect backend - the only Windows VPN backend) --
    "VPN_SERVERCERT": "",
    "OPENCONNECT_EXE": "",
    "VPNC_SCRIPT": "",
    "OPENFORTIVPN_BIN": "",
    "VPN_EXTRA_ARGS": "",
    "VPN_CONNECT_TIMEOUT_SECONDS": "60",

    # -- Mail / OTP (shared) --
    "IMAP_SERVER": "",
    "IMAP_PORT": "993",
    "IMAP_USER": "",
    "IMAP_PASS": "",
    "MAIL_TIMEOUT": "60",
    "MAIL_FROM_CONTAINS": "",
    "MAIL_SUBJECT_CONTAINS": "AuthCode:",
    "MAIL_CODE_REGEX": r"(?<!\d)(\d{6})(?!\d)",
    "MAIL_LOOKBACK_SECONDS": "90",
    "MAIL_USE_SSL": "true",
    "MAIL_MAILBOX": "INBOX",
    "MAIL_POLL_SECONDS": "5",
    "MAIL_POLL_TIMEOUT_SECONDS": "120",

    # -- Keep-alive (root app) --
    "PING_TARGET": "off",
    "PING_INTERVAL": "15",
    "MAX_PING_FAILS": "3",
    "RECONNECT_DELAY": "15",

    # -- UI / tray notifications (Sesame) --
    "UI_CONNECTED_TOAST_TITLE": "Sesame",
    "UI_CONNECTED_TOAST_BODY": "Sesame connected!",
    "UI_DISCONNECTED_TOAST_BODY": "Sesame disconnected.",
    "UI_STATUS_POLL_SECONDS": "5",
    "UI_START_MINIMIZED": "false",
}


def load() -> dict:
    """Load the flat config dict from `.env`, migrating a legacy Sesame
    `config.json` + keyring install into it the first time this runs."""
    load_dotenv(ENV_PATH, override=True)
    _migrate_legacy_sesame_config()
    return {key: os.getenv(key, default) for key, default in _DEFAULTS.items()}


def save(cfg: dict) -> None:
    """Persist every known key present in `cfg` back to `.env`."""
    if not ENV_PATH.exists():
        ENV_PATH.touch()
    for key in _DEFAULTS:
        if key not in cfg:
            continue
        val = cfg[key]
        if isinstance(val, bool):
            val = "true" if val else "false"
        set_key(str(ENV_PATH), key, "" if val is None else str(val))


# ------------------------------------------------------------- helpers ------
def as_bool(cfg: dict, key: str, default: bool = False) -> bool:
    v = cfg.get(key)
    if v is None or v == "":
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def use_ssl(cfg: dict) -> bool:
    return as_bool(cfg, "MAIL_USE_SSL", True)


def start_minimized(cfg: dict) -> bool:
    return as_bool(cfg, "UI_START_MINIMIZED", False)


def extra_args(cfg: dict) -> list[str]:
    import shlex
    raw = (cfg.get("VPN_EXTRA_ARGS") or "").strip()
    return shlex.split(raw) if raw else []


def split_server(cfg: dict) -> tuple[str, int]:
    """VPN_SERVER is a single 'host:port' string; split it for backends/UI
    that need the parts separately."""
    raw = (cfg.get("VPN_SERVER") or "").strip()
    raw = raw.replace("https://", "").replace("http://", "")
    if ":" in raw:
        host, _, port = raw.partition(":")
        try:
            return host, int(port)
        except ValueError:
            return host, 443
    return raw, 443


def join_server(host: str, port: int) -> str:
    host = (host or "").strip()
    return f"{host}:{port}" if host else ""


def vpn_username(cfg: dict) -> str:
    """VPN username: falls back to the part before '@' in the mail address
    if VPN_USER is not set separately."""
    u = (cfg.get("VPN_USER") or "").strip()
    if u:
        return u
    email = cfg.get("IMAP_USER") or ""
    return email.split("@")[0] if "@" in email else email


def mail_ready(cfg: dict) -> bool:
    return bool(cfg.get("IMAP_SERVER")) and bool(cfg.get("IMAP_USER")) and bool(cfg.get("IMAP_PASS"))


def vpn_ready(cfg: dict) -> bool:
    """For the openconnect backend: gateway + VPN username/password + mail OTP ready?"""
    host, _ = split_server(cfg)
    if not host:
        return False
    if not (vpn_username(cfg) and cfg.get("VPN_PASS")):
        return False
    return mail_ready(cfg)


# --------------------------------------------------------- one-time migration --
def _migrate_legacy_sesame_config() -> None:
    """If a pre-unification Sesame install (windows/config.json + keyring
    secrets) is found and hasn't been migrated yet, copy its settings into
    the shared .env (filling only keys the user hasn't already set) and
    leave config.json in place, untouched but superseded. Settings that only
    made sense for the deleted FortiClient GUI-automation backend (window
    position/size, calibration points) are dropped, not migrated."""
    if os.getenv(_MIGRATED_MARKER):
        return
    legacy_path = APP_DIR / "windows" / "config.json"
    if not legacy_path.exists():
        _mark_migrated()  # nothing to migrate; don't re-check config.json every load()
        return
    try:
        with open(legacy_path, "r", encoding="utf-8") as f:
            legacy = json.load(f)
    except Exception:
        _mark_migrated()
        return

    v = legacy.get("vpn", {}) or {}
    m = legacy.get("mail", {}) or {}
    ui = legacy.get("ui", {}) or {}

    mapping: dict[str, str] = {}

    gw = (v.get("gateway") or "").strip()
    if gw:
        mapping["VPN_SERVER"] = join_server(gw, v.get("gateway_port") or 443)
    vu = (m.get("vpn_username") or "").strip()  # legacy schema nests this under "mail"
    if vu:
        mapping["VPN_USER"] = vu
    if v.get("servercert"):
        mapping["VPN_SERVERCERT"] = str(v["servercert"])
    if v.get("openconnect_exe"):
        mapping["OPENCONNECT_EXE"] = str(v["openconnect_exe"])
    if v.get("vpnc_script"):
        mapping["VPNC_SCRIPT"] = str(v["vpnc_script"])
    if v.get("extra_args"):
        mapping["VPN_EXTRA_ARGS"] = " ".join(str(a) for a in v["extra_args"])
    if v.get("connect_timeout_seconds") is not None:
        mapping["VPN_CONNECT_TIMEOUT_SECONDS"] = str(v["connect_timeout_seconds"])
    # legacy "backend"/"forticlient_exe"/"window_pos"/"window_size"/"calibration"
    # fields (FortiClient GUI automation) have no replacement - that backend is gone.

    if m.get("imap_host"):
        mapping["IMAP_SERVER"] = str(m["imap_host"])
    if m.get("imap_port") is not None:
        mapping["IMAP_PORT"] = str(m["imap_port"])
    if m.get("username"):
        mapping["IMAP_USER"] = str(m["username"])
    if m.get("from_contains"):
        mapping["MAIL_FROM_CONTAINS"] = str(m["from_contains"])
    if m.get("subject_contains"):
        mapping["MAIL_SUBJECT_CONTAINS"] = str(m["subject_contains"])
    if m.get("code_regex"):
        mapping["MAIL_CODE_REGEX"] = str(m["code_regex"])
    if m.get("lookback_seconds") is not None:
        mapping["MAIL_LOOKBACK_SECONDS"] = str(m["lookback_seconds"])
    if "use_ssl" in m:
        mapping["MAIL_USE_SSL"] = "true" if m["use_ssl"] else "false"
    if m.get("mailbox"):
        mapping["MAIL_MAILBOX"] = str(m["mailbox"])
    if m.get("poll_seconds") is not None:
        mapping["MAIL_POLL_SECONDS"] = str(m["poll_seconds"])
    if m.get("poll_timeout_seconds") is not None:
        mapping["MAIL_POLL_TIMEOUT_SECONDS"] = str(m["poll_timeout_seconds"])

    if ui.get("connected_toast_title"):
        mapping["UI_CONNECTED_TOAST_TITLE"] = str(ui["connected_toast_title"])
    if ui.get("connected_toast_body"):
        mapping["UI_CONNECTED_TOAST_BODY"] = str(ui["connected_toast_body"])
    if ui.get("disconnected_toast_body"):
        mapping["UI_DISCONNECTED_TOAST_BODY"] = str(ui["disconnected_toast_body"])
    if ui.get("status_poll_seconds") is not None:
        mapping["UI_STATUS_POLL_SECONDS"] = str(ui["status_poll_seconds"])
    if "start_minimized" in ui:
        mapping["UI_START_MINIMIZED"] = "true" if ui["start_minimized"] else "false"

    mail_user = m.get("username", "")
    vpn_user_for_kr = vu or (mail_user.split("@")[0] if "@" in mail_user else mail_user)
    try:
        import keyring
    except Exception:
        keyring = None
    if keyring:
        try:
            pw = keyring.get_password("Sesame-IMAP", mail_user) if mail_user else None
            if pw:
                mapping["IMAP_PASS"] = pw
        except Exception:
            pass
        try:
            pw = keyring.get_password("Sesame-VPN", vpn_user_for_kr) if vpn_user_for_kr else None
            if pw:
                mapping["VPN_PASS"] = pw
        except Exception:
            pass

    if not ENV_PATH.exists():
        ENV_PATH.touch()
    changed = False
    for key, val in mapping.items():
        if not val or os.getenv(key):  # don't overwrite anything the user already set
            continue
        set_key(str(ENV_PATH), key, val)
        os.environ[key] = val
        changed = True

    if changed:
        print(f"[core.config] Migrated legacy {legacy_path} into {ENV_PATH} "
              f"— config.json is now superseded (left in place, unused).")
    _mark_migrated()


def _mark_migrated() -> None:
    if not ENV_PATH.exists():
        ENV_PATH.touch()
    set_key(str(ENV_PATH), _MIGRATED_MARKER, "1")
    os.environ[_MIGRATED_MARKER] = "1"
