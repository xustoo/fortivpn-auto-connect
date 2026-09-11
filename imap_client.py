#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Carbonio IMAP 2FA E-posta Okuyucu Modülü
Kolaysoft e-posta sunucusundan 'AuthCode' başlıklı doğrulama kodlarını çeker.
Mail sunucusu gecikmelerini tolere etmek için zaman aşımı ve bekleme süresi içerir.
"""

import time
import re
import imaplib
import email
from typing import Optional, Callable, Set

TOKEN_REGEX_SUBJ = re.compile(r"AuthCode:\s*(\d{6})", re.IGNORECASE)
TOKEN_REGEX_BODY = re.compile(r"Your authentication token code is\s+(\d{6})", re.IGNORECASE)

USED_TOKEN_CODES: Set[str] = set()
USED_EMAIL_IDS: Set[int] = set()


def get_latest_email_id(imap_server: str, imap_port: int, imap_user: str, imap_pass: str) -> Optional[int]:
    """
    Oturum başlamadan önceki en son e-postanın ID'sini alır.
    Kutudaki eski kodları kara listeye ekleyerek tekrar kullanılmalarını engeller.
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
    delay_sec: int = 20,
    timeout_sec: int = 90,
    log_callback: Optional[Callable[[str], None]] = None,
    stop_check: Optional[Callable[[], bool]] = None
) -> Optional[str]:
    """
    Carbonio IMAP üzerinden yeni gelen 2FA AuthCode e-postasını bekler.
    1. Önce mailin sunucuya ulaşması için 20 saniyelik zaman aşımı (delay) uygular.
    2. Ardından gelen kutusunu tarar ve yalnızca yeni gelen e-postayı okur.
    """
    def _log(msg: str):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)

    _log(f"IMAP: 2FA e-postasının Carbonio sunucusuna ulaşması bekleniyor ({delay_sec} saniye bekleme süresi)...")

    # 1. Aşama: E-posta gecikmesini bekleyen geri sayım döngüsü
    for sec_left in range(delay_sec, 0, -1):
        if stop_check and stop_check():
            _log("IMAP: İşlem kullanıcı tarafından durduruldu.")
            return None
        if sec_left in [20, 15, 10, 5, 2, 1]:
            _log(f"IMAP: E-posta bekleniyor... ({sec_left} sn kaldı)")
        time.sleep(1)

    _log(f"IMAP: Gelen kutusu taranıyor (Referans ID > {after_id})...")
    start_time = time.time()

    # 2. Aşama: Yeni gelen e-postayı yakalama döngüsü
    while time.time() - start_time < timeout_sec:
        if stop_check and stop_check():
            _log("IMAP: İşlem durduruldu.")
            return None

        mail = None
        try:
            mail = imaplib.IMAP4_SSL(imap_server, imap_port, timeout=8)
            mail.login(imap_user, imap_pass)
            mail.select("INBOX")

            status, data = mail.search(None, 'SUBJECT "AuthCode:"')
            if status == "OK" and data[0]:
                raw_ids = data[0].split()
                int_ids = sorted([int(x) for x in raw_ids if x.isdigit()])

                if int_ids:
                    # En yeni e-postaları kontrol et
                    for candidate_id in reversed(int_ids):
                        # 1. Şart: ID kesinlikle referanstan büyük olmalı
                        if after_id is not None and candidate_id <= after_id:
                            continue

                        # 2. Şart: Bu ID bu oturumda daha önce okunmamış olmalı
                        if candidate_id in USED_EMAIL_IDS:
                            continue

                        res, msg_data = mail.fetch(str(candidate_id), "(RFC822)")
                        if res != "OK" or not msg_data or not msg_data[0]:
                            continue

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

                        if not token_code:
                            continue

                        # 3. Şart: Kod eski denemelerden kalma bir kod olmamalı
                        if token_code in USED_TOKEN_CODES:
                            _log(f"IMAP: Mail ID {candidate_id} içindeki kod ({token_code}) eski denemeye ait. Yeni mail bekleniyor...")
                            continue

                        # YENİ KOD BAŞARIYLA BULUNDU
                        _log(f"IMAP: >>> YENİ 2FA KODU BULUNDU: {token_code} (Mail ID: {candidate_id}) <<<")
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

        except Exception as e:
            _log(f"IMAP Uyarısı: {e}")
            if mail:
                try:
                    mail.logout()
                except Exception:
                    pass

        time.sleep(2.0)

    _log(f"IMAP: {timeout_sec} saniye içinde yeni 2FA kodu içeren e-posta gelmedi.")
    return None
