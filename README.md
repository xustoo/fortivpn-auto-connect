# FortiVPN Auto-Connect & 2FA Manager

FortiClient SSL-VPN bağlantısını, iki aşamalı doğrulamayı (2FA / OTP) e-postadan (Carbonio, Zimbra, IMAP) otomatik okuyarak **tek tıkla ve eller serbest (hands-free)** şekilde otomatikleştiren açık kaynaklı masaüstü yönetim aracı.

Hem **macOS** (`openfortivpn` tabanlı) hem de **Windows** (`FortiSSLVPNcli.exe` tabanlı) sistemleri yerel olarak destekler.

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
├── install.sh              # macOS/Linux için tek tıkla/tek komutla otomatik kurulum aracı
├── Kurulum.command         # macOS Finder üzerinden çift tıklanabilir kurulum sihirbazı
├── install.bat             # Windows için otomatik sanal ortam ve kısayol kurulum aracı
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

## Hızlı ve Otomatik Kurulum (Önerilen)

### macOS (Tek Komutla Kurulum)

Terminalinizi açıp aşağıdaki komutu yapıştırmanız yeterlidir:

```bash
curl -fsSL https://raw.githubusercontent.com/xustoo/fortivpn-auto-connect/main/install.sh | bash
```

Bu komut:
- Gerekli sistem bağımlılıklarını (`openfortivpn`, `python3`) kontrol eder ve kurar.
- İzole sanal ortamı (`.venv`) oluşturur ve kütüphaneleri yükler.
- `.env` yapılandırma dosyasını hazır eder.
- Masaüstünüze çift tıklanabilir **FortiVPN.app** ve **FortiVPN_Baslat.command** kısayollarını yerleştirir.

*Alternatif Olarak:* Projeyi indirip klasör içindeki **`Kurulum.command`** dosyasına çift tıklayarak da sihirbazı başlatabilirsiniz.

---

### Windows (Otomatik Kurulum)

Projeyi indirdikten sonra klasördeki **`install.bat`** dosyasına çift tıklayın. Sanal ortamınız kurulacak ve Masaüstünüze `FortiVPN_Baslat.bat` kısayolu eklenecektir.

---

## Manuel Kurulum ve Kullanım Kılavuzu

### macOS Manuel Kurulum

#### 1. Ön Koşullar

macOS üzerinde tünel arabirimini oluşturmak için `openfortivpn` ve `Python 3` gereklidir:

```bash
brew install openfortivpn python
```

#### 2. Projeyi İndirme ve Bağımlılıkları Yükleme

```bash
git clone https://github.com/xustoo/fortivpn-auto-connect.git
cd fortivpn-auto-connect
./install.sh
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

### 1. Ön Koşullar

- **Python 3.8+**: [python.org](https://www.python.org/downloads/) üzerinden indirip kurun. *(Kurulum sırasında "Add Python to PATH" kutucuğunu işaretleyin).*
- **FortiClient SSL-VPN CLI**: FortiClient kurulumuyla birlikte gelen `FortiSSLVPNcli.exe` aracı gereklidir.  
  *(Genellikle şu konumdadır: `C:\Program Files (x86)\Fortinet\SslvpnClient\FortiSSLVPNcli.exe`)*

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

# Windows için FortiSSLVPNcli.exe tam yolu
FORTICLIENT_PATH=C:\Program Files (x86)\Fortinet\SslvpnClient\FortiSSLVPNcli.exe

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
| `FORTICLIENT_PATH`| *(Yalnızca Windows)* `FortiSSLVPNcli.exe` dosyasının sistemdeki tam yolu | `C:\Program Files (x86)\...` |

---

## Güvenlik Notu

- Kendi gerçek kullanıcı adı ve şifrelerinizin yer aldığı `.env` dosyası **`.gitignore`** dosyası ile korunmaktadır.
- Projeyi GitHub'a gönderirken **kesinlikle `.env` dosyasını commit etmeyin**, yalnızca `.env.example` şablon dosyasını paylaşın.

---

## Lisans

Bu proje [MIT Lisansı](LICENSE) kapsamında açık kaynak olarak sunulmaktadır.
