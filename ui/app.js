/* FortiVPN UI — vanilla JS, no build step.
   Python → UI: window.onStatus / onLog / onToken / onConnected / onDisconnected
   UI → Python: pywebview.api.connect / disconnect / get_config / save_config (+ optional export_log) */
(function () {
  "use strict";

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const body = document.body;
  const q = new URLSearchParams(location.search);

  /* ---------- Copy ---------- */
  const PHASES = {
    idle:         { level: "idle",      pill: "Bağlantı Kesildi",      icon: "i-x-circle",    line: "Bağlı değil",                        hint: "Bağlanmak için dokunun",        aria: "Bağlan" },
    preparing:    { level: "working",   pill: "Hazırlanıyor…",         icon: "i-loader",      line: "Yapılandırma okunuyor",              hint: "İptal etmek için dokunun",      aria: "Bağlantıyı iptal et" },
    connecting:   { level: "working",   pill: "Bağlanıyor…",           icon: "i-loader",      line: "Sunucuya giriş yapılıyor",           hint: "İptal etmek için dokunun",      aria: "Bağlantıyı iptal et" },
    scan2fa:      { level: "waiting",   pill: "2FA Taranıyor…",        icon: "i-mail",        line: "E-posta kutusu kontrol ediliyor",    hint: "İptal etmek için dokunun",      aria: "Bağlantıyı iptal et" },
    connected:    { level: "connected", pill: "Bağlandı",              icon: "i-check-circle",line: "Güvenli tünel etkin",                hint: "Bağlantıyı kesmek için dokunun", aria: "Bağlantıyı kes" },
    reconnecting: { level: "waiting",   pill: "Yeniden Bağlanılıyor…", icon: "i-refresh",     line: "Bağlantı koptu · yeniden deneniyor", hint: "İptal etmek için dokunun", aria: "Yeniden bağlanmayı iptal et" },
    error:        { level: "error",     pill: "Hata",                  icon: "i-alert",       line: "2FA Alınamadı",                      hint: "",                              aria: "Tekrar dene" }
  };
  const LEVEL_DEFAULT_PHASE = { idle: "idle", working: "connecting", waiting: "scan2fa", connected: "connected", error: "error" };
  const ERRORS = {
    "2fa":   { title: "2FA Alınamadı",            text: "Doğrulama e-postası beklenen sürede gelmedi." },
    login:   { title: "Giriş Başarısız",          text: "Sunucu kullanıcı adını veya parolayı reddetti." },
    admin:   { title: "Yönetici Yetkisi Gerekli", text: "Tüneli kurmak için uygulamayı yönetici olarak başlatın." },
    macpw:   { title: "Hatalı Mac Parolası",      text: "Sudo parolası doğrulanamadı. Ayarlar’dan güncelleyin." },
    openconnect:  { title: "openconnect Bulunamadı",  text: "openconnect.exe bulunamadı. Kurulum.bat ile kurun veya Ayarlar’dan yolunu belirtin." },
    openfortivpn: { title: "openfortivpn Bulunamadı", text: "openfortivpn bulunamadı. Homebrew ile kurun: brew install openfortivpn" }
  };

  const SAMPLE_LOG = [
    ["14:31:52", "info",    "FortiVPN başlatıldı (v1.4)"],
    ["14:31:52", "info",    "Ayarlar yüklendi"],
    ["14:31:58", "info",    "Sunucuya bağlanılıyor… vpn.example.com:10321"],
    ["14:31:59", "success", "Giriş bilgileri kabul edildi"],
    ["14:31:59", "warning", "2FA kodu bekleniyor"],
    ["14:32:00", "info",    "IMAP oturumu açıldı (imap.example.com:993)"],
    ["14:32:07", "token",   "2FA kodu alındı: 482915"],
    ["14:32:07", "info",    "Kod sunucuya gönderildi"],
    ["14:32:09", "success", "Tünel kuruldu"],
    ["14:32:09", "info",    "Canlılık ping’i başlatıldı (10.10.0.1)"],
    ["14:58:40", "warning", "Canlılık ping’i başarısız (1/3)"],
    ["14:59:10", "warning", "Canlılık ping’i başarısız (2/3)"],
    ["14:59:40", "success", "Canlılık ping’i yanıt verdi"],
    ["15:06:12", "error",   "IMAP oturumu zaman aşımına uğradı, yeniden açılacak"]
  ];

  /* ---------- State ---------- */
  const S = {
    phase: "idle",
    error: "2fa",
    seconds: 0,
    timer: null,
    logs: [],
    filter: "all",
    follow: true,
    config: null
  };

  /* ---------- Helpers ---------- */
  const pad = n => String(n).padStart(2, "0");
  const fmt = s => pad(Math.floor(s / 3600)) + ":" + pad(Math.floor(s / 60) % 60) + ":" + pad(s % 60);
  const now = () => { const d = new Date(); return pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds()); };
  const api = () => (window.pywebview && window.pywebview.api) || Mock;

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) return navigator.clipboard.writeText(text).catch(() => legacyCopy(text));
    legacyCopy(text); return Promise.resolve();
  }
  function legacyCopy(text) {
    const t = document.createElement("textarea");
    t.value = text; t.style.position = "fixed"; t.style.opacity = "0";
    document.body.appendChild(t); t.select();
    try { document.execCommand("copy"); } catch (e) {}
    t.remove();
  }

  /* ---------- Navigation ---------- */
  function go(screen) {
    body.dataset.screen = screen;
    $$(".rail-item").forEach(b => { if (b.dataset.go === screen) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current"); });
    if (screen === "log") scrollLogEnd();
  }
  document.addEventListener("click", e => {
    const t = e.target.closest("[data-go]");
    if (t) go(t.dataset.go);
  });
  document.addEventListener("keydown", e => {
    if ((e.ctrlKey || e.metaKey) && !e.shiftKey && ["1", "2", "3"].includes(e.key)) {
      e.preventDefault(); go(["connect", "log", "settings"][+e.key - 1]);
    }
    if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "d") { $("#devbar").hidden = !$("#devbar").hidden; }
  });

  /* ---------- Status ---------- */
  function setPhase(phase, opts = {}) {
    const prev = S.phase;
    const p = PHASES[phase] || PHASES.idle;
    S.phase = phase;
    body.dataset.state = p.level;
    body.dataset.phase = phase;

    let line = opts.text || p.line;
    if (phase === "error") {
      // Kodsuz ama metinli hata (bilinmeyen durum) eski S.error ile "2FA Alınamadı" demesin.
      const er = ERRORS[opts.code || (opts.text ? null : S.error)] || { title: opts.title || "Hata", text: opts.text || "" };
      if (opts.code) S.error = opts.code;
      line = er.title;
      $("#errText").textContent = opts.code || !opts.text ? er.text : opts.text;
      $("#errText").title = $("#errText").textContent;
    }
    $("#pillText").textContent = p.pill;
    $("#pillIcoUse").setAttribute("href", "#" + p.icon);
    $("#statusLine").textContent = line;
    $("#hint").textContent = p.hint;
    $("#powerBtn").setAttribute("aria-label", p.aria);
    $("#railDot").setAttribute("aria-label", p.pill);
    $("#railDot").title = p.pill;

    if (p.level === "connected") {
      startTimer();
      if (prev !== "connected" && !opts.silent) ripple();
    } else {
      stopTimer();
      if (p.level === "idle") { S.seconds = 0; renderTimer(); }
    }
  }
  function renderTimer() { $("#timer").textContent = fmt(S.seconds); }
  function startTimer() {
    renderTimer();
    if (S.timer) return;
    S.timer = setInterval(() => { S.seconds++; renderTimer(); }, 1000);
  }
  function stopTimer() { clearInterval(S.timer); S.timer = null; }
  function ripple() {
    const r = $("#ripple");
    r.classList.remove("is-go"); void r.offsetWidth; r.classList.add("is-go");
  }

  /* ---------- Power button ---------- */
  $("#powerBtn").addEventListener("click", () => {
    const lvl = body.dataset.state;
    if (lvl === "idle" || lvl === "error") {
      setPhase("preparing");
      Promise.resolve(api().connect()).catch(err => setPhase("error", { text: String(err) }));
    } else {
      Promise.resolve(api().disconnect());
      window.onDisconnected();
    }
  });

  /* ---------- Token chip ---------- */
  function setToken(code, time, source) {
    const chip = $(".chip-token");
    chip.classList.toggle("is-empty", !code);
    $("#tokenCode").textContent = code || "——————";
    $("#tokenTime").textContent = time || "—";
    $("#tokenSrc").textContent = code ? (source || "E-postadan alındı") : "Henüz alınmadı";
  }
  $("#copyToken").addEventListener("click", () => {
    const code = $("#tokenCode").textContent.trim();
    if (!/^\d+$/.test(code)) return;
    copyText(code).then(() => flashIcon($("#copyToken")));
  });
  function flashIcon(btn) {
    const use = btn.querySelector("use"); const old = use.getAttribute("href");
    use.setAttribute("href", "#i-check"); btn.classList.add("is-done");
    setTimeout(() => { use.setAttribute("href", old); btn.classList.remove("is-done"); }, 1400);
  }

  /* ---------- Log ---------- */
  const logEl = $("#logScroll");
  function rowHTML(l) {
    const esc = s => s.replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
    return '<div class="log-row" data-lv="' + l.lv + '"><span class="log-ts">' + l.ts + '</span><i class="lv lv-' + l.lv + '"></i><span class="log-msg">' + esc(l.msg) + "</span></div>";
  }
  function visible(l) { return S.filter === "all" || l.lv === S.filter; }
  function renderLog() {
    const rows = S.logs.filter(visible);
    logEl.innerHTML = rows.map(rowHTML).join("");
    $("#screen-log").classList.toggle("is-empty", rows.length === 0);
    $("#logEmpty .empty-title").textContent = S.logs.length ? "Bu filtrede kayıt yok" : "Henüz kayıt yok";
    $("#logEmpty .empty-sub").textContent = S.logs.length ? "Başka bir filtre seçin." : "Bağlantı başladığında olaylar burada görünür.";
    if (S.follow) scrollLogEnd();
  }
  function pushLog(msg, lv, ts) {
    const l = { ts: ts || now(), lv: normLevel(lv), msg: String(msg) };
    S.logs.push(l);
    if (S.logs.length > 2000) S.logs.shift();
    if (!visible(l)) return;
    $("#screen-log").classList.remove("is-empty");
    logEl.insertAdjacentHTML("beforeend", rowHTML(l));
    if (S.follow) scrollLogEnd(); else $("#logJump").classList.add("is-on");
  }
  function normLevel(lv) {
    return { success: "success", ok: "success", warning: "warning", warn: "warning", error: "error", token: "token", "2fa": "token" }[lv] || "info";
  }
  function scrollLogEnd() { if (S.pinned) return; logEl.scrollTop = logEl.scrollHeight; S.follow = true; $("#logJump").classList.remove("is-on"); }
  logEl.addEventListener("scroll", () => {
    if (S.pinned && logEl.scrollTop < 4) return;
    S.pinned = false;
    const atEnd = logEl.scrollHeight - logEl.scrollTop - logEl.clientHeight < 8;
    S.follow = atEnd;
    $("#logJump").classList.toggle("is-on", !atEnd);
  });
  $("#logJump").addEventListener("click", () => { S.pinned = false; scrollLogEnd(); });
  $$("#logFilter .seg-item").forEach(b => b.addEventListener("click", () => {
    S.filter = b.dataset.f;
    $$("#logFilter .seg-item").forEach(x => x.setAttribute("aria-checked", String(x === b)));
    S.follow = true; renderLog();
  }));
  $("#logFilter").addEventListener("keydown", e => {
    if (!["ArrowLeft", "ArrowRight"].includes(e.key)) return;
    const items = $$("#logFilter .seg-item"); const i = items.indexOf(document.activeElement);
    const n = items[(i + (e.key === "ArrowRight" ? 1 : items.length - 1)) % items.length];
    n.focus(); n.click();
  });
  const logText = () => S.logs.map(l => l.ts + "  " + l.lv.toUpperCase().padEnd(7) + " " + l.msg).join("\n");
  $("#logClear").addEventListener("click", () => { S.logs = []; renderLog(); });
  $("#logCopy").addEventListener("click", () => copyText(logText()).then(() => {
    $("#logCopyText").textContent = "Kopyalandı"; setTimeout(() => $("#logCopyText").textContent = "Kopyala", 1400);
  }));
  $("#logExport").addEventListener("click", () => {
    const a = api();
    if (a.export_log) return a.export_log(logText());
    const url = URL.createObjectURL(new Blob([logText()], { type: "text/plain;charset=utf-8" }));
    const el = Object.assign(document.createElement("a"), { href: url, download: "fortivpn-gunluk.txt" });
    document.body.appendChild(el); el.click(); el.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  });

  /* ---------- Settings ---------- */
  const form = $("#settingsForm");
  const FIELDS = ["server", "user", "password", "imap_host", "imap_port", "email", "email_password", "ping_target", "openconnect_path", "server_cert", "sudo_password"];
  function fillForm(cfg) {
    S.config = Object.assign({}, cfg);
    FIELDS.forEach(k => { const el = form.elements[k]; if (el && cfg[k] != null) el.value = cfg[k]; });
    $("#chipServer").textContent = cfg.server || "—"; $("#chipServer").title = cfg.server || "";
    $("#chipUser").textContent = cfg.user || "—";
  }
  function readForm() {
    const o = {}; FIELDS.forEach(k => { const el = form.elements[k]; if (el) o[k] = el.value.trim(); });
    o.imap_port = parseInt(o.imap_port, 10) || 993;
    return o;
  }
  $$(".reveal").forEach(b => b.addEventListener("click", () => {
    const inp = document.getElementById(b.dataset.reveal);
    const show = inp.type === "password";
    inp.type = show ? "text" : "password";
    b.querySelector("use").setAttribute("href", show ? "#i-eye-off" : "#i-eye");
    b.setAttribute("aria-label", show ? "Parolayı gizle" : "Parolayı göster");
    b.title = show ? "Gizle" : "Göster";
  }));
  let toastT;
  function toast(text, isError) {
    const t = $("#toast");
    $("#toastText").textContent = text;
    t.classList.toggle("is-error", !!isError);
    t.querySelector("use").setAttribute("href", isError ? "#i-alert" : "#i-check-circle");
    t.classList.add("is-on");
    clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove("is-on"), 2600);
  }
  form.addEventListener("submit", e => {
    e.preventDefault();
    const cfg = readForm();
    const port = form.elements.imap_port;
    const badPort = !/^\d{1,5}$/.test(port.value.trim());
    port.setAttribute("aria-invalid", String(badPort));
    if (badPort) { port.focus(); return toast("Port geçersiz", true); }
    Promise.resolve(api().save_config(cfg)).then(r => {
      if (r && r.ok === false) return toast(r.error || "Kaydedilemedi", true);
      fillForm(cfg); toast("Ayarlar kaydedildi");
    }).catch(err => toast(String(err), true));
  });
  $("#btnCancel").addEventListener("click", () => { if (S.config) fillForm(S.config); go("connect"); });

  /* ---------- Window chrome (custom variant) ---------- */
  $("#tbMin").addEventListener("click", () => { const a = api(); a.minimize && a.minimize(); });
  $("#tbClose").addEventListener("click", () => { const a = api(); a.close && a.close(); });

  /* ---------- Python → UI ---------- */
  window.onStatus = function (text, level, phase) {
    const ph = PHASES[phase] ? phase : LEVEL_DEFAULT_PHASE[level] || "idle";
    if (ph === "error") setPhase("error", { code: ERRORS[phase] ? phase : null, text });
    else setPhase(ph, { text });
  };
  window.onError = function (code, text) { setPhase("error", { code, text }); };
  window.onLog = function (line, level, ts) { pushLog(line, level, ts); };
  window.onToken = function (code, time, source) { setToken(code, time, source); };
  window.onConnected = function (startedAtMs) {
    S.seconds = startedAtMs ? Math.max(0, Math.round((Date.now() - startedAtMs) / 1000)) : 0;
    setPhase("connected");
  };
  window.onDisconnected = function (reason) {
    if (reason) setPhase("error", { code: ERRORS[reason] ? reason : null, text: ERRORS[reason] ? null : reason });
    else setPhase("idle");
  };

  /* ---------- Mock backend (browser preview only) ---------- */
  const Mock = (function () {
    let timers = [];
    const later = (ms, fn) => timers.push(setTimeout(fn, ms));
    const cfg = {
      server: "vpn.example.com:10321", user: "ahmet.yilmaz", password: "Ornek2026!vpn",
      imap_host: "imap.example.com", imap_port: 993, email: "ahmet.yilmaz@example.com", email_password: "mailparolasi2026",
      ping_target: "10.10.0.1", openconnect_path: "", server_cert: "", sudo_password: ""
    };
    return {
      connect() {
        timers.forEach(clearTimeout); timers = [];
        onLog("Sunucuya bağlanılıyor… " + cfg.server, "info");
        later(700,  () => { onStatus("Sunucuya giriş yapılıyor", "working", "connecting"); });
        later(1700, () => { onLog("Giriş bilgileri kabul edildi", "success"); onLog("2FA kodu bekleniyor", "warning"); onStatus("E-posta kutusu kontrol ediliyor", "waiting", "scan2fa"); });
        later(4200, () => { const c = String(Math.floor(100000 + Math.random() * 900000)); onToken(c, now(), "E-postadan alındı"); onLog("2FA kodu alındı: " + c, "token"); });
        later(5000, () => { onLog("Tünel kuruldu", "success"); onConnected(); });
        return true;
      },
      disconnect() { timers.forEach(clearTimeout); timers = []; onLog("Bağlantı kullanıcı tarafından kesildi", "info"); return true; },
      get_config() { return Object.assign({}, cfg); },
      save_config(c) { Object.assign(cfg, c); return { ok: true }; }
    };
  })();

  /* ---------- Boot ---------- */
  function boot() {
    body.dataset.os = q.get("os") || (/Mac/i.test(navigator.platform) ? "mac" : "win");
    body.dataset.chrome = q.get("chrome") || "native";
    if (q.get("motion") === "off") body.dataset.motion = "off";

    Promise.resolve(api().get_config()).then(fillForm);

    const logMode = q.get("log");
    if (logMode !== "empty") SAMPLE_LOG.forEach(([ts, lv, msg]) => S.logs.push({ ts, lv, msg }));
    renderLog();

    const state = q.get("state") || "idle";
    if (q.get("error")) S.error = q.get("error");
    S.seconds = state === "connected" ? +(q.get("t") || 2729) : (state === "reconnecting" ? +(q.get("t") || 2729) : 0);
    if (state === "idle" || state === "preparing" || state === "connecting" || state === "scan2fa") setToken(q.get("token") === "none" ? null : "482915", "14:32:07");
    setPhase(state, { silent: true, code: state === "error" ? S.error : null });
    if (state !== "connected") renderTimer();

    go(q.get("screen") || "connect");
    if (logMode === "scrolled") {
      S.pinned = true;
      const hold = () => { S.follow = false; logEl.scrollTop = 0; $("#logJump").classList.add("is-on"); };
      requestAnimationFrame(hold); setTimeout(hold, 120); setTimeout(hold, 600);
    }
    if (q.get("filter")) { const b = $('#logFilter [data-f="' + q.get("filter") + '"]'); b && b.click(); }
    if (q.get("saved")) { toast("Ayarlar kaydedildi"); clearTimeout(toastT); }
    if (q.get("focus")) { const f = document.getElementById("f-" + q.get("focus")); f && f.classList.add("is-focus"); }
    if (q.get("reveal")) { const b = $('[data-reveal="f-' + q.get("reveal") + '"]'); b && b.click(); }

    // Dev switcher
    const dv = $("#devbar");
    if (q.get("dev")) dv.hidden = false;
    $("#dvScreen").value = body.dataset.screen; $("#dvState").value = state; $("#dvError").value = S.error;
    $("#dvOs").value = body.dataset.os; $("#dvChrome").value = body.dataset.chrome;
    $("#dvScreen").onchange = e => go(e.target.value);
    $("#dvState").onchange = e => { if (e.target.value === "connected") S.seconds = 2729; setPhase(e.target.value, { code: S.error }); };
    $("#dvError").onchange = e => { S.error = e.target.value; if (S.phase === "error") setPhase("error", { code: S.error }); };
    $("#dvOs").onchange = e => body.dataset.os = e.target.value;
    $("#dvChrome").onchange = e => body.dataset.chrome = e.target.value;
  }

  window.addEventListener("pywebviewready", () => Promise.resolve(api().get_config()).then(fillForm));
  boot();
})();
