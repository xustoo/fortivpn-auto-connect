"""Windows-only: relaunch the app elevated so `openconnect` can create the
Wintun adapter it needs (this is Windows' equivalent of macOS's `sudo`).

Normally this path is not taken: Windows\\Kurulum.bat registers (with a single
UAC prompt, via Windows\\register_task.ps1) an on-demand Task Scheduler task
that runs with highest privileges, and the desktop shortcut starts it with
`schtasks /run`, so the app is already elevated when it starts. The task is
registered with battery restrictions disabled; otherwise it can sit "Queued"
on laptops running on battery.

This module is the fallback: if the task is missing or the app was started
by hand (`python main.py`) without admin rights, relaunch elevated via a
plain UAC prompt.
"""
from __future__ import annotations

import ctypes
import platform
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
MAIN_SCRIPT = APP_DIR / "main.py"


def is_windows() -> bool:
    return platform.system() == "Windows"


def is_admin() -> bool:
    if not is_windows():
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _launcher_exe() -> str:
    """Prefer pythonw.exe (no console window) next to the current interpreter."""
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if pythonw.exists():
        return str(pythonw)
    return sys.executable


def ensure_elevated_and_relaunch_if_needed() -> bool:
    """Call at startup, before building the UI.

    Returns True when the caller should continue starting the app normally
    (either already elevated, or elevation isn't applicable on this OS).
    Returns False when the caller should exit immediately: this instance
    handed off to an elevated relaunch (or the user declined/it failed), so
    a second, elevated process is (or should be) taking over.
    """
    if not is_windows():
        return True

    if is_admin():
        return True

    shell32 = ctypes.windll.shell32
    shell32.ShellExecuteW.restype = ctypes.c_void_p
    shell32.ShellExecuteW.argtypes = [
        ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
        ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_int
    ]
    exe = _launcher_exe()
    params = f'"{MAIN_SCRIPT}"'
    try:
        result = shell32.ShellExecuteW(None, "runas", exe, params, str(APP_DIR), 1)
        code = int(result) if result is not None else 0
        if code <= 32:
            print(f"[elevation] Yükseltme başlatılamadı (hata kodu: {code}). "
                  "openconnect tünelini kurmak için yönetici yetkisi gerekir; "
                  "UAC isteminde 'Evet' seçmeniz gerekiyor.")
            return False
    except Exception as e:
        print(f"[elevation] Yükseltme çağrısı başarısız oldu: {e!r}")
        return False

    return False
