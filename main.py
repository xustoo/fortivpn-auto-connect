#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
FortiVPN Desktop Kontrol Merkezi
=============================================================================
"""

import os
import sys
import time
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
import platform
import threading
from dotenv import load_dotenv, set_key

# Modülleri içe aktar
from vpn_worker import VPNWorker

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(ENV_PATH)

THEME = {
    "bg_dark": "#181825",
    "bg_card": "#24273a",
    "bg_card_border": "#363a4f",
    "fg_text": "#cad3f5",
    "fg_subtext": "#939ab7",
    "accent_blue": "#8aadf4",
    "accent_green": "#a6da95",
    "accent_red": "#ed8796",
    "accent_yellow": "#eed49f",
    "accent_purple": "#c6a0f6",
    "log_bg": "#11111b",
    "log_fg": "#cdd6f4",
}


class CustomButton(tk.Label):
    """
    Sade, modern ve işletim sistemi bağımsız renk desteği sunan profesyonel buton.
    """
    def __init__(
        self,
        parent,
        text="",
        command=None,
        bg="#313244",
        fg="#ffffff",
        hover_bg=None,
        active_bg=None,
        border_color=None,
        font=("SF Pro Text", 10, "bold"),
        padx=14,
        pady=7,
        **kwargs
    ):
        super().__init__(
            parent,
            text=text,
            font=font,
            bg=bg,
            fg=fg,
            padx=padx,
            pady=pady,
            cursor="pointinghand" if platform.system() == "Darwin" else "hand2",
            relief="flat",
            highlightthickness=1 if border_color else 0,
            highlightbackground=border_color or bg,
            **kwargs
        )
        self.command = command
        self._default_bg = bg
        self._hover_bg = hover_bg or bg
        self._active_bg = active_bg or hover_bg or bg

        self.bind("<Enter>", lambda e: self.configure(bg=self._hover_bg))
        self.bind("<Leave>", lambda e: self.configure(bg=self._default_bg))
        self.bind("<Button-1>", self._on_click)

    def _on_click(self, event=None):
        self.configure(bg=self._active_bg)
        self.after(90, lambda: self.configure(bg=self._hover_bg))
        if self.command:
            self.command()

    def set_text(self, new_text):
        self.config(text=new_text)


class FortiVPNApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("FortiClient VPN Yöneticisi")
        self.geometry("820x760")
        self.minsize(780, 680)
        self.configure(bg=THEME["bg_dark"])

        self.config_data = self.load_config()
        self.vpn_worker = None
        self.connected_start_time = None
        self.is_password_visible = False
        self.last_token_code = "------"
        self.last_token_time = "--:--:--"

        self.setup_styles()
        self.create_widgets()
        self.update_timer()

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(800, self.auto_start_on_launch)

    def load_config(self) -> dict:
        """Yapılandırma değişkenlerini .env dosyasından yükler."""
        return {
            "VPN_SERVER": os.getenv("VPN_SERVER", "vpn.kolaysoft.com.tr:10321"),
            "VPN_USER": os.getenv("VPN_USER", "salihkirlioglu"),
            "VPN_PASS": os.getenv("VPN_PASS", ""),
            "IMAP_SERVER": os.getenv("IMAP_SERVER", "mail.kolaysoft.com.tr"),
            "IMAP_PORT": os.getenv("IMAP_PORT", "993"),
            "IMAP_USER": os.getenv("IMAP_USER", "salih.kirlioglu@kolaysoft.com.tr"),
            "IMAP_PASS": os.getenv("IMAP_PASS", ""),
            "PING_TARGET": os.getenv("PING_TARGET", "off"),
            "PING_INTERVAL": os.getenv("PING_INTERVAL", "15"),
            "MAX_PING_FAILS": os.getenv("MAX_PING_FAILS", "3"),
            "RECONNECT_DELAY": os.getenv("RECONNECT_DELAY", "15"),
            "MAIL_TIMEOUT": os.getenv("MAIL_TIMEOUT", "90"),
            "MAC_SUDO_PASS": os.getenv("MAC_SUDO_PASS", ""),
            "TRUSTED_CERT": os.getenv("TRUSTED_CERT", "982454617fafe06a8268d7f663b1926b6d40cbc73dbdc47cc4aa0e2886e06305")
        }

    def setup_styles(self):
        self.style = ttk.Style(self)
        self.style.theme_use("clam")

    def create_widgets(self):
        # Üst Başlık ve Durum
        header_frame = tk.Frame(self, bg=THEME["bg_dark"], padx=26, pady=18)
        header_frame.pack(fill="x")

        title_text_box = tk.Frame(header_frame, bg=THEME["bg_dark"])
        title_text_box.pack(side="left")

        lbl_title = tk.Label(
            title_text_box, text="FortiClient VPN Yöneticisi",
            font=("SF Pro Display", 18, "bold"),
            bg=THEME["bg_dark"], fg=THEME["fg_text"]
        )
        lbl_title.pack(anchor="w")

        lbl_subtitle = tk.Label(
            title_text_box, text="Kolaysoft • İki Aşamalı Doğrulama (2FA)",
            font=("SF Pro Text", 10),
            bg=THEME["bg_dark"], fg=THEME["fg_subtext"]
        )
        lbl_subtitle.pack(anchor="w", pady=(2, 0))

        # Sağ: Durum Rozeti
        self.status_badge = tk.Label(
            header_frame, text="Bağlantı Kesildi",
            font=("SF Pro Text", 10, "bold"),
            bg=THEME["bg_card"], fg=THEME["accent_red"],
            padx=14, pady=6, relief="flat", highlightthickness=1,
            highlightbackground=THEME["bg_card_border"]
        )
        self.status_badge.pack(side="right")

        # Bilgi Kartları Alanı
        cards_container = tk.Frame(self, bg=THEME["bg_dark"], padx=20, pady=5)
        cards_container.pack(fill="x")
        cards_container.columnconfigure(0, weight=1)
        cards_container.columnconfigure(1, weight=1)

        self.card_server = self._create_card(cards_container, "SUNUCU ADRESİ", self.config_data["VPN_SERVER"])
        self.card_server["frame"].grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        self.card_time = self._create_card(cards_container, "BAĞLANTI SÜRESİ", "00:00:00 (Bağlı Değil)", value_color=THEME["accent_yellow"])
        self.card_time["frame"].grid(row=0, column=1, sticky="nsew", padx=6, pady=6)

        self.card_user = self._create_card(cards_container, "KULLANICI ADI", self.config_data["VPN_USER"])
        self.card_user["frame"].grid(row=1, column=0, sticky="nsew", padx=6, pady=6)

        self.card_pass = self._create_password_card(cards_container, "PAROLA", self.config_data["VPN_PASS"])
        self.card_pass["frame"].grid(row=1, column=1, sticky="nsew", padx=6, pady=6)

        self.token_card = self._create_token_card(cards_container)
        self.token_card.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=6, pady=8)

        # Kontrol Butonları
        btn_bar = tk.Frame(self, bg=THEME["bg_dark"], padx=26, pady=8)
        btn_bar.pack(fill="x")

        # Bağlan / Yeniden Başlat Butonu
        self.btn_connect = CustomButton(
            btn_bar,
            text="Bağlan",
            command=self.start_vpn,
            bg="#10b981",
            fg="#ffffff",
            hover_bg="#059669",
            active_bg="#047857",
            font=("SF Pro Text", 11, "bold"),
            padx=20,
            pady=9
        )
        self.btn_connect.pack(side="left", padx=(0, 10))

        # Bağlantıyı Kes Butonu
        self.btn_disconnect = CustomButton(
            btn_bar,
            text="Bağlantıyı Kes",
            command=self.stop_vpn,
            bg="#ef4444",
            fg="#ffffff",
            hover_bg="#dc2626",
            active_bg="#b91c1c",
            font=("SF Pro Text", 11, "bold"),
            padx=16,
            pady=9
        )
        self.btn_disconnect.pack(side="left", padx=(0, 10))

        # Ayarlar Butonu
        self.btn_settings = CustomButton(
            btn_bar,
            text="Ayarlar",
            command=self.open_settings,
            bg="#2a2d42",
            fg="#cad3f5",
            hover_bg="#3b3f5c",
            active_bg="#1e2030",
            border_color="#8aadf4",
            font=("SF Pro Text", 11),
            padx=16,
            pady=9
        )
        self.btn_settings.pack(side="left", padx=(0, 10))

        # Logları Temizle Butonu
        self.btn_clear_log = CustomButton(
            btn_bar,
            text="Logları Temizle",
            command=self.clear_logs,
            bg="#24273a",
            fg="#939ab7",
            hover_bg="#363a4f",
            active_bg="#181825",
            border_color="#363a4f",
            font=("SF Pro Text", 10),
            padx=14,
            pady=9
        )
        self.btn_clear_log.pack(side="right")

        # Olay Günlüğü (Log) Paneli
        log_frame = tk.Frame(self, bg=THEME["bg_dark"], padx=26, pady=8)
        log_frame.pack(fill="both", expand=True)

        lbl_log_title = tk.Label(
            log_frame, text="OLAY GÜNLÜĞÜ",
            font=("SF Pro Text", 9, "bold"),
            bg=THEME["bg_dark"], fg=THEME["fg_subtext"]
        )
        lbl_log_title.pack(anchor="w", pady=(0, 4))

        self.log_text = scrolledtext.ScrolledText(
            log_frame, bg=THEME["log_bg"], fg=THEME["log_fg"],
            insertbackground="white", font=("Menlo", 10),
            wrap="word", relief="flat", padx=10, pady=10,
            highlightthickness=1, highlightbackground=THEME["bg_card_border"]
        )
        self.log_text.pack(fill="both", expand=True)

        self.log_text.tag_config("SUCCESS", foreground=THEME["accent_green"])
        self.log_text.tag_config("ERROR", foreground=THEME["accent_red"])
        self.log_text.tag_config("WARN", foreground=THEME["accent_yellow"])
        self.log_text.tag_config("TOKEN", foreground=THEME["accent_purple"], font=("Menlo", 10, "bold"))

    def _create_card(self, parent, title: str, initial_val: str, value_color=None):
        frame = tk.Frame(
            parent, bg=THEME["bg_card"], padx=14, pady=12,
            highlightthickness=1, highlightbackground=THEME["bg_card_border"]
        )
        lbl_title = tk.Label(
            frame, text=title, font=("SF Pro Text", 9, "bold"),
            bg=THEME["bg_card"], fg=THEME["fg_subtext"]
        )
        lbl_title.pack(anchor="w")

        lbl_val = tk.Label(
            frame, text=initial_val, font=("SF Pro Display", 13, "bold"),
            bg=THEME["bg_card"], fg=value_color or THEME["fg_text"]
        )
        lbl_val.pack(anchor="w", pady=(3, 0))
        return {"frame": frame, "value_label": lbl_val}

    def _create_password_card(self, parent, title: str, password_val: str):
        frame = tk.Frame(
            parent, bg=THEME["bg_card"], padx=14, pady=12,
            highlightthickness=1, highlightbackground=THEME["bg_card_border"]
        )
        lbl_title = tk.Label(
            frame, text=title, font=("SF Pro Text", 9, "bold"),
            bg=THEME["bg_card"], fg=THEME["fg_subtext"]
        )
        lbl_title.pack(anchor="w")

        content_row = tk.Frame(frame, bg=THEME["bg_card"])
        content_row.pack(fill="x", pady=(3, 0))

        masked_text = "•" * min(len(password_val), 14) if password_val else "(Tanımlanmadı)"
        lbl_val = tk.Label(
            content_row, text=masked_text, font=("SF Pro Display", 13, "bold"),
            bg=THEME["bg_card"], fg=THEME["fg_text"]
        )
        lbl_val.pack(side="left", anchor="w")

        btn_toggle = CustomButton(
            content_row,
            text="Göster",
            command=lambda: self.toggle_password_visibility(lbl_val, btn_toggle),
            bg="#2a2d42",
            fg="#8aadf4",
            hover_bg="#3b3f5c",
            border_color="#8aadf4",
            font=("SF Pro Text", 9, "bold"),
            padx=10,
            pady=4
        )
        btn_toggle.pack(side="right")
        return {"frame": frame, "value_label": lbl_val, "button": btn_toggle}

    def toggle_password_visibility(self, label: tk.Label, button):
        actual_pass = self.config_data.get("VPN_PASS", "")
        if self.is_password_visible:
            label.config(text="•" * min(len(actual_pass), 14))
            button.set_text("Göster")
            self.is_password_visible = False
        else:
            label.config(text=actual_pass if actual_pass else "(Boş)")
            button.set_text("Gizle")
            self.is_password_visible = True

    def _create_token_card(self, parent):
        frame = tk.Frame(
            parent, bg=THEME["bg_card"], padx=18, pady=12,
            highlightthickness=1, highlightbackground=THEME["accent_purple"]
        )
        header_box = tk.Frame(frame, bg=THEME["bg_card"])
        header_box.pack(fill="x")

        lbl_title = tk.Label(
            header_box, text="İKİ AŞAMALI DOĞRULAMA (2FA KODU)",
            font=("SF Pro Text", 9, "bold"),
            bg=THEME["bg_card"], fg=THEME["accent_purple"]
        )
        lbl_title.pack(side="left")

        self.lbl_token_source = tk.Label(
            header_box, text="Kaynak: Carbonio IMAP",
            font=("SF Pro Text", 8),
            bg=THEME["bg_card"], fg=THEME["fg_subtext"]
        )
        self.lbl_token_source.pack(side="right")

        code_box = tk.Frame(frame, bg=THEME["bg_card"])
        code_box.pack(fill="x", pady=(6, 0))

        self.lbl_token_value = tk.Label(
            code_box, text="[  - - - - - -  ]", font=("Menlo", 20, "bold"),
            bg=THEME["bg_card"], fg=THEME["accent_green"], padx=8
        )
        self.lbl_token_value.pack(side="left")

        self.lbl_token_time = tk.Label(
            code_box, text="Henüz kod okunmadı",
            font=("SF Pro Text", 10),
            bg=THEME["bg_card"], fg=THEME["fg_subtext"]
        )
        self.lbl_token_time.pack(side="left", padx=15)

        btn_copy = CustomButton(
            code_box,
            text="Kopyala",
            command=self.copy_token_to_clipboard,
            bg="#8b5cf6",
            fg="#ffffff",
            hover_bg="#7c3aed",
            active_bg="#6d28d9",
            font=("SF Pro Text", 9, "bold"),
            padx=14,
            pady=5
        )
        btn_copy.pack(side="right")
        return frame

    def copy_token_to_clipboard(self):
        if self.last_token_code and self.last_token_code != "------":
            self.clipboard_clear()
            self.clipboard_append(self.last_token_code)
            self.log_message(f"Panoya kopyalandı: {self.last_token_code}", "TOKEN")
            messagebox.showinfo("Kopyalandı", f"2FA Kodu ({self.last_token_code}) panoya kopyalandı.")

    def request_mac_sudo_pass(self) -> str:
        res = [None]
        event = threading.Event()

        def _ask():
            pwd = simpledialog.askstring(
                "Mac Yönetici Yetkisi Gerekli",
                "Kolaysoft VPN ağ tünelini kurabilmek için\n"
                "lütfen Mac oturum açma parolanızı girin:\n\n"
                "(Bu parola .env dosyanıza kaydedilir ve tekrar sorulmaz)",
                show="*",
                parent=self
            )
            res[0] = pwd
            event.set()

        self.after(0, _ask)
        event.wait(timeout=60)
        entered_pwd = res[0] or ""
        if entered_pwd:
            self.config_data["MAC_SUDO_PASS"] = entered_pwd
            set_key(ENV_PATH, "MAC_SUDO_PASS", entered_pwd)
        return entered_pwd

    def auto_start_on_launch(self):
        self.log_message("Uygulama açıldı. Otomatik Kolaysoft VPN bağlantısı başlatılıyor...", "WARN")
        self.start_vpn()

    def start_vpn(self):
        load_dotenv(ENV_PATH, override=True)
        self.config_data = self.load_config()
        if self.vpn_worker and self.vpn_worker.is_alive():
            self.log_message("Mevcut VPN oturumu yenileniyor...", "WARN")
            self.vpn_worker.stop()
            self.vpn_worker.join(timeout=2.0)

        self.vpn_worker = VPNWorker(
            config=self.config_data,
            on_status_change=self.on_status_change_callback,
            on_token_received=self.on_token_received_callback,
            on_connected=self.on_connected_callback,
            on_disconnected=self.on_disconnected_callback,
            on_log=self.on_log_callback,
            get_sudo_pass_callback=self.request_mac_sudo_pass
        )
        self.vpn_worker.start()

    def stop_vpn(self):
        if self.vpn_worker:
            self.vpn_worker.stop()
            self.vpn_worker = None
        self.set_status("Bağlantı Kesildi", THEME["accent_red"])
        self.connected_start_time = None
        self.card_time["value_label"].config(text="00:00:00 (Bağlantı Kesildi)", fg=THEME["accent_red"])

    def on_status_change_callback(self, status: str, color: str):
        self.after(0, lambda: self.set_status(status, color))

    def on_token_received_callback(self, token: str):
        self.after(0, lambda: self.display_token(token))

    def on_connected_callback(self):
        self.after(0, self.handle_connected)

    def on_disconnected_callback(self):
        self.after(0, self.handle_disconnected)

    def on_log_callback(self, msg: str):
        self.after(0, lambda: self.log_message(msg))

    def set_status(self, text: str, color: str):
        self.status_badge.config(text=text, fg=color)

    def display_token(self, token: str):
        self.last_token_code = token
        self.last_token_time = time.strftime("%H:%M:%S")
        self.lbl_token_value.config(text=f"[  {token}  ]", fg=THEME["accent_green"])
        self.lbl_token_time.config(
            text=f"Son okuma saati: {self.last_token_time}",
            fg=THEME["fg_text"]
        )

    def handle_connected(self):
        self.connected_start_time = time.time()
        self.set_status("Bağlandı", THEME["accent_green"])
        self.log_message("Kolaysoft VPN bağlantısı başarıyla kuruldu!", "SUCCESS")

    def handle_disconnected(self):
        self.connected_start_time = None
        self.set_status("Bağlantı Kapandı", THEME["accent_red"])
        self.card_time["value_label"].config(text="00:00:00 (Bağlı Değil)", fg=THEME["accent_yellow"])

    def update_timer(self):
        if self.connected_start_time:
            elapsed = int(time.time() - self.connected_start_time)
            hours, remainder = divmod(elapsed, 3600)
            mins, secs = divmod(remainder, 60)
            time_str = f"{hours:02d}:{mins:02d}:{secs:02d}"
            detail_str = f"{mins} dk {secs} sn aktif" if hours == 0 else f"{hours} sa {mins} dk aktif"
            self.card_time["value_label"].config(
                text=f"{time_str}  ({detail_str})",
                fg=THEME["accent_green"]
            )
        self.after(1000, self.update_timer)

    def log_message(self, msg: str, tag: str = None):
        t_str = time.strftime("%H:%M:%S")
        full_msg = f"[{t_str}] {msg}\n"
        if not tag:
            if any(w in msg for w in ["Başarı", "Aktif", "SUCCESS", "TEBRİKLER", "Açıldı"]):
                tag = "SUCCESS"
            elif any(w in msg for w in ["HATA", "başarısız", "koptu", "ERROR", "Yanlış"]):
                tag = "ERROR"
            elif any(w in msg for w in ["2FA", "token", "Token"]):
                tag = "TOKEN"
            elif any(w in msg for w in ["UYARI", "bekleniyor", "denenecek"]):
                tag = "WARN"

        self.log_text.insert(tk.END, full_msg, tag)
        self.log_text.see(tk.END)

    def clear_logs(self):
        self.log_text.delete("1.0", tk.END)

    def open_settings(self):
        win = tk.Toplevel(self)
        win.title("VPN Yapılandırma Ayarları")
        win.geometry("540x630")
        win.configure(bg=THEME["bg_dark"])
        win.transient(self)
        win.grab_set()

        lbl_s_title = tk.Label(
            win, text="Bağlantı ve Kimlik Bilgileri",
            font=("SF Pro Display", 15, "bold"),
            bg=THEME["bg_dark"], fg=THEME["accent_blue"]
        )
        lbl_s_title.pack(anchor="w", padx=20, pady=(18, 12))

        fields = [
            ("VPN Sunucusu (Host:Port)", "VPN_SERVER", False),
            ("VPN Kullanıcı Adı", "VPN_USER", False),
            ("VPN Parolası", "VPN_PASS", True),
            ("IMAP Mail Sunucusu", "IMAP_SERVER", False),
            ("IMAP Portu (SSL)", "IMAP_PORT", False),
            ("IMAP E-posta Adresi", "IMAP_USER", False),
            ("IMAP E-posta Parolası", "IMAP_PASS", True),
            ("Canlılık Ping Hedefi (off önerilir)", "PING_TARGET", False),
            ("Mac Sudo Parolası (Ağ tüneli için)", "MAC_SUDO_PASS", True)
        ]

        entries = {}
        form_frame = tk.Frame(win, bg=THEME["bg_dark"], padx=20)
        form_frame.pack(fill="both", expand=True)

        for i, (label_text, key, is_secret) in enumerate(fields):
            lbl = tk.Label(
                form_frame, text=label_text, font=("SF Pro Text", 9, "bold"),
                bg=THEME["bg_dark"], fg=THEME["fg_subtext"]
            )
            lbl.grid(row=i*2, column=0, sticky="w", pady=(4, 0))

            ent = tk.Entry(
                form_frame, font=("SF Pro Text", 10),
                bg=THEME["bg_card"], fg=THEME["fg_text"],
                insertbackground="white", relief="flat",
                show="*" if is_secret else ""
            )
            ent.insert(0, self.config_data.get(key, ""))
            ent.grid(row=i*2+1, column=0, sticky="ew", pady=(2, 6))
            entries[key] = ent

        form_frame.columnconfigure(0, weight=1)

        def save_settings():
            for k, entry in entries.items():
                val = entry.get().strip()
                self.config_data[k] = val
                set_key(ENV_PATH, k, val)

            self.card_server["value_label"].config(text=self.config_data["VPN_SERVER"])
            self.card_user["value_label"].config(text=self.config_data["VPN_USER"])
            
            actual_pass = self.config_data["VPN_PASS"]
            if not self.is_password_visible:
                self.card_pass["value_label"].config(text="•" * min(len(actual_pass), 14))
            else:
                self.card_pass["value_label"].config(text=actual_pass)

            messagebox.showinfo("Kaydedildi", "Ayarlar başarıyla kaydedildi!", parent=win)
            win.destroy()
            self.log_message("Ayarlar güncellendi.", "WARN")

        btn_save = CustomButton(
            win,
            text="Kaydet",
            command=save_settings,
            bg="#10b981",
            fg="#ffffff",
            hover_bg="#059669",
            active_bg="#047857",
            font=("SF Pro Text", 11, "bold"),
            padx=24,
            pady=9
        )
        btn_save.pack(pady=18)

    def on_close(self):
        if self.vpn_worker:
            self.vpn_worker.stop()
        self.destroy()
        sys.exit(0)


if __name__ == "__main__":
    app = FortiVPNApp()
    app.mainloop()
