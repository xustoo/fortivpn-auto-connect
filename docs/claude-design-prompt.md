# Claude Design Prompt — FortiVPN Desktop Redesign

> Kullanım: Claude Design'a iki görseli ekle (1: Nano VPN referansı, 2: bina fotoğrafı), aşağıdaki "PROMPT" bölümünün tamamını yapıştır.

---

## PROMPT

You are a senior product designer. Redesign the desktop UI of **FortiVPN**, a small internal tool that connects to a FortiGate SSL-VPN and automatically fetches the 2FA token from a mailbox (IMAP). Deliver a high-fidelity, pixel-precise design (all three screens, all states) plus a short design-language spec I can hand to a developer.

### Attached references
1. **Image 1 – Nano VPN (layout/interaction reference).** Take from it: one dominant, glowing circular power button as the hero of the screen; a slim vertical icon rail on the left; a big status/timer readout above the button; calm dark surface; soft glow only around the hero element; compact secondary information. Do NOT copy its world map, flags, speed graphs, pricing, or green-only palette.
2. **Image 2 – Glass skyscraper corner, shot from below (background reference).** Use it as the window's backdrop, see "Background" below.

### Product context (keep real, don't invent features)
- Audience: employees of Kolaysoft (professional/enterprise context). Language of all UI copy: **Turkish**.
- Core job: **one click → connected.** The app logs in, waits for the 2FA mail, reads the code, completes the tunnel, and shows a connection timer. Everything else is secondary.
- Platforms: **Windows 11 and macOS**. The design must look native-appropriate on both: use the system font stack (Segoe UI Variable / SF Pro Text), system monospace for logs (Cascadia Mono / SF Mono–Menlo), no platform-specific chrome assumptions. Design the window contents only; show a plain neutral title bar so either OS can supply its own.
- Implementation: it will be built as **plain HTML + CSS + vanilla JS (no framework, no build step)** inside a **pywebview** window (WebView2 on Windows, WKWebView on macOS; Python backend exposes `connect()`, `disconnect()`, `get_config()`, `save_config()` and pushes status/log/token events to JS). Deliver the design as **a working static prototype**: `index.html`, `styles.css`, `app.js`, plus assets, with all three screens and every state switchable (e.g. a hidden `?state=` query param or a small dev switcher). Constraints and freedoms:
  - Allowed: CSS variables as design tokens, `backdrop-filter` blur (keep it subtle; must degrade gracefully to a solid fill), box-shadows, gradients, SVG icons (inline), CSS keyframe animations, `prefers-reduced-motion` support.
  - Not allowed: external CDNs, web fonts fetched at runtime (use the system font stack; if a custom font is essential, ship it locally as woff2), JS frameworks, anything needing network access (the app is often used before the VPN is up).
  - Cross-platform: no layout or font assumptions that break on either OS; test mentally at 100% and 125%/150% Windows scaling and macOS Retina.
  - Window is frameless-or-native: design for a native title bar by default, and show the optional custom drag-region variant separately.
  - Export the background as an optimized `bg.jpg`/`bg.webp` (under 200 KB) and compose the shadow/vignette in CSS on top of it, so strength can be tuned with a single CSS variable.

### Window
- **Fixed size, not resizable: 720 × 460 px** (Nano VPN is ≈ 4:3 and larger; ours is slightly smaller and wider-than-tall). Design at 1x and note 2x export. Give a 76px left rail + 644px content area grid, 24px outer padding, 8px spacing unit.

### Background (important)
- Use the building photo as the full-window backdrop of the **Bağlan (Connect)** screen, as a subtle texture, not a wallpaper:
  - Recolor to the app's palette (deep navy → petrol/teal-blue tint), desaturate, ~12–18% visible strength.
  - Add a **soft shadow overlay**: a dark vertical gradient (top ≈ 55% opacity → bottom ≈ 85%) plus a radial vignette so edges fall into shadow and the center behind the power button stays calm.
  - The V-shaped building corner should sit behind/above the hero button so the converging lines lead the eye to it. The pattern must never reduce text contrast below WCAG AA (4.5:1 for body, 3:1 for large text).
  - On Günlük and Ayarlar screens, use the same image at a much lower strength (~6–8%) so the app feels like one space but data stays readable.
  - Rail and cards sit on top as dark "frosted" glass panels (translucent fill + subtle `backdrop-filter: blur`, with a solid-color fallback, 1px low-contrast border), as in Nano VPN's side card.

### Visual language
- Mood: **calm, secure, corporate, premium** — think a modern security product, not a gaming VPN. Restrained, lots of negative space, one accent.
- Palette (propose final hex, keep it to these roles):
  - Background base: very dark navy (≈ #0B1220 – #0E1726)
  - Surface/panel: slightly lighter navy (≈ #131C2E) with 1px border (≈ #22304A)
  - Text primary / secondary / muted
  - **Accent (brand/idle/action): cool blue-cyan** derived from the building photo (≈ #4C9AFF – #5BB8FF)
  - **Success (connected): emerald** (≈ #34D399) — used for the connected glow
  - Warning (retrying / waiting for 2FA): amber
  - Danger (error / disconnect): soft red
  - Existing app uses a Catppuccin-like palette (#181825, #24273a, #8aadf4, #a6da95, #ed8796, #eed49f, #c6a0f6); replace it with the new cohesive system, but keep the semantic mapping blue=working, green=connected, yellow=waiting, red=error, purple=2FA token.
- Type: 3 sizes of hierarchy maximum per screen. Timer in large tabular/monospaced-figure numerals (≈ 40px, light/medium weight). Labels in 11px uppercase with +6% tracking. Body 13px.
- Elevation: communicate by tone and 1px borders, not heavy shadows. Glow only on the power button and the active rail item.
- Motion notes (implement as CSS keyframes, honoring `prefers-reduced-motion`): idle ring breathes slowly; connecting = rotating arc; 2FA scanning = pulsing dots; connected = steady emerald glow + a one-time ripple.

### Screens (design all, every state)

**1. Bağlan (Connect) — home, the "one-click" screen**
- Top-left: small wordmark “FortiVPN” + subtitle “Kolaysoft • İki Aşamalı Doğrulama (2FA)”. Top-right: status pill.
- Center hero: **large circular power button (≈ 150px diameter, ring + glow ≈ 210px)**. Single click toggles: connect when off, disconnect when on (long label under it: “Bağlanmak için dokunun” / “Bağlantıyı kesmek için dokunun”). No separate Connect/Disconnect buttons.
- Above the button: status text and big timer `00:45:29` (label “Bağlantı süresi”; when not connected show `00:00:00` in muted tone).
- Below the button, one slim info row of 3 compact chips: **Sunucu** (vpn.kolaysoft.com.tr:10321), **Kullanıcı** (kullanıcı adı), **2FA kodu** (last code in purple monospace, source e.g. “E-postadan alındı”, time `14:32:07`, small copy icon). Parola is NOT shown on this screen (moves to Ayarlar, masked) — less clutter, more security.
- States to render as separate frames:
  1. Bağlantı Kesildi (idle, accent-blue ring, red-tinted pill)
  2. Hazırlanıyor… / Bağlanıyor… (rotating arc, blue)
  3. 2FA Taranıyor… (amber, scanning dots, “E-posta kutusu kontrol ediliyor”)
  4. Bağlandı (emerald glow, timer running)
  5. Yeniden Bağlanılıyor… (amber)
  6. Hata (e.g. “2FA Alınamadı”, “Giriş Başarısız”, “Yönetici Yetkisi Gerekli”, “Hatalı Mac Parolası”): red ring + one-line human explanation + a text action “Günlüğü aç” that jumps to Günlük.

**2. Günlük (Logs) — separate screen, reached from the rail**
- Full-height log view in a dark panel. Header: title “Olay Günlüğü”, live-status dot, and actions on the right: **Temizle**, **Kopyala**, (optional) **Dışa aktar**.
- Filter segmented control: Tümü · Başarılı · Uyarı · Hata · 2FA.
- Each line: `HH:MM:SS` muted timestamp column, a 6px colored level dot, then the message in mono. Color mapping: success green, error red, warning amber, token/2FA purple, default neutral. Show ~14 realistic Turkish sample lines (e.g. “Sunucuya bağlanılıyor…”, “2FA kodu alındı: 482915”, “Tünel kuruldu”, “Canlılık ping’i başarısız (2/3)”).
- Empty state: “Henüz kayıt yok”. Auto-scroll indicator / “Sona git” pill when user scrolled up.

**3. Ayarlar (Settings)**
- Replaces the current popup dialog; it is now a screen in the same window (no scroll if possible; if not, a single clean scroll region).
- Grouped cards: **VPN** (Sunucu Host:Port, Kullanıcı adı, Parola [masked + göster/gizle]), **E-posta (2FA)** (IMAP sunucusu, Port SSL, E-posta, Parola), **Gelişmiş** (Canlılık ping hedefi; on Windows: openconnect.exe yolu, Sunucu sertifikası; on macOS: Sudo parolası). Show the **Windows variant** as the main design and a short note/frame for the macOS variant of the Gelişmiş group.
- Inputs: 36px tall, dark filled, 1px border, accent focus ring, label above in 11px uppercase muted, helper text where the existing label has hints (“boşsa PATH’te aranır”).
- Sticky footer: primary **Kaydet** button + secondary “Vazgeç”. Include saved-confirmation state (inline toast “Ayarlar kaydedildi”, not a modal).

### Navigation
- Slim **left icon rail** (76px) like Nano VPN: three items — **Bağlan** (shield/power), **Günlük** (list/terminal), **Ayarlar** (gear) — icon + 10px label, active item has accent glow bar + tinted background. Footer of rail: tiny connection-status dot and app version `v1.x`. Use one consistent outline icon set (2px stroke, 24px grid).

### Deliverables
1. All frames above at 720×460 (1x), plus one 2x export check.
2. A **design-language sheet**: color tokens (hex + role), type scale, spacing/radius scale (suggest 8/12/16 radii), button variants (primary, secondary, ghost, danger), input, pill, chip, rail item, toast, log row.
3. A **JS bridge contract** (short table): the functions the UI calls on Python (`pywebview.api.connect()` etc.) and the global callbacks Python will call on the UI (`onStatus(text, level)`, `onLog(line, level)`, `onToken(code, time)`, `onConnected()`, `onDisconnected()`), with the payload shape of each. Status `level` ∈ `idle | working | waiting | connected | error`; the UI must derive all colors from that level via a `data-state` attribute on `<body>`, never from colors sent by Python.
4. Accessibility check: contrast ratios for text on each surface, focus states for keyboard navigation, colour is never the only state indicator (status always has text + icon).

### Quality bar / do-nots
- Professional enough to show to a CIO; stylish enough to feel current. No neon overload, no gradients on text, no skeuomorphism, no emoji, no stock “hacker” imagery, no world map, no fake stats/graphs/speed meters (the app does not measure them).
- Keep information density low on the home screen: hero button + timer + 3 chips. That is it.
- Every pixel value, color, and spacing must be explicit so the developer can reproduce it without guessing.
