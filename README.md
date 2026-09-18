# FortiVPN Auto-Connect & 2FA Manager

FortiClient SSL-VPN bağlantısını, iki aşamalı doğrulamayı (2FA / OTP) e-postadan (Carbonio, Zimbra, IMAP) otomatik okuyarak **tek tıkla ve eller serbest (hands-free)** şekilde otomatikleştiren açık kaynaklı masaüstü yönetim aracı.

Hem **macOS** hem de **Windows** sistemlerinde, FortiClient uygulamasına ihtiyaç duymadan, açık kaynaklı istemcilerle (`openfortivpn` / `openconnect`) yerel olarak çalışır.

---

## Özellikler

- **Tam Otomatik 2FA (Zero-Click):** VPN sunucusuna bağlanır, 2FA kodu istendiğinde e-posta kutuna bağlanarak en güncel tek kullanımlık kodu (AuthCode) regex ile yakalar, otomatik olarak terminale yazar ve maili "Okundu" işaretler.
- **Akıllı Gecikme Toleransı:** Mail sunucusunun e-postayı iletme süresini (20 saniyelik geri sayım ve 90 saniyelik zaman aşımıyla) tolere eder; eski kodları kara listeye alarak asla yanlış/önceki kodu girmez.
- **Sade ve Profesyonel Arayüz:** Emoji veya gereksiz görsel karmaşadan arındırılmış, karanlık mod (dark theme) destekli modern masaüstü kontrol merkezi.
- **Canlı Süre ve Bilgi Paneli:** Hangi sunucuya bağlandığını, kullanıcı adını, maskeli şifreni (göster/gizle butonlu), son okunan 2FA kodunu ve tünelin kaç dakikadır aktif olduğunu saniye saniye gösterir.
- **Canlılık Denetimi (Keep-Alive):** Tünel durumunu izler, bağlantı koptuğunda süreci güvenle yeniler ve otomatik olarak tekrar bağlanır.
- **Çapraz Platform:** macOS ve Windows işletim sistemlerinde sorunsuz çalışır.

---

## Proje Dizin Yapısı

```text
FortiVPN/
├── main.py                 # Masaüstü grafik arayüzü (Tkinter tabanlı GUI)
├── vpn_worker.py           # Arka plan VPN tünel ve süreç yönetim motoru
├── imap_client.py          # Carbonio / IMAP 2FA e-posta tarama ve kod çıkarma modülü
├── requirements.txt        # Gerekli Python bağımlılıkları
├── .env.example            # Örnek yapılandırma şablonu
├── .gitignore              # Hassas parolaların GitHub'a gitmesini engelleyen dosya
├── FortiVPN_Baslat.command # macOS hızlı başlatıcı betiği
└── FortiVPN.app            # macOS çift tıklanabilir yerel uygulama paketi
```

---

## macOS Kurulum ve Kullanım Kılavuzu

### 1. Ön Koşullar

macOS üzerinde tünel arabirimini oluşturmak için `openfortivpn` ve `Python 3` gereklidir:

```bash
# Homebrew yüklü değilse Homebrew kurun, ardından:
brew install openfortivpn python
```

### 2. Projeyi İndirme ve Bağımlılıkları Yükleme

```bash
git clone <REPO_URL>
cd FortiVPN
pip3 install -r requirements.txt
```

### 3. Yapılandırma (`.env` Dosyası)

`.env.example` dosyasını kopyalayarak `.env` oluşturun:

```bash
cp .env.example .env
```

`.env` dosyasını bir metin düzenleyiciyle açıp kendi bilgilerinizi girin:

```ini
# VPN Sunucu Bilgileri
VPN_SERVER=vpn.sirketiniz.com:10321
VPN_USER=kullanici_adiniz
VPN_PASS=vpn_parolaniz
TRUSTED_CERT=   # Opsiyonel: Gateway sha256 sertifika özeti (boş bırakılırsa otomatik yakalanır)

# E-posta (Carbonio / IMAP SSL Port 993) Bilgileri
IMAP_SERVER=mail.sirketiniz.com
IMAP_PORT=993
IMAP_USER=adiniz@sirketiniz.com
IMAP_PASS=eposta_parolaniz
MAIL_TIMEOUT=90

# Canlılık Denetimi (Varsayılan olarak 'off' önerilir)
PING_TARGET=off

# macOS Yönetici Parolası (Ağ tüneli açmak için gereklidir)
MAC_SUDO_PASS=  # Boş bırakırsanız uygulama ilk açılışta ekrandan sorar ve kaydeder
```

### 4. Çalıştırma

Uygulamayı 3 farklı şekilde başlatabilirsiniz:

1. **Terminalden:**
   ```bash
   python3 main.py
   ```
2. **Hızlı Başlatıcı:** Klasördeki `FortiVPN_Baslat.command` dosyasına çift tıklayarak.
3. **Masaüstü Uygulaması:** `FortiVPN.app` paketine çift tıklayarak.

---

## Windows Kurulum ve Kullanım Kılavuzu

Windows'ta FortiClient uygulamasının kurulu olmasına **gerek yoktur**. Bağlantı, macOS'taki `openfortivpn`'in Windows karşılığı olan açık kaynaklı **openconnect** istemcisiyle kurulur (`--protocol=fortinet`).

### 1. Ön Koşullar

- **Python 3.8+**: [python.org](https://www.python.org/downloads/) üzerinden indirip kurun. *(Kurulum sırasında "Add Python to PATH" kutucuğunu işaretleyin).*
- **openconnect for Windows (CLI)**: `choco install openconnect-gui` / manuel OpenConnect-GUI installer'ı **sadece GUI'yi kurar, ayrı bir `openconnect.exe` içermez** — bizim otomasyonumuz için işe yaramaz. Gerçek CLI, openconnect projesinin kendi resmi GitLab CI derlemesinden indiriliyor:
  ```
  https://gitlab.com/openconnect/openconnect/-/jobs/artifacts/v9.21/raw/openconnect-installer-MinGW64-GnuTLS.exe?job=MinGW64%2FGnuTLS
  ```
  Bu dosyayı indirip çalıştırın (`openconnect.exe` genelde `C:\Program Files\OpenConnect\` altına kurulur). Kurulum sonrası klasörü PATH'e ekleyin, ya da `.env` dosyasındaki `OPENCONNECT_EXE` ile tam yolu belirtin.

  > Not: Bu link openconnect'in `v9.21` etiketine bağlı bir GitLab CI artifact'i; ileride süresi dolabilir. Güncel bir sürüm gerekirse: [gitlab.com/openconnect/openconnect/-/pipelines](https://gitlab.com/openconnect/openconnect/-/pipelines) üzerinden istediğiniz etiketin pipeline'ını açıp **"MinGW64/GnuTLS"** job'ının artifact'ini indirin.

### 2. Projeyi İndirme ve Bağımlılıkları Yükleme

Komut İstemi (CMD) veya PowerShell'de:

```cmd
git clone <REPO_URL>
cd FortiVPN
pip install -r requirements.txt
```

### 3. Yapılandırma (`.env` Dosyası)

`copy .env.example .env` komutu ile `.env` oluşturun ve bilgilerinizi düzenleyin:

```ini
VPN_SERVER=vpn.sirketiniz.com:10321
VPN_USER=kullanici_adiniz
VPN_PASS=vpn_parolaniz

# openconnect.exe PATH'te değilse tam yolu
OPENCONNECT_EXE=
# Boş bırakılırsa ilk bağlantıda sunucu sertifikası otomatik yakalanıp buraya kaydedilir
VPN_SERVERCERT=

IMAP_SERVER=mail.sirketiniz.com
IMAP_PORT=993
IMAP_USER=adiniz@sirketiniz.com
IMAP_PASS=eposta_parolaniz
MAIL_TIMEOUT=90
PING_TARGET=off
```

### 4. Çalıştırma

```cmd
python main.py
```

`openconnect`'in Windows'ta bir sanal ağ arayüzü (Wintun) oluşturabilmesi için yönetici yetkisi gerekir. Uygulama, admin olarak çalışmıyorsa başlangıçta kendini otomatik olarak yükseltilmiş (yönetici) şekilde yeniden başlatır — bunun için **her açılışta bir kez** Windows Kullanıcı Hesabı Denetimi (UAC) onayı istenir ("Evet" demeniz yeterli).

> Not: Görev Zamanlayıcı üzerinden "girişte otomatik, hiç UAC istemeden" çalıştırma da denendi, ancak bazı Windows kurulumlarında (ör. "en yüksek yetkiyle + kullanıcı oturumunda çalıştır" birleşimi) görev sonsuza dek "Queued" durumunda kalıp hiç çalışmıyor — bu, Windows'un görev zamanlayıcısının bilinen bir kısıtı. Bu yüzden daha basit ve güvenilir olan "her açılışta bir UAC onayı" yöntemi kullanılıyor.

---

## Yapılandırma Değişkenleri Açıklaması

| Değişken | Açıklama | Örnek Değer |
| :--- | :--- | :--- |
| `VPN_SERVER` | FortiGate VPN ağ geçidi host ve port bilgisi | `vpn.sirketiniz.com:10321` |
| `VPN_USER` | VPN kullanıcı adınız | `salihkirlioglu` |
| `VPN_PASS` | VPN oturum açma parolanız | `GucluParola123!` |
| `IMAP_SERVER` | Carbonio / Zimbra e-posta sunucusu adresi | `mail.sirketiniz.com` |
| `IMAP_PORT` | Güvenli IMAP SSL portu (Standart 993) | `993` |
| `IMAP_USER` | Doğrulama kodunun geldiği e-posta adresi | `adiniz@sirketiniz.com` |
| `IMAP_PASS` | E-posta hesabı parolanız | `MailSifresi123!` |
| `MAIL_TIMEOUT` | 2FA mailini bekleme tavan süresi (saniye) | `90` |
| `PING_TARGET` | VPN canlılık denetimi (ping atılacak iç IP). Devre dışı bırakmak için `off` yapın | `off` |
| `MAC_SUDO_PASS` | *(Yalnızca macOS)* `openfortivpn` tüneli için Mac kullanıcı parolası | `macParolaniz` |
| `OPENCONNECT_EXE` | *(Yalnızca Windows)* `openconnect.exe` dosyasının tam yolu (boşsa PATH'te aranır) | `C:\Tools\openconnect\openconnect.exe` |
| `VPN_SERVERCERT` | *(Yalnızca Windows)* openconnect sunucu sertifika özeti (boşsa ilk bağlantıda otomatik yakalanır) | `pin-sha256:...` |

---

## Güvenlik Notu

- Kendi gerçek kullanıcı adı ve şifrelerinizin yer aldığı `.env` dosyası **`.gitignore`** dosyası ile korunmaktadır.
- Projeyi GitHub'a gönderirken **kesinlikle `.env` dosyasını commit etmeyin**, yalnızca `.env.example` şablon dosyasını paylaşın.

---

## Lisans

Bu proje [MIT Lisansı](LICENSE) kapsamında açık kaynak olarak sunulmaktadır.
