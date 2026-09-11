#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Carbonio IMAP 2FA E-posta Okuyucu Modülü
Kolaysoft e-posta sunucusundan 'AuthCode' başlıklı doğrulama kodlarını anlık olarak çeker.
Eski mailleri asla indirmez; sadece ID numarası oturum başındakinden büyük olan
yeni e-posta düştüğünde milisaniyeler içinde tek bir sorgu ile kodu alır.
"""

import time
import re
import imaplib
import email
from typing import Optional, Callable, Set

TOKEN_REGEX_SUBJ = re.compile(r"AuthCode:\s*(\d{6})", re.IGNORECASE)
TOKEN_REGEX_BODY = re.compile(r"Your authentication token code is\s+(\d{6})", re.IGNORECASE)

USED_TOKEN_CODES: Set[str] = set()


def get_latest_email_id(imap_server: str, imap_port: int, imap_user: str, imap_pass: str) -> Optional[int]:
    """
    Oturum başlamadan önceki en yüksek e-posta ID numarasını döner.
    """
    mail = None
    try:
        mail = imaplib.IMAP4_SSL(imap_server, imap_port, timeout=8)
        mail.login(imap_user, imap_pass)
        mail.select("INBOX")
        status, data = mail.search(None, 'SUBJECT "AuthCode:"')
        if status == "OK" and data[0]:
            ids = [int(x) for x in data[0].split() if x.isdigit()]
            if ids:
                return max(ids)
    except Exception:
        pass
    finally:
        if mail:
            try:
                mail.logout()
            except Exception:
                pass
    return None


def fetch_token_from_imap(
    imap_server: str,
    imap_port: int,
    imap_user: str,
    imap_pass: str,
    after_id: Optional[int] = None,
    timeout_sec: int = 25,
    log_callback: Optional[Callable[[str], None]] = None,
    stop_check: Optional[Callable[[], bool]] = None
) -> Optional[str]:
    """
    Carbonio IMAP üzerinden yeni gelen 2FA kodunu yakalar.
    Eski mailleri tek tek indirip zaman kaybetmez; ID numarası after_id'den büyük
    yeni bir e-posta tespit edildiğinde ANINDA sadece o e-postayı çeker (0.2 sn).
    """
    def _log(msg: str):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)

    _log(f"IMAP: Yeni e-posta bekleniyor (Referans ID > {after_id})...")
    start_time = time.time()

    while time.time() - start_time < timeout_sec:
        if stop_check and stop_check():
            _log("IMAP: İşlem durduruldu.")
            return None

        mail = None
        try:
            mail = imaplib.IMAP4_SSL(imap_server, imap_port, timeout=5)
            mail.login(imap_user, imap_pass)
            mail.select("INBOX")

            # 1. Hızlı Arama: Sadece ID listesini al (ağda yalnızca birkaç bayt tutar, 0.2 sn sürer)
            status, data = mail.search(None, 'SUBJECT "AuthCode:"')
            if status == "OK" and data[0]:
                raw_ids = data[0].split()
                int_ids = [int(x) for x in raw_ids if x.isdigit()]

                if int_ids:
                    latest_id = max(int_ids)

                    # Eğer en son gelen e-posta bile referans ID'ye eşit veya küçükse:
                    # YENİ MAİL HENÜZ GELMEDİ! Eski mailleri indirme, bekle.
                    if after_id is not None and latest_id <= after_id:
                        try:
                            mail.logout()
                        except Exception:
                            pass
                        time.sleep(1.0)
                        continue

                    # YENİ MAİL GELDİ! (latest_id > after_id)
                    # Sadece ve sadece bu TEK e-postayı indir (0.1 sn)
                    res, msg_data = mail.fetch(str(latest_id), '(RFC822)')
                    if res == "OK" and msg_data and msg_data[0]:
                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)
                        subject = str(msg.get("Subject", ""))

                        token_code = None
                        m_subj = TOKEN_REGEX_SUBJ.search(subject)
                        if m_subj:
                            token_code = m_subj.group(1)
                        else:
                            body = ""
                            if msg.is_multipart():
                                for p in msg.walk():
                                    if p.get_content_type() in ["text/plain", "text/html"]:
                                        body += str(p.get_payload(decode=True))
                            else:
                                body = str(msg.get_payload(decode=True))
                            m_body = TOKEN_REGEX_BODY.search(body)
                            if m_body:
                                token_code = m_body.group(1)

                        if token_code and token_code not in USED_TOKEN_CODES:
                            _log(f"IMAP: Yeni 2FA kodu yakalandı: {token_code} (Mail ID: {latest_id})")
                            USED_TOKEN_CODES.add(token_code)
                            try:
                                mail.store(str(latest_id), "+FLAGS", "\\Seen")
                                mail.logout()
                            except Exception:
                                pass
                            return token_code

            try:
                mail.close()
                mail.logout()
            except Exception:
                pass

        except Exception:
            if mail:
                try:
                    mail.logout()
                except Exception:
                    pass

        time.sleep(1.0)

    _log(f"IMAP: {timeout_sec} saniye içinde yeni 2FA kodu gelmedi.")
    return None
