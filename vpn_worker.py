#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VPN İş Parçacığı ve Yönetim Modülü (macOS openfortivpn & Windows openconnect)
"""

import os
import sys
import time
import subprocess
import platform
import threading
import shutil
import re
import signal
import tempfile
from datetime import datetime, timezone
from typing import Optional, Callable
from imap_client import fetch_token_from_imap, get_latest_email_id, create_imap_session


class VPNWorker(threading.Thread):
    def __init__(
        self,
        config: dict,
        on_status_change: Callable[[str, str], None],
        on_token_received: Callable[[str], None],
        on_connected: Callable[[], None],
        on_disconnected: Callable[[], None],
        on_log: Callable[[str], None],
        get_sudo_pass_callback: Optional[Callable[[], str]] = None
    ):
        super().__init__(daemon=True)
        self.config = config
        self.on_status_change = on_status_change
        self.on_token_received = on_token_received
        self.on_connected = on_connected
        self.on_disconnected = on_disconnected
        self.on_log = on_log
        self.get_sudo_pass_callback = get_sudo_pass_callback

        self._stop_event = threading.Event()
        self.process: Optional[subprocess.Popen] = None
        self.trusted_cert: str = self.config.get("TRUSTED_CERT", "")
        self.is_connected = False
        self.temp_config_path = None

    def log(self, msg: str):
        self.on_log(msg)

    def stop(self):
        """VPN bağlantısını güvenli şekilde durdurur."""
        self._stop_event.set()
        self.kill_process()
        self.cleanup_temp_files()
        self.is_connected = False
        self.on_status_change("Bağlantı Kesildi", "#ed8796")
        self.on_disconnected()
        self.log("VPN bağlantısı sonlandırıldı.")

    def cleanup_temp_files(self):
        if self.temp_config_path and os.path.exists(self.temp_config_path):
            try:
                os.remove(self.temp_config_path)
            except Exception:
                pass
            self.temp_config_path = None

    def kill_process(self):
        """Mevcut süreci ve alt süreçlerini sonlandırır."""
        if self.process and self.process.poll() is None:
            try:
                if platform.system() == "Windows":
                    # Önce nazikçe (Ctrl+Break) - openconnect Wintun adaptörünü
                    # düzgün temizleyebilsin diye; olmazsa zorla sonlandır.
                    try:
                        self.process.send_signal(signal.CTRL_BREAK_EVENT)
                        self.process.wait(timeout=3)
                    except Exception:
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(self.process.pid)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                else:
                    self.process.terminate()
                    time.sleep(0.4)
                    if self.process.poll() is None:
                        self.process.kill()
            except Exception:
                pass
        self.process = None

    def ping_target(self, host: str) -> bool:
        """Canlılık pingi atar."""
        is_win = platform.system() == "Windows"
        param = "-n" if is_win else "-c"
        timeout_param = "-w" if is_win else "-W"
        timeout_val = "1000" if is_win else "1"

        cmd = ["ping", param, "1", timeout_param, timeout_val, host]
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2
            )
            return res.returncode == 0
        except Exception:
            return False

    def run(self):
        """Ana döngü: Bağlanma ve otomatik kurtarma."""
        reconnect_delay = int(self.config.get("RECONNECT_DELAY", "20"))

        while not self._stop_event.is_set():
            try:
                success = self._run_single_vpn_session()
            except Exception as e:
                self.log(f"Oturum hatası: {e}")
                success = False

            if self._stop_event.is_set():
                break

            self.is_connected = False
            self.on_disconnected()
            self.on_status_change("Yeniden Bağlanılıyor...", "#eed49f")
            self.log(f"Bağlantı kapandı. {reconnect_delay} saniye sonra tekrar denenecek...")

            for _ in range(reconnect_delay):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    def _prepare_openfortivpn_config(self) -> str:
        """openfortivpn için geçici yapılandırma dosyası oluşturur."""
        server_raw = self.config.get("VPN_SERVER", "").replace("https://", "").replace("http://", "")
        if ":" in server_raw:
            host, port = server_raw.split(":", 1)
        else:
            host, port = server_raw, "443"

        user = self.config.get("VPN_USER", "")
        password = self.config.get("VPN_PASS", "")

        conf_lines = [
            f"host = {host}",
            f"port = {port}",
            f"username = {user}",
            f"password = {password}"
        ]

        if self.trusted_cert:
            conf_lines.append(f"trusted-cert = {self.trusted_cert}")

        fd, temp_path = tempfile.mkstemp(prefix="fortivpn_", suffix=".conf")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(conf_lines) + "\n")

        os.chmod(temp_path, 0o600)
        self.temp_config_path = temp_path
        return temp_path

    def _run_single_vpn_session(self) -> bool:
        """Tek bir VPN oturumunu yönetir."""
        self.kill_process()
        self.cleanup_temp_files()
        self.on_status_change("Hazırlanıyor...", "#8aadf4")

        system = platform.system()
        server = self.config.get("VPN_SERVER", "").replace("https://", "").replace("http://", "")
        user = self.config.get("VPN_USER", "")
        password = self.config.get("VPN_PASS", "")

        self.log("IMAP: Referans e-posta ve aktif oturum hazırlanıyor...")
        imap_session, baseline_id = create_imap_session(
            imap_server=self.config.get("IMAP_SERVER", ""),
            imap_port=int(self.config.get("IMAP_PORT", "993")),
            imap_user=self.config.get("IMAP_USER", ""),
            imap_pass=self.config.get("IMAP_PASS", "")
        )

        sudo_pass = self.config.get("MAC_SUDO_PASS", "")

        if system == "Windows":
            openconnect_exe = (
                self.config.get("OPENCONNECT_EXE")
                or shutil.which("openconnect")
                or shutil.which("openconnect.exe")
            )
            if not openconnect_exe:
                for candidate in (
                    r"C:\Program Files\OpenConnect\openconnect.exe",
                    r"C:\Program Files (x86)\OpenConnect\openconnect.exe",
                ):
                    if os.path.isfile(candidate):
                        openconnect_exe = candidate
                        break
            if not openconnect_exe or not os.path.exists(openconnect_exe):
                self.log("HATA: openconnect.exe bulunamadı! .env dosyasında OPENCONNECT_EXE ayarlayın.")
                self.on_status_change("openconnect Eksik", "#ed8796")
                return False

            # --passwd-on-stdin kasıtlı olarak kullanılmıyor: openconnect düz bir
            # stdin pipe'ından da parola/OTP istemlerini okuyabiliyor; parola burada
            # reaktif olarak (parola istemi tespit edilince) gönderiliyor, aşağıda.
            cmd = [openconnect_exe, "--protocol=fortinet", "-u", user, "-v"]

            servercert = self.config.get("VPN_SERVERCERT", "")
            if servercert:
                cmd += ["--servercert", servercert]

            vpnc_script = self.config.get("VPNC_SCRIPT", "")
            if vpnc_script:
                cmd += ["--script", vpnc_script]

            import shlex
            raw_extra = (self.config.get("VPN_EXTRA_ARGS") or "").strip()
            if raw_extra:
                cmd += shlex.split(raw_extra)

            cmd.append(server)
        else:
            openfortivpn_bin = shutil.which("openfortivpn") or "/opt/homebrew/bin/openfortivpn"
            if not os.path.exists(openfortivpn_bin):
                self.log("HATA: openfortivpn bulunamadı!")
                self.on_status_change("openfortivpn Eksik", "#ed8796")
                return False

            if not sudo_pass:
                test_res = subprocess.run(["sudo", "-n", "true"], capture_output=True)
                if test_res.returncode != 0:
                    if self.get_sudo_pass_callback:
                        self.log("Ağ tüneli oluşturmak için Mac parolası isteniyor...")
                        sudo_pass = self.get_sudo_pass_callback()
                        if sudo_pass:
                            self.config["MAC_SUDO_PASS"] = sudo_pass
                        else:
                            self.log("HATA: Mac parolası girilmedi.")
                            self.on_status_change("Yetki İptal", "#ed8796")
                            return False

            conf_path = self._prepare_openfortivpn_config()
            cmd = ["sudo", "-S", openfortivpn_bin, "-c", conf_path]

        self.on_status_change("Bağlanıyor...", "#8aadf4")
        self.log(f"VPN başlatılıyor: {server} (Kullanıcı: {user})")

        popen_kwargs = {}
        if system == "Windows":
            # Konsol penceresi açmaz + Ctrl+Break ile düzgün kapatabilmemizi sağlar
            # (bkz. disconnect: openconnect'in Wintun adaptörünü temizleyebilmesi için).
            popen_kwargs["creationflags"] = (
                subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
            )

        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=0,
                **popen_kwargs
            )
        except Exception as e:
            self.log(f"VPN süreci başlatılamadı: {e}")
            self.on_status_change("Başlatma Hatası", "#ed8796")
            return False

        if system != "Windows" and sudo_pass:
            time.sleep(0.2)
            try:
                self.process.stdin.write(f"{sudo_pass}\n".encode("utf-8"))
                self.process.stdin.flush()
            except Exception:
                pass

        # Windows/openconnect: parola, "Password:" istemi tespit edilince reaktif
        # olarak gönderilir (aşağıdaki döngüde). openconnect prompt'u hiç
        # basmazsa diye kısa bir süre sonra proaktif olarak da gönderilir.
        pw_sent = False
        proc_start_time = time.time()

        token_requested = False
        output_buffer = ""
        connected = False

        while not self._stop_event.is_set():
            if self.process.poll() is not None:
                self.log(f"VPN istemcisi kapandı (Çıkış Kodu: {self.process.returncode})")
                break

            try:
                raw_byte = self.process.stdout.read(1)
            except Exception:
                break

            if not raw_byte:
                time.sleep(0.03)
                continue

            char = raw_byte.decode("utf-8", errors="replace")
            output_buffer += char

            if char == "\n":
                line = output_buffer.strip()
                if line and not any(p in line.lower() for p in ["password", "parola"]):
                    self.log(f"[VPN] {line}")
                output_buffer = ""
            elif len(output_buffer) > 400:
                output_buffer = output_buffer[-400:]

            # Hatalı Mac Parolası
            if "incorrect password attempt" in output_buffer or "Sorry, try again" in output_buffer:
                self.log("HATA: Girilen Mac yönetici parolası yanlış!")
                self.on_status_change("Hatalı Mac Parolası", "#ed8796")
                self.config["MAC_SUDO_PASS"] = ""
                return False

            # FortiGate Güvenlik Duvarı Koruması / Hata Mesajları
            if any(p in output_buffer.lower() for p in ["too many bad login attempts", "login disabled", "permission denied"]):
                self.log("UYARI: FortiGate sunucusu çok fazla deneme nedeniyle geçici olarak kilitlendi (60-120 sn). Bekleniyor...")
                self.on_status_change("Sunucu Kilitli (Bekleniyor)", "#eed49f")
                time.sleep(30)
                return False

            # Sertifika onayı (openfortivpn: Y/N; openconnect: 'yes' bekliyor)
            if any(p in output_buffer for p in ["(Y/N)", "(y/n)", "Do you want to continue with this connection?"]):
                self.log("CLI: Sertifika onayı tespit edildi, 'Y' gönderiliyor...")
                self.process.stdin.write(b"Y\n")
                self.process.stdin.flush()
                output_buffer = ""
            elif "enter 'yes' to accept" in output_buffer.lower():
                self.log("CLI: Sertifika onayı tespit edildi, 'yes' gönderiliyor...")
                self.process.stdin.write(b"yes\n")
                self.process.stdin.flush()
                output_buffer = ""

            # Sertifika digest yakalama (openfortivpn: --trusted-cert=..., openconnect: pin-sha256:...)
            cert_match = re.search(r"--trusted-cert=([a-f0-9]{64})", output_buffer, re.IGNORECASE)
            if cert_match and not self.trusted_cert:
                found_digest = cert_match.group(1)
                self.log(f"Sertifika özeti yakalandı: {found_digest}")
                self.trusted_cert = found_digest
                self.config["TRUSTED_CERT"] = found_digest

            servercert_match = re.search(r"(pin-sha256:[A-Za-z0-9+/=]+)", output_buffer)
            if servercert_match and not self.config.get("VPN_SERVERCERT"):
                found_servercert = servercert_match.group(1)
                self.log(f"Sunucu sertifika özeti yakalandı: {found_servercert}")
                self.config["VPN_SERVERCERT"] = found_servercert

            if system == "Windows":
                # Windows/openconnect: yönetici yetkisi olmadan Wintun adaptörü kurulamaz.
                if re.search(r"administrator privileges|access is denied.*wintun|wintun.*access is denied|"
                             r"neither windows-tap nor wintun|set up tun device failed",
                             output_buffer, re.IGNORECASE):
                    self.log("HATA: openconnect ağ adaptörünü kuramadı - uygulamayı YÖNETİCİ olarak çalıştırın.")
                    self.on_status_change("Yönetici Yetkisi Gerekli", "#ed8796")
                    return False

                # Parola istemi: openconnect --passwd-on-stdin kullanmadan da bu pipe'tan
                # parolayı okuyabiliyor; istem görülünce (ya da kısa bir süre sonra
                # proaktif olarak, istem hiç basılmazsa diye) parola gönderilir.
                pw_prompt = re.search(r"password[: ]*$|enter .*password|account password",
                                       output_buffer, re.IGNORECASE)
                if not pw_sent and (pw_prompt or (time.time() - proc_start_time) > 1.2):
                    pw_sent = True
                    try:
                        self.process.stdin.write(f"{password}\n".encode("utf-8"))
                        self.process.stdin.flush()
                    except Exception:
                        pass
                    output_buffer = ""

            # --- 1. 2FA TOKEN İSTEMİ ---
            is_token_prompt = any(
                p in output_buffer.lower() for p in [
                    "two-factor authentication token:",
                    "two-factor authentication",
                    "two-factor",
                    "token:",
                    "sms/email token:",
                    "otp:",
                    "one-time-password:",
                    "enter token:",
                    "authcode",
                    "challenge",
                    "code:",
                    "code :",
                    "enter code",
                    "verification code",
                    "passcode",
                    "second factor",
                    "fortitoken",
                    "2fa"
                ]
            )

            if is_token_prompt and not token_requested:
                token_requested = True
                prompt_time = datetime.now(timezone.utc)
                self.on_status_change("2FA Taranıyor...", "#eed49f")
                self.log("[2FA] İstemi algılandı. Yeni doğrulama e-postası taranıyor...")

                token_code = fetch_token_from_imap(
                    imap_server=self.config.get("IMAP_SERVER", ""),
                    imap_port=int(self.config.get("IMAP_PORT", "993")),
                    imap_user=self.config.get("IMAP_USER", ""),
                    imap_pass=self.config.get("IMAP_PASS", ""),
                    after_id=baseline_id,
                    timeout_sec=int(self.config.get("MAIL_TIMEOUT", "45")),
                    log_callback=self.log,
                    stop_check=lambda: self._stop_event.is_set(),
                    existing_mail_session=imap_session
                )

                if not token_code:
                    self.log("HATA: 2FA kodu e-postadan yakalanamadı!")
                    self.on_status_change("2FA Alınamadı", "#ed8796")
                    return False

                self.on_token_received(token_code)
                self.log(f"[2FA] Kod VPN istemcisine iletiliyor: {token_code}")

                if not self.process or not self.process.stdin:
                    self.log("VPN süreci sonlandırıldığı için kod iletilemedi.")
                    return False

                try:
                    self.process.stdin.write(f"{token_code}\n".encode("utf-8"))
                    self.process.stdin.flush()
                except (BrokenPipeError, OSError) as e:
                    self.log(f"HATA: VPN sunucusu zaman aşımı nedeniyle bağlantıyı erken kapattı ({e}).")
                    return False

                output_buffer = ""

            # --- 2. SADECE GERÇEK TÜNEL AÇILMA MESAJLARINI KABUL ET ---
            is_connected_msg = any(
                p in output_buffer for p in [
                    "Tunnel is up and running.",
                    "Status: Connected",
                    "Tunnel running",
                    "ip-up: ppp0",
                    "Interface ppp0 is UP",
                    "Adding VPN nameservers",
                    # openconnect (Windows)
                    "Configured as",
                    "Connected as",
                    "Connected tun",
                    "SSL connected",
                    "session authentication will expire",
                    "Established DTLS",
                    "Established ESP",
                    "ESP session established",
                    "tunnel is up and running"
                ]
            )

            if is_connected_msg and not connected:
                connected = True
                self.is_connected = True
                self.on_status_change("Bağlandı", "#a6da95")
                self.on_connected()
                self.log(">>> TEBRİKLER: Kolaysoft VPN Tüneli Başarıyla Açıldı! <<<")
                break

        # --- AŞAMA 2: CANLILIK VE SÜREÇ DENETİMİ (KEEP-ALIVE) ---
        if connected and not self._stop_event.is_set():
            ping_target_ip = self.config.get("PING_TARGET", "off").strip().lower()
            ping_interval = int(self.config.get("PING_INTERVAL", "15"))
            enable_ping = ping_target_ip not in ["off", "none", "no", "", "10.0.0.1"]

            if enable_ping:
                self.log(f"Canlılık pingi aktif: {ping_target_ip} ({ping_interval}s)")
            else:
                self.log("VPN Tüneli devrede. Bağlantı arka planda sürekli canlı tutuluyor.")

            consecutive_fails = 0
            max_fails = int(self.config.get("MAX_PING_FAILS", "3"))

            while not self._stop_event.is_set():
                if self.process.poll() is not None:
                    self.log("VPN süreci kapandı.")
                    break

                if enable_ping:
                    if self.ping_target(ping_target_ip):
                        if consecutive_fails > 0:
                            self.log("VPN ping normale döndü.")
                        consecutive_fails = 0
                    else:
                        consecutive_fails += 1
                        self.log(f"Ping yanıt vermedi ({consecutive_fails}/{max_fails})")
                        if consecutive_fails >= max_fails:
                            self.log("KRİTİK: VPN tüneli ping yanıtı vermedi!")
                            break

                for _ in range(ping_interval):
                    if self._stop_event.is_set():
                        break
                    time.sleep(1)

        self.cleanup_temp_files()
        return connected
