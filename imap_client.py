#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Carbonio IMAP 2FA E-posta Okuyucu Modülü
Kolaysoft e-posta sunucusundan 'AuthCode' başlıklı doğrulama kodlarını anlık olarak çeker.
Zaman damgası (Timestamp) kontrolü sayesinde eski e-postaları kesinlikle eler
ve sadece bu istek anından SONRA gelen yeni e-postayı kabul eder.
"""

import time
import re
import imaplib
import email
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta
from typing import Optional, Callable, Set

TOKEN_REGEX_SUBJ = re.compile(r"AuthCode:\s*(\d{6})", re.IGNORECASE)
TOKEN_REGEX_BODY = re.compile(r"Your authentication token code is\s+(\d{6})", re.IGNORECASE)

USED_TOKEN_CODES: Set[str] = set()
USED_EMAIL_IDS: Set[int] = set()


def get_latest_email_id(imap_server: str, imap_port: int, imap_user: str, imap_pass: str) -> Optional[int]:
    """
    Oturum başlamadan önceki en son e-postanın ID'sini alır ve mevcut eski kodları kara listeye ekler.
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
                for eid in ids[-6:]:
                    USED_EMAIL_IDS.add(eid)
                    res, msg_data = mail.fetch(str(eid), "(RFC822)")
                    if res == "OK" and msg_data and msg_data[0]:
                        msg = email.message_from_bytes(msg_data[0][1])
                        m_subj = TOKEN_REGEX_SUBJ.search(str(msg.get("Subject", "")))
                        if m_subj:
                            USED_TOKEN_CODES.add(m_subj.group(1))
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
    request_timestamp: Optional[datetime] = None,
    timeout_sec: int = 35,
    log_callback: Optional[Callable[[str], None]] = None,
    stop_check: Optional[Callable[[], bool]] = None
) -> Optional[str]:
    """
    Carbonio IMAP üzerinden YENİ gelen 2FA AuthCode e-postasını arar.
    
    Çift Kontrol Mantığı:
    1. Zaman Damgası: E-postanın gönderilme saati, isteğin başlatıldığı andan (request_timestamp) yeni olmalıdır.
    2. ID Kontrolü: E-posta ID'si, oturum başındaki referans ID'den büyük olmalıdır.
    Bu sayede asla eski e-postayı okumaz; yeni e-posta düştüğü saniyede (gecikmeden) anında kodu alır.
    """
    def _log(msg: str):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)

    # İstek zamanı verilmemişse şu anki UTC zamanı al (sunucu saat farkı için 3 sn tolerans)
    if not request_timestamp:
        request_timestamp = datetime.now(timezone.utc) - timedelta(seconds=3)
    else:
        request_timestamp = request_timestamp - timedelta(seconds=3)

    req_str = request_timestamp.strftime("%H:%M:%S")
    _log(f"IMAP: 2FA e-postası bekleniyor (İstek zamanı: {req_str} UTC, Referans ID > {after_id})...")

    start_time = time.time()
    last_log_time = 0

    while time.time() - start_time < timeout_sec:
        if stop_check and stop_check():
            _log("IMAP: İşlem durduruldu.")
            return None

        mail = None
        try:
            mail = imaplib.IMAP4_SSL(imap_server, imap_port, timeout=6)
            mail.login(imap_user, imap_pass)
            mail.select("INBOX")

            status, data = mail.search(None, 'SUBJECT "AuthCode:"')
            if status == "OK" and data[0]:
                raw_ids = data[0].split()
                int_ids = sorted([int(x) for x in raw_ids if x.isdigit()])

                if int_ids:
                    # En yeni e-postaları geriye doğru incele
                    for candidate_id in reversed(int_ids):
                        # 1. Filtre: ID daha önce bu oturumda kullanıldıysa atla
                        if candidate_id in USED_EMAIL_IDS:
                            continue

                        # E-posta verisini çek
                        res, msg_data = mail.fetch(str(candidate_id), "(RFC822)")
                        if res != "OK" or not msg_data or not msg_data[0]:
                            continue

                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)

                        # 2. Filtre: Zaman Damgası Kontrolü (Email Date >= Request Time)
                        date_str = msg.get("Date")
                        if date_str:
                            try:
                                msg_dt = parsedate_to_datetime(date_str).astimezone(timezone.utc)
                                if msg_dt < request_timestamp:
                                    # Bu e-posta istek anından önce gelmiş, yani ESKİ!
                                    now = time.time()
                                    if now - last_log_time > 3:
                                        _log(f"IMAP: Son e-posta ({candidate_id}) istek anından önceye ait ({msg_dt.strftime('%H:%M:%S')}). Yeni mail bekleniyor...")
                                        last_log_time = now
                                    continue
                            except Exception:
                                pass

                        # 3. Filtre: ID referanstan büyük olmalı
                        if after_id is not None and candidate_id <= after_id:
                            continue

                        # Kodu yakala
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

                        if not token_code or token_code in USED_TOKEN_CODES:
                            continue

                        # TÜM ŞARTLAR SAĞLANDI: YENİ E-POSTA VE KOD!
                        _log(f"IMAP: Yeni doğrulama kodu başarıyla yakalandı: {token_code} (Mail ID: {candidate_id})")
                        USED_TOKEN_CODES.add(token_code)
                        USED_EMAIL_IDS.add(candidate_id)

                        try:
                            mail.store(str(candidate_id), "+FLAGS", "\\Seen")
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

        time.sleep(1.2)

    _log(f"IMAP: {timeout_sec} saniye içinde yeni 2FA kodu içeren e-posta gelmedi.")
    return None
