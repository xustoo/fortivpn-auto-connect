#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
FortiVPN Desktop Kontrol Merkezi
=============================================================================
Arayüz `ui/` klasöründeki HTML/CSS/JS'tir ve pywebview penceresinde çalışır
(Windows: WebView2, macOS: WKWebView). Bu dosya yalnızca Python tarafını
(köprü) içerir:

  JS -> Python : pywebview.api.connect / disconnect / get_config /
                 save_config / export_log / minimize / close
  Python -> JS : window.onStatus / onError / onLog / onToken /
                 onConnected / onDisconnected   (bkz. ui/app.js)
"""

import json
import os
import platform
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import webview

from vpn_worker import VPNWorker
from core import config as core_config
from core import elevation

APP_DIR = Path(__file__).resolve().parent
UI_DIR = APP_DIR / "ui"

WINDOW_TITLE = "FortiVPN"
WINDOW_SIZE = (720, 492)  # 460 içerik + 32 özel başlık çubuğu (ui/styles.css)
WINDOW_BG = "#0B1220"

# ui/app.js alan adı -> .env anahtarı
FIELD_MAP = {
    "server": "VPN_SERVER",
    "user": "VPN_USER",
    "password": "VPN_PASS",
    "imap_host": "IMAP_SERVER",
    "imap_port": "IMAP_PORT",
    "email": "IMAP_USER",
    "email_password": "IMAP_PASS",
    "ping_target": "PING_TARGET",
    "openconnect_path": "OPENCONNECT_EXE",
    "server_cert": "VPN_SERVERCERT",
    "sudo_password": "MAC_SUDO_PASS",
}

PLACEHOLDER_DEFAULTS = {
    "VPN_SERVER": "vpn.kolaysoft.com.tr:10321",
    "VPN_USER": "salihkirlioglu",
    "IMAP_SERVER": "mail.kolaysoft.com.tr",
    "IMAP_USER": "salih.kirlioglu@kolaysoft.com.tr",
    "TRUSTED_CERT": "982454617fafe06a8268d7f663b1926b6d40cbc73dbdc47cc4aa0e2886e06305",
}

# VPNWorker durum metni -> ui/app.js evresi
STATUS_PHASES = {
    "Bağlantı Kesildi": "idle",
    "Bağlantı Kapandı": "idle",
    "Hazırlanıyor": "preparing",
    "Bağlanıyor": "connecting",
    "2FA Taranıyor": "scan2fa",
    "Bağlandı": "connected",
    "Yeniden Bağlanılıyor": "reconnecting",
}
# VPNWorker durum metni -> ui/app.js hata kodu (ERRORS)
STATUS_ERRORS = {
    "2FA Alınamadı": "2fa",
    "Giriş Başarısız": "login",
    "Yönetici Yetkisi Gerekli": "admin",
    "Hatalı Mac Parolası": "macpw",
    "openconnect Eksik": "openconnect",
    "openfortivpn Eksik": "openfortivpn",
}
# Bilinmeyen durumlar için VPNWorker'ın gönderdiği renkten seviye türet
COLOR_LEVELS = {
    "#ed8796": "error",
    "#eed49f": "waiting",
    "#a6da95": "connected",
}


def classify_log(msg: str) -> str:
    """Günlük satırını ui/app.js seviyelerinden birine eşler."""
    if any(w in msg for w in ["Başarı", "Aktif", "SUCCESS", "TEBRİKLER", "Açıldı"]):
        return "success"
    if any(w in msg for w in ["HATA", "başarısız", "koptu", "ERROR", "Yanlış"]):
        return "error"
    if any(w in msg for w in ["2FA", "token", "Token"]):
        return "token"
    if any(w in msg for w in ["UYARI", "bekleniyor", "denenecek"]):
        return "warning"
    return "info"


class Api:
    """JS tarafına açılan köprü. `_` ile başlayan üyeler JS'e açılmaz."""

    def __init__(self, auto_connect: bool = True):
        self._window = None
        self._worker = None
        self._auto_connect = auto_connect
        self._auto_started = False
        self._fitted = False
        self._closing = False
        self._config = self._load_config()

    # ------------------------------------------------------------ config ----
    @staticmethod
    def _load_config() -> dict:
        cfg = core_config.load()
        for key, val in PLACEHOLDER_DEFAULTS.items():
            if not cfg.get(key):
                cfg[key] = val
        return cfg

    def get_config(self) -> dict:
        self._config = self._load_config()
        return {js: self._config.get(env, "") for js, env in FIELD_MAP.items()}

    def save_config(self, values: dict) -> dict:
        try:
            for js, env in FIELD_MAP.items():
                if js in values:
                    self._config[env] = str(values[js]).strip()
            core_config.save(self._config)
        except Exception as exc:
            return {"ok": False, "error": f"Kaydedilemedi: {exc}"}
        self._log("Ayarlar güncellendi.", "warning")
        return {"ok": True}

    # -------------------------------------------------------------- VPN -----
    def connect(self) -> bool:
        self._config = self._load_config()
        self._stop_worker(join=True, notify=False)
        self._worker = VPNWorker(
            config=self._config,
            on_status_change=self._on_status,
            on_token_received=self._on_token,
            on_connected=self._on_connected,
            on_disconnected=self._on_disconnected,
            on_log=self._on_log,
            get_sudo_pass_callback=self._request_mac_sudo_pass,
        )
        self._worker.daemon = True
        self._worker.start()
        return True

    def disconnect(self) -> bool:
        self._stop_worker()
        return True

    def shutdown(self) -> None:
        # `closing` olayı pywebview'da UI iş parçacığında senkron çalışır; bu sırada
        # evaluate_js (worker.stop()'un günlük satırı dahil) UI iş parçacığının
        # kendisini beklediği için pencere kilitlenir ("Yanıt Vermiyor"). Bu yüzden
        # kapanış başladıktan sonra arayüze hiçbir şey gönderilmez.
        self._closing = True
        self._stop_worker(notify=False)

    def _stop_worker(self, join: bool = False, notify: bool = True) -> None:
        worker, self._worker = self._worker, None
        if not worker:
            return
        if not notify:
            # Yeniden bağlanırken eski oturumun "Bağlantı Kesildi" bildirimi
            # yeni oturumun durumunu ezmesin.
            worker.on_status_change = lambda *_: None
            worker.on_disconnected = lambda: None
        worker.stop()
        if join:
            worker.join(timeout=2.0)

    def _request_mac_sudo_pass(self) -> str:
        """macOS: parola arayüzde Ayarlar > Gelişmiş altında tutulur."""
        pwd = core_config.load().get("MAC_SUDO_PASS", "")
        if not pwd:
            self._log("Mac yönetici parolası gerekli: Ayarlar > Gelişmiş bölümünden "
                      "Sudo parolasını girin.", "warning")
        return pwd

    # ----------------------------------------------------------- window -----
    def minimize(self) -> None:
        if self._window:
            self._window.minimize()

    def close(self) -> None:
        if self._window:
            self._window.destroy()

    def export_log(self, text: str) -> dict:
        if not self._window:
            return {"ok": False}
        picked = self._window.create_file_dialog(
            webview.FileDialog.SAVE, save_filename="fortivpn-gunluk.txt"
        )
        if not picked:
            return {"ok": False}
        path = picked if isinstance(picked, str) else picked[0]
        Path(path).write_text(text, encoding="utf-8")
        return {"ok": True}

    # --------------------------------------------- lifecycle (Python-side) --
    def _fit_window(self) -> None:
        """Windows'ta pywebview boyutu çerçeveyi de kapsar; tasarım ise içerik
        alanında tam 720x460 bekler. Farkı ölçüp pencereyi büyütür."""
        for _ in range(2):
            try:
                inner_w, inner_h = self._window.evaluate_js("[innerWidth, innerHeight]")
            except Exception:
                return
            dw, dh = WINDOW_SIZE[0] - inner_w, WINDOW_SIZE[1] - inner_h
            if not (dw or dh):
                return
            self._window.resize(self._window.width + dw, self._window.height + dh)

    def _on_loaded(self) -> None:
        if not self._auto_started and not self._fitted:
            self._fitted = True
            self._fit_window()
        if self._auto_connect and not self._auto_started:
            self._auto_started = True
            self._log("Uygulama açıldı. Otomatik Kolaysoft VPN bağlantısı başlatılıyor...", "warning")
            self.connect()

    # ------------------------------------------- Python -> JS (any thread) ---
    def _js(self, fn: str, *args) -> None:
        if not self._window or self._closing:
            return
        call =",".join(json.dumps(a) for a in args)
        try:
            self._window.evaluate_js(f"window.{fn}&&window.{fn}({call})")
        except Exception:
            pass  # pencere kapanırken gelen geç bildirimler önemsiz

    def _log(self, msg: str, level: str = None) -> None:
        self._js("onLog", msg, level or classify_log(msg), time.strftime("%H:%M:%S"))

    def _on_log(self, msg: str) -> None:
        self._log(msg)

    def _on_token(self, token: str) -> None:
        self._js("onToken", token, time.strftime("%H:%M:%S"), "E-postadan alındı")

    def _on_connected(self) -> None:
        self._js("onConnected", int(time.time() * 1000))

    def _on_disconnected(self) -> None:
        self._js("onDisconnected")

    def _on_status(self, text: str, color: str) -> None:
        key = text.rstrip(".… ").strip()
        if key in STATUS_ERRORS:
            code = STATUS_ERRORS[key]
            self._js("onStatus", text, "error", code)
        elif key in STATUS_PHASES:
            self._js("onStatus", None, "idle", STATUS_PHASES[key])
        else:
            level = COLOR_LEVELS.get((color or "").lower(), "working")
            phase = {"error": "error", "waiting": "reconnecting",
                     "connected": "connected"}.get(level, "connecting")
            self._js("onStatus", text, level, phase)


# ---------------------------------------------------------------------------
def acquire_single_instance_lock():
    """Aynı anda birden fazla FortiVPN kopyasının çalışmasını engeller."""
    lock_path = os.path.join(tempfile.gettempdir(), "fortivpn_single_instance.lock")
    try:
        if platform.system() == "Windows":
            import msvcrt
            f = open(lock_path, "w")
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                return f
            except (IOError, OSError):
                return None
        else:
            import fcntl
            f = open(lock_path, "w")
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return f
            except (IOError, BlockingIOError, OSError):
                return None
    except Exception:
        return None


def show_native_warning(title: str, message: str) -> None:
    """Pencere açılmadan önce kullanılan basit sistem uyarısı."""
    try:
        if platform.system() == "Windows":
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x30)  # MB_ICONWARNING
        elif platform.system() == "Darwin":
            script = 'display dialog {} with title {} buttons {{"Tamam"}} with icon caution'.format(
                json.dumps(message), json.dumps(title))
            subprocess.run(["osascript", "-e", script], check=False)
        else:
            print(f"{title}\n{message}", file=sys.stderr)
    except Exception:
        print(f"{title}\n{message}", file=sys.stderr)


def run_ui(auto_connect: bool = True, debug: bool = False) -> None:
    api = Api(auto_connect=auto_connect)
    window = webview.create_window(
        WINDOW_TITLE,
        str(UI_DIR / "index.html"),
        js_api=api,
        width=WINDOW_SIZE[0],
        height=WINDOW_SIZE[1],
        resizable=False,
        frameless=True,    # başlık çubuğunu ui/index.html'deki .titlebar çizer
        easy_drag=False,   # sürükleme yalnızca .pywebview-drag-region'dan
        background_color=WINDOW_BG,
        text_select=False,
    )
    api._window = window
    window.events.loaded += api._on_loaded
    window.events.closing += api.shutdown
    webview.start(debug=debug)
    api.shutdown()


if __name__ == "__main__":
    try:
        if not elevation.ensure_elevated_and_relaunch_if_needed():
            sys.exit(0)

        lock_file = acquire_single_instance_lock()
        if lock_file is None:
            show_native_warning(
                "FortiVPN Zaten Çalışıyor",
                "FortiVPN arka planda zaten açık durumdadır.\n\n"
                "Aynı anda birden fazla uygulamanın çalışması VPN sunucusunun "
                "oturumunuzu sürekli sonlandırmasına neden olur. Lütfen açık olan pencereyi kullanın."
            )
            sys.exit(0)

        try:
            run_ui(auto_connect="--no-autoconnect" not in sys.argv,
                   debug="--debug" in sys.argv)
        finally:
            try:
                lock_file.close()
            except Exception:
                pass
    except SystemExit:
        raise
    except Exception:
        # pythonw.exe (Görev Zamanlayıcı ile sessiz başlatma) hiçbir konsola
        # bağlı değil; beklenmeyen bir hata sessizce kaybolmasın diye buraya yazılır.
        import traceback
        crash_log = APP_DIR / "crash.log"
        with open(crash_log, "a", encoding="utf-8") as f:
            f.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            traceback.print_exc(file=f)
        raise
