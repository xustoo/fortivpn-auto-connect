# FortiVPN Auto-Connect

A desktop app that connects to a FortiGate SSL-VPN and handles two-factor
authentication for you. When the gateway asks for a one-time code, the app
reads it from your mailbox over IMAP and submits it, so you don't have to type it.

- **No FortiClient required.** Uses the open-source clients `openfortivpn`
  (macOS) and `openconnect` with `--protocol=fortinet` (Windows).
- **Automatic 2FA.** Watches your inbox (Carbonio, Zimbra or any IMAP server)
  for the authentication email, extracts the code, submits it and marks the
  message as read.
- **Ignores stale codes.** Codes that were already used are blocklisted, so an
  old email is never submitted. Slow mail delivery is handled with a
  configurable timeout.
- **Keep-alive.** Optionally monitors the tunnel and reconnects when it drops.
- **Status panel.** Shows the server, user, last 2FA code and connection uptime.
- **Cross-platform.** Runs on macOS and Windows.

## How It Works

1. The app starts `openfortivpn` or `openconnect` with your credentials.
2. When the gateway requests a token, it polls your mailbox over IMAPS for a
   new code that it has not used before.
3. The code is written to the VPN client's input and the email is marked as read.
4. If keep-alive is enabled, the app pings an internal host and restarts the
   tunnel after repeated failures.

## Installation

### macOS

```bash
curl -fsSL https://raw.githubusercontent.com/xustoo/fortivpn-auto-connect/main/install.sh | bash
```

The installer:

- installs `openfortivpn` and `python3` if they are missing;
- creates a virtual environment (`.venv`) and installs the Python dependencies;
- creates a `.env` file from `.env.example`;
- puts `FortiVPN.app` and `FortiVPN_Baslat.command` launchers on your desktop.

You can also clone the repository and double-click `Kurulum.command`.

### Windows

Run in PowerShell:

```powershell
irm https://raw.githubusercontent.com/xustoo/fortivpn-auto-connect/main/Windows/install.ps1 | iex
```

The installer:

- downloads the project to `Desktop\FortiVPN` (with `git clone`, or as a ZIP
  if Git is not installed);
- offers to install Python if it is missing (via `winget`, falling back to the
  official python.org installer);
- installs the Python dependencies;
- offers to install the `openconnect` CLI (v9.21, including the Wintun driver),
  showing the file size and SHA-256 hash before installing;
- registers a `FortiVPN-AutoConnect` scheduled task that runs the app with
  administrator rights;
- creates a `.env` file from `.env.example`;
- puts a `FortiVPN_Baslat.bat` launcher on your desktop.

Installing openconnect and registering the task happen in a single elevated
step, so Windows shows **one** UAC prompt during setup. If the prompt does not
appear, look for a flashing icon on the taskbar.

You can also clone the repository and run `Windows\Kurulum.bat` directly.

## Manual Installation

### macOS

```bash
brew install openfortivpn python
git clone https://github.com/xustoo/fortivpn-auto-connect.git
cd fortivpn-auto-connect
./install.sh
```

### Windows

```cmd
git clone https://github.com/xustoo/fortivpn-auto-connect.git
cd fortivpn-auto-connect
Windows\Kurulum.bat
```

If a step fails (for example, because a corporate network blocks a download),
install the components yourself:

- **Python 3.8+** from [python.org](https://www.python.org/downloads/).
  Select "Add Python to PATH" during installation.
- **openconnect CLI.** Note that OpenConnect-GUI (including
  `choco install openconnect-gui`) does not ship `openconnect.exe` and will not
  work. Download the official build from the openconnect GitLab CI:

  ```
  https://gitlab.com/openconnect/openconnect/-/jobs/artifacts/v9.21/raw/openconnect-installer-MinGW64-GnuTLS.exe?job=MinGW64%2FGnuTLS
  ```

  It installs to `C:\Program Files\OpenConnect\` by default. Add that folder to
  `PATH` or set `OPENCONNECT_EXE` in `.env`.

  This artifact link is tied to the `v9.21` tag and may expire. For a newer
  version, open the
  [openconnect pipelines](https://gitlab.com/openconnect/openconnect/-/pipelines)
  page and download the artifact of the `MinGW64/GnuTLS` job for the tag you want.

## Configuration

Settings are read from a `.env` file in the project root. The installers
create it for you. To create it manually:

```bash
cp .env.example .env
```

Example:

```ini
# VPN
VPN_SERVER=vpn.example.com:10321
VPN_USER=your_username
VPN_PASS=your_vpn_password

# Mail (IMAP over SSL)
IMAP_SERVER=mail.example.com
IMAP_PORT=993
IMAP_USER=you@example.com
IMAP_PASS=your_mail_password
MAIL_TIMEOUT=90

# Keep-alive (off is recommended unless you have a reliable internal host)
PING_TARGET=off

# macOS only: password used to run openfortivpn with sudo.
# Leave empty and the app asks for it on first launch.
MAC_SUDO_PASS=

# Windows only
OPENCONNECT_EXE=
VPN_SERVERCERT=
```

| Variable | Description | Example |
| :--- | :--- | :--- |
| `VPN_SERVER` | FortiGate gateway host and port | `vpn.example.com:10321` |
| `VPN_USER` | VPN username | `your_username` |
| `VPN_PASS` | VPN password | |
| `IMAP_SERVER` | Mail server that receives the 2FA email | `mail.example.com` |
| `IMAP_PORT` | IMAPS port | `993` |
| `IMAP_USER` | Mailbox that receives the 2FA email | `you@example.com` |
| `IMAP_PASS` | Mailbox password | |
| `MAIL_TIMEOUT` | Maximum time to wait for the 2FA email, in seconds | `90` |
| `PING_TARGET` | Internal IP to ping for keep-alive, or `off` to disable | `off` |
| `PING_INTERVAL` | Seconds between keep-alive pings | `15` |
| `MAX_PING_FAILS` | Consecutive failed pings before reconnecting | `3` |
| `RECONNECT_DELAY` | Seconds to wait before reconnecting | `15` |
| `TRUSTED_CERT` | *(macOS)* SHA-256 digest of the gateway certificate. Detected automatically if empty | |
| `MAC_SUDO_PASS` | *(macOS)* Your Mac user password, used to start `openfortivpn` | |
| `OPENCONNECT_EXE` | *(Windows)* Full path to `openconnect.exe`. Looked up in `PATH` if empty | `C:\Program Files\OpenConnect\openconnect.exe` |
| `VPN_SERVERCERT` | *(Windows)* Gateway certificate pin. Captured and saved on first connection if empty | `pin-sha256:...` |
| `VPNC_SCRIPT` | *(Windows)* Custom `vpnc-script` path passed to openconnect | |
| `VPN_EXTRA_ARGS` | *(Windows)* Extra arguments passed to openconnect | |

## Usage

### macOS

Use any of the following:

- double-click `FortiVPN.app`;
- double-click `FortiVPN_Baslat.command`;
- run `python3 main.py` from the project folder.

### Windows

Double-click `FortiVPN_Baslat.bat` on your desktop, or run:

```cmd
python main.py
```

openconnect needs administrator rights to create the Wintun network adapter.
The desktop launcher starts the app through the `FortiVPN-AutoConnect`
scheduled task, which already runs elevated, so no UAC prompt is shown. If the
task is missing or the app is started another way, the app relaunches itself
as administrator and Windows shows a UAC prompt.

## Project Structure

```text
fortivpn-auto-connect/
├── main.py                  # Desktop app: pywebview window and JS bridge to the VPN worker
├── vpn_worker.py            # VPN tunnel and process management
├── imap_client.py           # Mailbox polling and 2FA code extraction
├── core/
│   ├── config.py            # .env loading and saving
│   └── elevation.py         # Windows administrator elevation
├── ui/                      # Interface (plain HTML, CSS and JS)
├── install.sh               # macOS installer
├── Kurulum.command          # macOS installer (Finder double-click)
├── FortiVPN_Baslat.command  # macOS launcher
├── FortiVPN.app             # macOS app bundle
├── Windows/
│   ├── install.ps1          # Windows web installer
│   ├── Kurulum.bat          # Windows setup script
│   └── register_task.ps1    # Elevated setup step: openconnect install and scheduled task
├── requirements.txt
└── .env.example
```

## Security

- `.env` contains your VPN, mail and system passwords in plain text. Keep it
  private.
- `.env` is listed in `.gitignore`. Never commit it; share only `.env.example`.

## License

Released under the [MIT License](LICENSE).

## Credits

Background photo by [Allison Saeng](https://unsplash.com/@allisonsaeng) on [Unsplash](https://unsplash.com/photos/PjnV5hvsGzI), used under the [Unsplash License](https://unsplash.com/license). The image is not covered by this project's license.
