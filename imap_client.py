#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Carbonio IMAP 2FA E-posta Okuyucu Modülü
Kolaysoft e-posta sunucusundan 'AuthCode' başlıklı doğrulama kodlarını anlık olarak çeker.
Eski denemelerden kalan e-postaları kesinlikle filtreler ve sadece yeni gelen kodu kabul eder.
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
    Mevcut en son AuthCode e-postasının ID numarasını döner.
    Ayrıca kutudaki mevcut tüm eski kodları kara listeye ekler ki tekrar kullanılmasınlar.
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
    timeout_sec: int = 45,
    log_callback: Optional[Callable[[str], None]] = None,
    stop_check: Optional[Callable[[], bool]] = None
) -> Optional[str]:
    """
    Carbonio IMAP üzerinden YENİ gelen 2FA AuthCode e-postasını anlık olarak arar.
    FortiGate zaman aşımına (15 sn) uğramadan kodu anında yakalamak için 1.5 saniyelik
    hızlı döngüyle tarar. Eski kodları kesinlikle atlar!
    """
    def _log(msg: str):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)

    _log(f"IMAP: Yeni 2FA e-postası taranıyor (Referans ID > {after_id})...")
    start_time = time.time()

    # Sunucuya e-postanın ilk baytının düşmesi için 1 saniyelik mikro bekleme
    time.sleep(1.0)

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
                        # 1. Kural: Eğer referans ID varsa, e-posta ID'si mutlaka referanstan BÜYÜK olmalıdır!
                        if after_id is not None and candidate_id <= after_id:
                            continue

                        # 2. Kural: Bu e-posta daha önce okunduysa atla
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

                        # 3. Kural: Kod daha önce kullanılmış bir kod ise kesinlikle atla!
                        if token_code in USED_TOKEN_CODES:
                            continue

                        # YEPYENİ KOD BULUNDU!
                        _log(f"IMAP: Yeni 2FA kodu bulundu: {token_code} (Mail ID: {candidate_id})")
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
            if mail:
                try:
                    mail.logout()
                except Exception:
                    pass

        time.sleep(1.2)

    _log(f"IMAP: {timeout_sec} saniye içinde yeni 2FA kodu içeren e-posta gelmedi.")
    return None
