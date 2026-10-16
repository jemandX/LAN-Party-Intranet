(() => {
  "use strict";

  const API = "/api/state";
  const LS_KEY = "lanparty-state";
  const DEFAULT = {
    rev: 0,
    schedule: [
      { time: "12:00", title: "Aufwärmen (freies Spiel)" },
      { time: "13:00", title: "Hotdog-Pause" },
      { time: "14:00", title: "Runde 1" },
      { time: "15:30", title: "Pause" },
      { time: "16:00", title: "Runde 2" },
      { time: "17:30", title: "Finale" }
    ],
    rounds: 2,
    players: [
      { name: "Spieler 1", scores: [0, 0] },
      { name: "Spieler 2", scores: [0, 0] },
      { name: "Spieler 3", scores: [0, 0] }
    ],
    hotdogs: 0,
    info: "WLAN-Passwort, Server-IPs und Regeln hier eintragen."
  };

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s || "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const num = (v) => { const n = parseInt(v, 10); return Number.isFinite(n) ? n : 0; };

  let state = null;
  let online = false;
  let saveTimer = null;
  let pendingSave = false;
  let currentAccount = null;
  let sounds = [];

  function normalize(s) {
    s = s && typeof s === "object" ? s : JSON.parse(JSON.stringify(DEFAULT));
    s.schedule = Array.isArray(s.schedule) ? s.schedule : [];
    s.players = Array.isArray(s.players) ? s.players : [];
    s.rounds = Math.max(1, num(s.rounds) || 1);
    s.hotdogs = Math.max(0, num(s.hotdogs));
    s.info = typeof s.info === "string" ? s.info : "";
    s.players.forEach((p) => {
      p.scores = Array.isArray(p.scores) ? p.scores.map(num) : [];
      while (p.scores.length < s.rounds) p.scores.push(0);
    });
    return s;
  }

  function showMessage(message) {
    $("authMessage").textContent = message;
    if (message) $("authHint").textContent = message;
    else updateAccountUI();
  }

  function updateAccountUI() {
    const loggedIn = !!currentAccount;
    $("signedIn").hidden = !loggedIn;
    $("signedIn").textContent = loggedIn ? `Angemeldet als ${currentAccount.username}${currentAccount.role === "admin" ? " (Admin)" : ""}` : "";
    $("arrive").hidden = !loggedIn;
    $("openSettings").hidden = !loggedIn;
    $("logout").hidden = !loggedIn;
    $("openAuth").hidden = loggedIn;
    $("authHint").textContent = loggedIn
      ? (currentAccount.role === "admin" ? "Du bist als Admin angemeldet." : "Du kannst Punktestände und Hotdogs ändern.")
      : "Nur lesender Zugriff. Melde dich an, um Punkte und Hotdogs zu ändern.";
    updatePermissions();
  }

  function updatePermissions() {
    const loggedIn = !!currentAccount;
    const admin = loggedIn && currentAccount.role === "admin";
    $("schedule").querySelectorAll("input, button").forEach((el) => { el.disabled = !admin; });
    $("addItem").disabled = !admin;
    $("info").disabled = !admin;
    $("dogMinus").disabled = !loggedIn;
    $("dogPlus").disabled = !loggedIn;
    $("addPlayer").disabled = !admin;
    $("addRound").disabled = !admin;
    $("removeRound").disabled = !admin;
    $("resetScores").disabled = !admin;
    $("scores").querySelectorAll("input, button").forEach((el) => {
      el.disabled = !loggedIn || (el.dataset.f === "name" || el.hasAttribute("data-delp")) && !admin;
    });
  }

  function setOnline(v) {
    online = v;
    const el = $("status");
    el.textContent = v ? "Live-Sync" : "Nur lokal (Server nicht erreichbar)";
    el.className = "badge " + (v ? "live" : "local");
  }

  async function loadState() {
    try {
      const r = await fetch(API, { cache: "no-store" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const s = await r.json();
      setOnline(true);
      return normalize(s);
    } catch (e) {
      setOnline(false);
      try { return normalize(JSON.parse(localStorage.getItem(LS_KEY))); } catch (e2) {}
      return normalize(null);
    }
  }

  function queueSave() {
    pendingSave = true;
    clearTimeout(saveTimer);
    saveTimer = setTimeout(save, 300);
  }

  async function save() {
    try { localStorage.setItem(LS_KEY, JSON.stringify(state)); } catch (e) {}
    if (online) {
      try {
        const r = await fetch(API, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(state)
        });
        if (r.status === 401 || r.status === 403) {
          const error = await r.json().catch(() => ({}));
          if (r.status === 401) { currentAccount = null; updateAccountUI(); }
          showMessage(error.error || "Du darfst diese Änderung nicht speichern.");
          pendingSave = false;
          return;
        }
        if (!r.ok) throw new Error("HTTP " + r.status);
        const s = await r.json();
        state.rev = s.rev;
      } catch (e) {
        setOnline(false);
      }
    }
    pendingSave = false;
  }

  function isEditing() {
    const a = document.activeElement;
    return pendingSave || (a && (a.tagName === "INPUT" || a.tagName === "TEXTAREA"));
  }

  async function poll() {
    if (isEditing()) return;
    await refreshAccount();
    const s = await loadState();
    if (!state || s.rev !== state.rev) {
      state = s;
      renderAll();
    }
  }

  function renderSchedule() {
    $("schedule").innerHTML = state.schedule.map((it, i) =>
      `<li data-i="${i}">
         <input type="time" value="${esc(it.time)}" data-f="time" aria-label="Uhrzeit">
         <input type="text" value="${esc(it.title)}" data-f="title" aria-label="Programmpunkt" maxlength="80">
         <button type="button" class="x" data-del="${i}" aria-label="Programmpunkt entfernen">✕</button>
       </li>`).join("");
    sortScheduleDom();
    tick();
    updatePermissions();
  }

  function sortScheduleDom() {
    const ul = $("schedule");
    [...ul.children]
      .sort((a, b) => a.querySelector('[data-f="time"]').value.localeCompare(b.querySelector('[data-f="time"]').value))
      .forEach((li) => ul.appendChild(li));
  }

  $("schedule").addEventListener("input", (e) => {
    const li = e.target.closest("li");
    if (!li || !e.target.dataset.f) return;
    state.schedule[+li.dataset.i][e.target.dataset.f] = e.target.value;
    queueSave();
  });
  $("schedule").addEventListener("change", (e) => {
    if (e.target.dataset.f === "time") { sortScheduleDom(); tick(); }
  });
  $("schedule").addEventListener("click", (e) => {
    const b = e.target.closest("[data-del]");
    if (!b) return;
    state.schedule.splice(+b.dataset.del, 1);
    renderSchedule();
    queueSave();
  });
  $("addItem").addEventListener("click", () => {
    const last = state.schedule.map((x) => x.time).filter(Boolean).sort().pop() || "12:00";
    state.schedule.push({ time: last, title: "Neuer Programmpunkt" });
    renderSchedule();
    queueSave();
    const rows = $("schedule").querySelectorAll('[data-f="title"]');
    const target = [...rows].reverse().find((r) => r.value === "Neuer Programmpunkt");
    if (target) { target.focus(); target.select(); }
  });

  const toMin = (t) => {
    const m = /^(\d{1,2}):(\d{2})$/.exec(t || "");
    return m ? +m[1] * 60 + +m[2] : null;
  };

  function tick() {
    const now = new Date();
    $("clock").textContent = now.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    if (!state) return;

    const secsNow = now.getHours() * 3600 + now.getMinutes() * 60 + now.getSeconds();
    const items = state.schedule
      .map((it, i) => ({ i, m: toMin(it.time), title: it.title }))
      .filter((x) => x.m !== null)
      .sort((a, b) => a.m - b.m);
    const cur = [...items].reverse().find((x) => x.m * 60 <= secsNow);
    const next = items.find((x) => x.m * 60 > secsNow);

    document.querySelectorAll("#schedule li").forEach((li) => {
      const i = +li.dataset.i;
      const m = toMin(li.querySelector('[data-f="time"]').value);
      li.classList.toggle("current", !!cur && cur.i === i);
      li.classList.toggle("next", !!next && next.i === i);
      li.classList.toggle("past", m !== null && m * 60 <= secsNow && !(cur && cur.i === i));
    });

    $("nowTitle").textContent = cur ? cur.title || "(ohne Titel)" : (items.length ? "Gleich geht's los" : "Noch kein Programm");
    if (next) {
      const s = next.m * 60 - secsNow;
      const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
      const t = (h ? h + " h " : "") + m + " min " + String(sec).padStart(2, "0") + " s";
      $("countdown").textContent = `Danach: ${next.title || "(ohne Titel)"} in ${t}`;
    } else {
      $("countdown").textContent = items.length ? "Das war das Programm für heute." : "";
    }
  }

  const total = (p) => p.scores.reduce((a, b) => a + (Number(b) || 0), 0);

  function renderScores() {
    let h = "<thead><tr><th>Platz</th><th class='avatar-cell'></th><th>Name / Steam</th>";
    for (let r = 0; r < state.rounds; r++) h += `<th>Runde ${r + 1}</th>`;
    h += "<th>Gesamt</th><th></th></tr></thead><tbody>";
    state.players.forEach((p, pi) => {
      const avatar = p.avatar_url || "";
      const steam = p.steam_handle || "";
      h += `<tr data-p="${pi}"><td class="rank"></td>
        <td class="avatar-cell">${avatar ? `<img src="${esc(avatar)}" class="avatar-thumb" alt="">` : `<span class="avatar-thumb"></span>`}</td>
        <td>
          <input type="text" value="${esc(p.name)}" data-f="name" aria-label="Name" maxlength="30">
          ${steam ? `<br><small style="color:var(--muted)">Steam: ${esc(steam)}</small>` : ""}
        </td>`;
      for (let r = 0; r < state.rounds; r++) {
        h += `<td><input type="number" value="${num(p.scores[r])}" data-r="${r}" aria-label="Punkte Runde ${r + 1}"></td>`;
      }
      h += `<td class="total">${total(p)}</td>
        <td><button type="button" class="x" data-delp="${pi}" aria-label="Spieler entfernen">✕</button></td></tr>`;
    });
    h += "</tbody>";
    $("scores").innerHTML = h;
    rankDom();
    updatePermissions();
  }

  function rankDom() {
    const tb = $("scores").querySelector("tbody");
    if (!tb) return;
    const rows = [...tb.children];
    rows.sort((a, b) => total(state.players[+b.dataset.p]) - total(state.players[+a.dataset.p]));
    rows.forEach((tr, i) => {
      tr.querySelector(".rank").textContent = i + 1;
      tr.classList.toggle("first", i === 0 && total(state.players[+tr.dataset.p]) > 0);
      tb.appendChild(tr);
    });
  }

  $("scores").addEventListener("input", (e) => {
    const tr = e.target.closest("tr[data-p]");
    if (!tr) return;
    const p = state.players[+tr.dataset.p];
    if (e.target.dataset.f === "name") {
      p.name = e.target.value;
    } else if (e.target.dataset.r !== undefined) {
      p.scores[+e.target.dataset.r] = num(e.target.value);
      tr.querySelector(".total").textContent = total(p);
    }
    queueSave();
  });
  $("scores").addEventListener("change", rankDom);
  $("scores").addEventListener("click", (e) => {
    const b = e.target.closest("[data-delp]");
    if (!b) return;
    const p = state.players[+b.dataset.delp];
    if (!confirm(`„${p.name}" wirklich entfernen?`)) return;
    state.players.splice(+b.dataset.delp, 1);
    renderScores();
    queueSave();
  });

  $("addPlayer").addEventListener("click", () => {
    state.players.push({ name: "Spieler " + (state.players.length + 1), scores: Array(state.rounds).fill(0) });
    renderScores();
    queueSave();
  });
  $("addRound").addEventListener("click", () => {
    state.rounds += 1;
    state.players.forEach((p) => p.scores.push(0));
    renderScores();
    queueSave();
  });
  $("removeRound").addEventListener("click", () => {
    if (state.rounds <= 1) return;
    if (!confirm(`Runde ${state.rounds} mit allen Punkten entfernen?`)) return;
    state.rounds -= 1;
    state.players.forEach((p) => p.scores.length = state.rounds);
    renderScores();
    queueSave();
  });
  $("resetScores").addEventListener("click", () => {
    if (!confirm("Alle Punkte auf 0 setzen?")) return;
    state.players.forEach((p) => p.scores = Array(state.rounds).fill(0));
    renderScores();
    queueSave();
  });

  function renderDogs() { $("dogCount").textContent = state.hotdogs; }
  $("dogPlus").addEventListener("click", () => { state.hotdogs += 1; renderDogs(); queueSave(); });
  $("dogMinus").addEventListener("click", () => { state.hotdogs = Math.max(0, state.hotdogs - 1); renderDogs(); queueSave(); });
  $("info").addEventListener("input", (e) => { state.info = e.target.value; queueSave(); });

  function authView(view) {
    const settings = view === "settings";
    $("authPanel").hidden = false;
    $("authTabs").hidden = settings;
    $("loginForm").hidden = view !== "login";
    $("registerForm").hidden = view !== "register";
    $("settingsForm").hidden = !settings;
    $("authTitle").textContent = settings ? "Profil-Einstellungen" : view === "register" ? "Registrieren" : "Anmelden";
    showMessage("");
    if (settings && currentAccount) {
      const f = $("settingsForm").elements;
      f.sound_mode.value = currentAccount.sound_mode || "name";
      f.sound_file.value = currentAccount.sound_file || "";
      f.steam_handle.value = currentAccount.steam_handle || "";
      f.avatar_url.value = currentAccount.avatar_url || "";
      f.sound_mode.dispatchEvent(new Event("change"));
    }
  }

  function populateSoundMenus() {
    document.querySelectorAll(".sound-file").forEach((select) => {
      const currentVal = select.value;
      select.replaceChildren();
      const fallback = document.createElement("option");
      fallback.value = "";
      fallback.textContent = "Signalton-Fallback (keine Datei)";
      select.appendChild(fallback);
      sounds.forEach((filename) => {
        const option = document.createElement("option");
        option.value = filename;
        option.textContent = filename;
        select.appendChild(option);
      });
      select.value = currentVal;
    });
    document.querySelectorAll(".sound-mode").forEach((select) => {
      select.onchange = () => {
        const fileSelect = select.closest("form").querySelector(".sound-file");
        if(fileSelect) fileSelect.disabled = select.value === "name";
      };
      select.dispatchEvent(new Event("change"));
    });
  }

  async function refreshAccount() {
    try {
      const response = await fetch("/api/me", { cache: "no-store" });
      if (!response.ok) return;
      const data = await response.json();
      currentAccount = data.user || null;
      updateAccountUI();
    } catch (e) {}
  }

  async function loadSounds() {
    try {
      const response = await fetch("/api/sounds", { cache: "no-store" });
      if (response.ok) sounds = (await response.json()).sounds || [];
    } catch (e) { sounds = []; }
    populateSoundMenus();
  }

  async function postJson(path, data) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || "Die Anfrage ist fehlgeschlagen.");
    return result;
  }

  async function uploadSoundFile(fileInputId) {
    const fileInput = $(fileInputId);
    if (!fileInput.files.length) {
      showMessage("Bitte zuerst eine Datei auswählen.");
      return;
    }
    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append("file", file);

    try {
      const r = await fetch("/api/sound/upload", { method: "POST", body: formData });
      const res = await r.json();
      if (!r.ok) throw new Error(res.error || "Upload fehlgeschlagen");
      fileInput.value = "";
      await loadSounds();
      showMessage("Datei erfolgreich hochgeladen!");
    } catch (err) {
      showMessage(err.message);
    }
  }

  $("openAuth").addEventListener("click", () => authView("login"));
  $("openSettings").addEventListener("click", () => authView("settings"));
  $("closeAuth").addEventListener("click", () => { $("authPanel").hidden = true; });
  document.querySelectorAll("[data-auth-tab]").forEach((button) => {
    button.addEventListener("click", () => authView(button.dataset.authTab));
  });

  $("regUploadBtn").addEventListener("click", (e) => { e.preventDefault(); uploadSoundFile("regSoundFile"); });
  $("setUploadBtn").addEventListener("click", (e) => { e.preventDefault(); uploadSoundFile("setSoundFile"); });

  $("loginForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    try {
      const result = await postJson("/api/login", {
        username: formElement.elements.username.value,
        password: formElement.elements.password.value
      });
      currentAccount = result.user;
      formElement.reset();
      $("authPanel").hidden = true;
      showMessage("");
      updateAccountUI();
    } catch (error) { showMessage(error.message || "Anmeldung fehlgeschlagen."); }
  });

  $("registerForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    const f = formElement.elements;
    try {
      const result = await postJson("/api/register", {
        username: f.username.value,
        password: f.password.value,
        steam_handle: f.steam_handle.value,
        avatar_url: f.avatar_url.value,
        sound_mode: f.sound_mode.value,
        sound_file: f.sound_file.value
      });
      currentAccount = result.user;
      formElement.reset();
      $("authPanel").hidden = true;
      showMessage("");
      updateAccountUI();
      await poll();
    } catch (error) { showMessage(error.message || "Registrierung fehlgeschlagen."); }
  });

  $("settingsForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    const f = formElement.elements;
    try {
      const result = await postJson("/api/me/settings", {
        steam_handle: f.steam_handle.value,
        avatar_url: f.avatar_url.value,
        sound_mode: f.sound_mode.value,
        sound_file: f.sound_file.value
      });
      currentAccount = result.user;
      showMessage("Einstellungen gespeichert.");
      updateAccountUI();
    } catch (error) { showMessage(error.message || "Fehler beim Speichern."); }
  });

  document.querySelectorAll(".sound-test").forEach((button) => {
    button.addEventListener("click", async () => {
      const form = button.closest("form");
      const f = form.elements;
      try {
        const data = {
          sound_mode: f.sound_mode.value,
          sound_file: f.sound_file.value
        };
        if (form.id === "registerForm") data.username = f.username.value;
        const result = await postJson("/api/sound/test", data);
        if (data.sound_file) {
          new Audio('/sounds/' + data.sound_file).play().catch(() => {});
        }
        showMessage(result.message || "Sound wurde gestartet.");
      } catch (error) { showMessage(error.message || "Sound konnte nicht gestartet werden."); }
    });
  });

  $("arrive").addEventListener("click", async () => {
    try {
      const response = await fetch("/api/sound/arrive", { method: "POST" });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error || "Sound konnte nicht gestartet werden.");
      if (result.sound_file) {
        new Audio('/sounds/' + result.sound_file).play().catch(() => {});
      }
      showMessage(result.message || "Du bist angemeldet.");
    } catch (error) { showMessage(error.message || "Sound konnte nicht gestartet werden."); }
  });

  $("logout").addEventListener("click", async () => {
    try { await fetch("/api/logout", { method: "POST" }); } catch (e) {}
    currentAccount = null;
    $("authPanel").hidden = true;
    updateAccountUI();
  });

  function renderAll() {
    renderSchedule();
    renderScores();
    renderDogs();
    $("info").value = state.info;
    tick();
  }

  (async () => {
    state = await loadState();
    await refreshAccount();
    await loadSounds();
    renderAll();
    setInterval(tick, 1000);
    setInterval(poll, 3000);
  })();
})();