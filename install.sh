#!/usr/bin/env bash
# =============================================================================
# FortiVPN Auto-Connect Otomatik Kurulum Aracı (macOS / Linux)
# =============================================================================

set -e

# Renk Tanımlamaları
CLR_RESET="\033[0m"
CLR_BOLD="\033[1m"
CLR_BLUE="\033[1;34m"
CLR_GREEN="\033[1;32m"
CLR_YELLOW="\033[1;33m"
CLR_RED="\033[1;31m"
CLR_CYAN="\033[1;36m"

print_header() {
    echo -e "\n${CLR_BLUE}====================================================${CLR_RESET}"
    echo -e "${CLR_BOLD}   FortiVPN Auto-Connect - Otomatik Kurulum Sihirbazı${CLR_RESET}"
    echo -e "${CLR_BLUE}====================================================${CLR_RESET}\n"
}

print_info() {
    echo -e "${CLR_CYAN}[INFO]${CLR_RESET} $1"
}

print_success() {
    echo -e "${CLR_GREEN}[BASARILI]${CLR_RESET} $1"
}

print_warning() {
    echo -e "${CLR_YELLOW}[UYARI]${CLR_RESET} $1"
}

print_error() {
    echo -e "${CLR_RED}[HATA]${CLR_RESET} $1"
}

print_header

REPO_URL="https://github.com/xustoo/fortivpn-auto-connect.git"
OS_TYPE="$(uname -s)"

# 1. Hedef Dizin Belirleme
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "")"

if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/main.py" ] && [ -f "$SCRIPT_DIR/vpn_worker.py" ]; then
    INSTALL_DIR="$SCRIPT_DIR"
    print_info "Mevcut proje dizininde kurulum yapılıyor: $INSTALL_DIR"
else
    if [ -d "$HOME/Desktop" ]; then
        INSTALL_DIR="$HOME/Desktop/FortiVPN"
    else
        INSTALL_DIR="$HOME/FortiVPN"
    fi
    print_info "Hedef kurulum dizini: $INSTALL_DIR"

    if [ -d "$INSTALL_DIR/.git" ]; then
        print_info "Mevcut repo güncelleniyor..."
        git -C "$INSTALL_DIR" pull origin main || true
    else
        print_info "Proje GitHub'dan klonlanıyor..."
        if ! command -v git &>/dev/null; then
            print_error "Git sistemde bulunamadı. Lütfen önce Git'i kurun."
            exit 1
        fi
        git clone "$REPO_URL" "$INSTALL_DIR"
    fi
fi

cd "$INSTALL_DIR"

# 2. İşletim Sistemi ve Paket Yöneticisi Kontrolleri
print_info "Sistem gereksinimleri denetleniyor..."

if [ "$OS_TYPE" = "Darwin" ]; then
    # Homebrew Kontrolü
    if ! command -v brew &>/dev/null; then
        if [ -x "/opt/homebrew/bin/brew" ]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        elif [ -x "/usr/local/bin/brew" ]; then
            eval "$(/usr/local/bin/brew shellenv)"
        fi
    fi

    if ! command -v brew &>/dev/null; then
        print_warning "Homebrew tespit edilemedi."
        echo "openfortivpn ve Python kurulumu için Homebrew gereklidir."
        echo "Yüklemek için terminalde şu komutu çalıştırabilirsiniz:"
        echo '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    fi

    # openfortivpn Kontrolü
    if ! command -v openfortivpn &>/dev/null && [ ! -f "/opt/homebrew/bin/openfortivpn" ] && [ ! -f "/usr/local/bin/openfortivpn" ]; then
        print_info "openfortivpn kuruluyor..."
        if command -v brew &>/dev/null; then
            brew install openfortivpn
            print_success "openfortivpn başarıyla kuruldu."
        else
            print_error "openfortivpn bulunamadı ve Homebrew yüklü değil."
            print_error "Lütfen manuel olarak 'brew install openfortivpn' çalıştırın."
        fi
    else
        print_success "openfortivpn mevcut."
    fi

elif [ "$OS_TYPE" = "Linux" ]; then
    if ! command -v openfortivpn &>/dev/null; then
        print_info "Linux paket yöneticisi ile openfortivpn kuruluyor..."
        if command -v apt-get &>/dev/null; then
            sudo apt-get update && sudo apt-get install -y openfortivpn
        elif command -v dnf &>/dev/null; then
            sudo dnf install -y openfortivpn
        elif command -v pacman &>/dev/null; then
            sudo pacman -S --noconfirm openfortivpn
        fi
    fi
fi

# 3. Python 3 Kontrolü
PYTHON_BIN=""
for py_candidate in python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
    if command -v "$py_candidate" &>/dev/null; then
        PYTHON_BIN="$py_candidate"
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    print_error "Python 3 sistemde bulunamadı!"
    if [ "$OS_TYPE" = "Darwin" ] && command -v brew &>/dev/null; then
        print_info "Python 3 Homebrew üzerinden yükleniyor..."
        brew install python
        PYTHON_BIN="python3"
    else
        print_error "Lütfen Python 3 kurup betiği tekrar çalıştırın."
        exit 1
    fi
fi

PY_VER="$("$PYTHON_BIN" --version 2>&1)"
print_success "Python algılandı: $PY_VER ($PYTHON_BIN)"

# 4. İzole Python Sanal Ortamı (Virtualenv) Kurulumu
VENV_DIR="$INSTALL_DIR/.venv"
if [ ! -f "$VENV_DIR/bin/python3" ]; then
    print_info "İzole Python sanal ortamı oluşturuluyor (.venv)..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

print_info "Gerekli Python kütüphaneleri yükleniyor..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
if [ -f "$INSTALL_DIR/requirements.txt" ]; then
    "$VENV_DIR/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"
fi
print_success "Tüm Python bağımlılıkları eksiksiz kuruldu."

# 5. Yapılandırma Dosyası (.env) Kontrolü
if [ ! -f "$INSTALL_DIR/.env" ]; then
    if [ -f "$INSTALL_DIR/.env.example" ]; then
        cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
        print_info "Varsayılan .env yapılandırma şablonu oluşturuldu."
    fi
else
    print_success "Mevcut .env yapılandırma dosyası korundu."
fi

# 6. macOS Başlatıcıları ve Kısayolların Oluşturulması
if [ "$OS_TYPE" = "Darwin" ]; then
    print_info "macOS uygulama başlatıcıları yapılandırılıyor..."

    # FortiVPN_Baslat.command oluştur
    LAUNCHER_CMD="$INSTALL_DIR/FortiVPN_Baslat.command"
    cat <<LAUNCHER_EOF > "$LAUNCHER_CMD"
#!/usr/bin/env bash
cd "$INSTALL_DIR" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:\$PATH"
exec "$INSTALL_DIR/.venv/bin/python3" main.py
LAUNCHER_EOF
    chmod +x "$LAUNCHER_CMD"

    # Masaüstüne doğrudan kısayol kopyala (eğer kurulum Masaüstü harici bir dizindeyse)
    if [ "$INSTALL_DIR" != "$HOME/Desktop/FortiVPN" ] && [ -d "$HOME/Desktop" ]; then
        DESKTOP_CMD="$HOME/Desktop/FortiVPN_Baslat.command"
        cp "$LAUNCHER_CMD" "$DESKTOP_CMD"
        chmod +x "$DESKTOP_CMD"
    fi

    # FortiVPN.app Paketi Hazırla
    APP_DIR="$INSTALL_DIR/FortiVPN.app"
    mkdir -p "$APP_DIR/Contents/MacOS"
    mkdir -p "$APP_DIR/Contents/Resources"

    cat <<PLIST_EOF > "$APP_DIR/Contents/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>FortiVPN</string>
    <key>CFBundleIdentifier</key>
    <string>com.kolaysoft.fortivpn</string>
    <key>CFBundleName</key>
    <string>FortiVPN</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>2.0.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST_EOF

    cat <<APP_EXEC_EOF > "$APP_DIR/Contents/MacOS/FortiVPN"
#!/usr/bin/env bash
DIR="$INSTALL_DIR"
cd "\$DIR" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:\$PATH"
exec "\$DIR/.venv/bin/python3" main.py
APP_EXEC_EOF
    chmod +x "$APP_DIR/Contents/MacOS/FortiVPN"

    # Kullanıcının Masaüstüne FortiVPN.app kısayolunu/paketini yerleştir
    if [ -d "$HOME/Desktop" ] && [ "$APP_DIR" != "$HOME/Desktop/FortiVPN.app" ]; then
        rm -rf "$HOME/Desktop/FortiVPN.app" 2>/dev/null || true
        cp -R "$APP_DIR" "$HOME/Desktop/FortiVPN.app"
    fi

    print_success "Masaüstü başlatıcısı hazırlandı: FortiVPN.app ve FortiVPN_Baslat.command"
fi

# 7. Kurulum Tamamlandı
echo -e "\n${CLR_GREEN}====================================================${CLR_RESET}"
echo -e "${CLR_BOLD}   FortiVPN Kurulumu Başarıyla Tamamlandı!          ${CLR_RESET}"
echo -e "${CLR_GREEN}====================================================${CLR_RESET}\n"

echo -e "Uygulamayı başlatmak için:"
if [ "$OS_TYPE" = "Darwin" ]; then
    echo -e "  1. Masaüstündeki ${CLR_CYAN}FortiVPN.app${CLR_RESET} veya ${CLR_CYAN}FortiVPN_Baslat.command${CLR_RESET} dosyasına çift tıklayın."
    echo -e "  2. Veya terminalden doğrudan çalıştırmak için:"
    echo -e "     ${CLR_BOLD}cd \"$INSTALL_DIR\" && .venv/bin/python3 main.py${CLR_RESET}\n"
else
    echo -e "  Terminalden çalıştırmak için:"
    echo -e "     ${CLR_BOLD}cd \"$INSTALL_DIR\" && .venv/bin/python3 main.py${CLR_RESET}\n"
fi
