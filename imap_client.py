#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Carbonio IMAP 2FA E-posta Okuyucu Modülü
Kolaysoft e-posta sunucusundan 'AuthCode' başlıklı doğrulama kodlarını anlık olarak çeker.
Ağ yavaşlığında bile gecikme yaşamamak için:
1. Tek bir SSL oturumunu açık tutar (her döngüde yeniden login olup saniyeler kaybetmez).
2. Sadece e-posta Başlığını (BODY.PEEK[HEADER.FIELDS (SUBJECT)]) çeker (~40 bayt).
3. 0.4 saniye aralıklarla NOOP ile anında yeni ID kontrolü yapar.
"""

import time
import re
import imaplib
from typing import Optional, Callable, Set, Tuple

TOKEN_REGEX_SUBJ = re.compile(r"AuthCode:\s*(\d{6})", re.IGNORECASE)
TOKEN_REGEX_BODY = re.compile(r"Your authentication token code is\s+(\d{6})", re.IGNORECASE)

USED_TOKEN_CODES: Set[str] = set()


def create_imap_session(
    imap_server: str,
    imap_port: int,
    imap_user: str,
    imap_pass: str
) -> Tuple[Optional[imaplib.IMAP4_SSL], Optional[int]]:
    """
    IMAP SSL bağlantısını kurar, INBOX'ı seçer ve mevcut en son e-posta ID'sini döner.
    Bu oturum açık tutularak 2FA sorgusunda doğrudan kullanılır, böylece sıfırdan
    bağlanma ve login süreleri (şirket ağında 4-6 saniye) tamamen bertaraf edilir.
    """
    try:
        mail = imaplib.IMAP4_SSL(imap_server, imap_port, timeout=10)
        mail.login(imap_user, imap_pass)
        mail.select("INBOX")
        status, data = mail.search(None, 'SUBJECT "AuthCode:"')
        latest_id = None
        if status == "OK" and data[0]:
            ids = [int(x) for x in data[0].split() if x.isdigit()]
            if ids:
                latest_id = max(ids)
        return mail, latest_id
    except Exception:
        return None, None


def get_latest_email_id(imap_server: str, imap_port: int, imap_user: str, imap_pass: str) -> Optional[int]:
    """
    Oturum başlamadan önceki en yüksek e-posta ID numarasını döner.
    """
    mail, latest_id = create_imap_session(imap_server, imap_port, imap_user, imap_pass)
    if mail:
        try:
            mail.logout()
        except Exception:
            pass
    return latest_id


def fetch_token_from_imap(
    imap_server: str,
    imap_port: int,
    imap_user: str,
    imap_pass: str,
    after_id: Optional[int] = None,
    timeout_sec: int = 25,
    log_callback: Optional[Callable[[str], None]] = None,
    stop_check: Optional[Callable[[], bool]] = None,
    existing_mail_session: Optional[imaplib.IMAP4_SSL] = None
) -> Optional[str]:
    """
    Carbonio IMAP üzerinden yeni gelen 2FA kodunu yakalar.
    Eğer mevcut bir IMAP oturumu (existing_mail_session) verilmişse onu kullanır,
    böylece yavaş ağlarda SSL el sıkışması ve login beklemesi 0 saniyeye iner.
    Sadece SUBJECT başlığını çektiği için transfer anında tamamlanır.
    """
    def _log(msg: str):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)

    _log(f"IMAP: Yeni e-posta bekleniyor (Referans ID > {after_id})...")
    start_time = time.time()

    mail = existing_mail_session
    owns_session = False

    while time.time() - start_time < timeout_sec:
        if stop_check and stop_check():
            _log("IMAP: İşlem durduruldu.")
            if owns_session and mail:
                try:
                    mail.logout()
                except Exception:
                    pass
            return None

        # Eğer oturum yoksa veya koptuysa yeniden bağlan
        if mail is None:
            try:
                mail = imaplib.IMAP4_SSL(imap_server, imap_port, timeout=8)
                mail.login(imap_user, imap_pass)
                mail.select("INBOX")
                owns_session = True
            except Exception as e:
                _log(f"IMAP bağlantı denemesi: {e}")
                time.sleep(0.5)
                continue

        try:
            # Gelen kutusunu sunucuyla senkronize et (NOOP)
            mail.noop()

            # Sadece AuthCode başlıklı e-posta ID'lerini tara
            status, data = mail.search(None, 'SUBJECT "AuthCode:"')
            if status == "OK" and data[0]:
                raw_ids = data[0].split()
                int_ids = [int(x) for x in raw_ids if x.isdigit()]

                if int_ids:
                    latest_id = max(int_ids)

                    # Eğer henüz yeni e-posta gelmediyse bekle
                    if after_id is not None and latest_id <= after_id:
                        time.sleep(0.4)
                        continue

                    # YENİ MAİL DÜŞTÜ! (latest_id > after_id)
                    # Tüm e-posta gövdesini değil, SADECE SUBJECT BAŞLIĞINI ÇEK (~50 bayt)
                    # Bu sayede şirket interneti ne kadar yavaş olursa olsun anında gelir (0.05 sn).
                    res, hdr_data = mail.fetch(str(latest_id), '(BODY.PEEK[HEADER.FIELDS (SUBJECT)])')
                    token_code = None

                    if res == "OK" and hdr_data and hdr_data[0]:
                        raw_hdr = hdr_data[0][1]
                        if isinstance(raw_hdr, bytes):
                            hdr_text = raw_hdr.decode("utf-8", errors="ignore")
                        else:
                            hdr_text = str(raw_hdr)
                        
                        m_subj = TOKEN_REGEX_SUBJ.search(hdr_text)
                        if m_subj:
                            token_code = m_subj.group(1)

                    # Başlıkta bulunamadıysa garanti olması için gövdeyi kontrol et
                    if not token_code:
                        res, msg_data = mail.fetch(str(latest_id), '(RFC822)')
                        if res == "OK" and msg_data and msg_data[0]:
                            raw_email = msg_data[0][1]
                            body_text = str(raw_email)
                            m_body = TOKEN_REGEX_BODY.search(body_text)
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

        except Exception as e:
            # Oturum koptuysa sıfırla, döngüde yeniden açılacak
            try:
                mail.close()
                mail.logout()
            except Exception:
                pass
            mail = None
            owns_session = True

        time.sleep(0.4)

    _log(f"IMAP: {timeout_sec} saniye içinde yeni 2FA kodu gelmedi.")
    if mail:
        try:
            mail.logout()
        except Exception:
            pass
    return None
