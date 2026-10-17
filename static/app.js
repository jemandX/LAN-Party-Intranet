'use strict';

// ---------- Hilfsfunktionen ----------
const $ = (sel) => document.querySelector(sel);

function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  if (props) {
    for (const [k, v] of Object.entries(props)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k === 'text') el.textContent = v;
      else if (k === 'value') el.value = v;
      else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else if (v === true) el.setAttribute(k, '');
      else el.setAttribute(k, v);
    }
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

let toastTimer = null;
function toast(msg, isError) {
  const t = $('#toast');
  t.textContent = msg;
  t.className = 'show' + (isError ? ' error' : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.className = ''; }, isError ? 6000 : 2800);
}

async function api(path, opts) {
  const o = Object.assign({ method: 'GET', credentials: 'same-origin', headers: {} }, opts || {});
  if (o.json !== undefined) {
    o.method = 'POST';
    o.headers['Content-Type'] = 'application/json';
    o.body = JSON.stringify(o.json);
  }
  delete o.json;
  let res;
  try {
    res = await fetch(path, o);
  } catch (e) {
    throw new Error('Server nicht erreichbar. Läuft der Server noch?');
  }
  const text = await res.text();
  let data = null;
  try { data = JSON.parse(text); } catch (e) { /* keine JSON-Antwort */ }
  if (!res.ok) {
    const msg = data && data.error ? data.error : 'Fehler ' + res.status + ': ' + text.slice(0, 200);
    if (res.status === 401 && path !== '/api/login' && path !== '/api/register') {
      showAuth();
    }
    throw new Error(msg);
  }
  return data;
}

// ---------- Zustand ----------
let state = null;
let me = null;
let tab = 'scores';
let pendingRender = false;
const draft = { settings: null };

function busy() {
  const a = document.activeElement;
  const view = $('#view');
  if (a && view.contains(a) && ['INPUT', 'TEXTAREA', 'SELECT'].includes(a.tagName)) return true;
  for (const au of view.querySelectorAll('audio')) {
    if (!au.paused && !au.ended) return true;
  }
  return false;
}

function applyState(st, force) {
  if (!st || st.changed === false) return;
  if (state && st.rev < state.rev && !force) return;
  state = st;
  me = st.me;
  if (!force && busy()) { pendingRender = true; return; }
  pendingRender = false;
  render();
}

function flushPending() {
  if (pendingRender && !busy()) {
    pendingRender = false;
    render();
  }
}

async function refresh(force) {
  const st = await api('/api/state');
  applyState(st, force);
}

async function act(payload) {
  try {
    applyState(await api('/api/action', { json: payload }));
  } catch (e) {
    toast(e.message, true);
    try { await refresh(true); } catch (e2) { /* ignoriert */ }
  }
}

// ---------- Anmeldung ----------
function showAuth() {
  state = null;
  me = null;
  $('#app').hidden = true;
  $('#auth').hidden = false;
}

function showApp() {
  $('#auth').hidden = true;
  $('#app').hidden = false;
}

function setupAuth() {
  const loginForm = $('#loginForm');
  const regForm = $('#registerForm');
  const msg = $('#authMsg');
  const switchTo = (reg) => {
    loginForm.hidden = reg;
    regForm.hidden = !reg;
    $('#showLogin').classList.toggle('active', !reg);
    $('#showRegister').classList.toggle('active', reg);
    msg.textContent = '';
  };
  $('#showLogin').addEventListener('click', () => switchTo(false));
  $('#showRegister').addEventListener('click', () => switchTo(true));

  async function submit(form, path) {
    msg.textContent = '';
    const btn = form.querySelector('button[type=submit]');
    btn.disabled = true;
    try {
      await api(path, { json: { username: form.elements.username.value, password: form.elements.password.value } });
      form.reset();
      draft.settings = null;
      await refresh(true);
      showApp();
    } catch (e) {
      msg.textContent = e.message;
    } finally {
      btn.disabled = false;
    }
  }
  loginForm.addEventListener('submit', (ev) => { ev.preventDefault(); submit(loginForm, '/api/login'); });
  regForm.addEventListener('submit', (ev) => { ev.preventDefault(); submit(regForm, '/api/register'); });

  $('#logoutBtn').addEventListener('click', async () => {
    try { await api('/api/logout', { json: {} }); } catch (e) { /* ignoriert */ }
    draft.settings = null;
    showAuth();
  });
}

// ---------- Rendering ----------
const TABS = [
  ['scores', 'Punkte'],
  ['hotdogs', 'Hotdogs'],
  ['schedule', 'Zeitplan'],
  ['info', 'Info'],
  ['players', 'Spieler & Steam'],
  ['settings', 'Einstellungen'],
  ['admin', 'Admin'],
];

function render() {
  if (!state || !me) return;
  showApp();
  $('#whoami').textContent = me.username + (me.is_admin ? ' (Admin)' : '');
  const tabs = $('#tabs');
  const list = TABS.filter(([id]) => id !== 'admin' || me.is_admin);
  if (!list.some(([id]) => id === tab)) tab = 'scores';
  tabs.replaceChildren(...list.map(([id, label]) =>
    h('button', { type: 'button', class: id === tab ? 'active' : '', onclick: () => { tab = id; render(); } }, label)));
  const fn = { scores: renderScores, hotdogs: renderHotdogs, schedule: renderSchedule, info: renderInfo,
               players: renderPlayers, settings: renderSettings, admin: renderAdmin }[tab];
  $('#view').replaceChildren(fn());
}

function totalsOf() {
  const t = {};
  for (const p of state.players) {
    let sum = 0;
    for (const r of state.rounds) sum += ((state.scores[p.id] || {})[r.id]) || 0;
    t[p.id] = sum;
  }
  return t;
}

function askText(label, payloadFn) {
  const input = h('input', { type: 'text', maxlength: '32', placeholder: label, 'aria-label': label });
  const go = () => {
    const v = input.value.trim();
    if (!v) return;
    act(payloadFn(v));
    input.value = '';
  };
  input.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') { ev.preventDefault(); go(); } });
  return h('div', { class: 'row' }, input, h('button', { type: 'button', onclick: go }, 'Hinzufügen'));
}

function renderScores() {
  const st = state;
  const t = totalsOf();
  const root = h('div');
  const ranked = st.players.slice().sort((a, b) => t[b.id] - t[a.id]);

  root.append(h('div', { class: 'card' }, h('h2', null, 'Rangliste'),
    ranked.length
      ? h('ol', { class: 'rank' }, ranked.map((p) =>
          h('li', { class: p.id === st.top ? 'leader' : '' },
            h('span', null, (p.id === st.top ? '★ ' : '') + p.name),
            h('span', null, String(t[p.id])))))
      : h('p', { class: 'hint' }, 'Noch keine Spieler. Ein Admin legt sie unten an.')));

  const head = h('tr', null, h('th', { class: 'name' }, 'Spieler'),
    st.rounds.map((r) => h('th', { class: 'num' }, r.name, me.is_admin
      ? h('button', { type: 'button', class: 'small danger', title: 'Runde löschen', 'aria-label': 'Runde ' + r.name + ' löschen',
          onclick: () => { if (confirm('Runde "' + r.name + '" samt Punkten löschen?')) act({ action: 'round_delete', id: r.id }); } }, '✕')
      : null)),
    h('th', { class: 'num' }, 'Summe'),
    me.is_admin ? h('th', null, '') : null);

  const body = st.players.map((p) => h('tr', { class: p.id === st.top ? 'leader' : '' },
    h('td', { class: 'name' }, (p.id === st.top ? '★ ' : '') + p.name),
    st.rounds.map((r) => {
      const val = (st.scores[p.id] || {})[r.id];
      const inp = h('input', { type: 'number', inputmode: 'numeric', step: '1', class: 'cell',
        'aria-label': p.name + ' – ' + r.name, value: val === undefined ? '' : String(val) });
      inp.addEventListener('change', () => {
        act({ action: 'score_set', player: p.id, round: r.id, value: inp.value === '' ? null : Number(inp.value) });
      });
      return h('td', { class: 'num' }, inp);
    }),
    h('td', { class: 'total' }, String(t[p.id])),
    me.is_admin ? h('td', null, h('button', { type: 'button', class: 'small danger', title: 'Spieler löschen',
      'aria-label': p.name + ' löschen',
      onclick: () => { if (confirm('Spieler "' + p.name + '" löschen?')) act({ action: 'player_delete', id: p.id }); } }, '✕')) : null));

  root.append(h('div', { class: 'card' }, h('h2', null, 'Punkte pro Runde'),
    st.players.length
      ? h('div', { class: 'tablewrap' }, h('table', null, h('thead', null, head), h('tbody', null, body)))
      : h('p', { class: 'hint' }, 'Keine Spieler vorhanden.'),
    st.players.length && !st.rounds.length ? h('p', { class: 'hint' }, 'Noch keine Runden. Ein Admin legt sie unten an.') : null,
    h('p', { class: 'hint' }, 'Der Führende (★) hat die strikt höchste Summe über 0. Bei Gleichstand an der Spitze wird niemand hervorgehoben.')));

  if (me.is_admin) {
    root.append(h('div', { class: 'card' }, h('h2', null, 'Spieler hinzufügen'),
      askText('Name des Spielers', (v) => ({ action: 'player_add', name: v }))));
    root.append(h('div', { class: 'card' }, h('h2', null, 'Runde hinzufügen'),
      askText('Name der Runde', (v) => ({ action: 'round_add', name: v }))));
  }
  return root;
}

function renderHotdogs() {
  const st = state;
  let sum = 0;
  for (const p of st.players) sum += st.hotdogs[p.id] || 0;
  const items = st.players.map((p) => h('li', null,
    h('span', { class: 'grow' }, p.name),
    h('button', { type: 'button', 'aria-label': 'Ein Hotdog weniger für ' + p.name, onclick: () => act({ action: 'hotdog_add', player: p.id, delta: -1 }) }, '−'),
    h('span', { class: 'counter' }, String(st.hotdogs[p.id] || 0)),
    h('button', { type: 'button', class: 'primary', 'aria-label': 'Ein Hotdog mehr für ' + p.name, onclick: () => act({ action: 'hotdog_add', player: p.id, delta: 1 }) }, '+')));
  return h('div', { class: 'card' }, h('h2', null, 'Hotdog-Zähler 🌭'),
    h('p', null, 'Insgesamt gegessen: ', h('strong', null, String(sum))),
    items.length ? h('ul', { class: 'list' }, items) : h('p', { class: 'hint' }, 'Noch keine Spieler.'));
}

function renderSchedule() {
  const st = state;
  const root = h('div', { class: 'card' }, h('h2', null, 'Zeitplan'));
  if (st.schedule.length) {
    root.append(h('ul', { class: 'list' }, st.schedule.map((e) => h('li', null,
      h('span', { class: 'time' }, e.time), h('span', { class: 'grow' }, e.title),
      me.is_admin ? h('button', { type: 'button', class: 'small danger', 'aria-label': 'Eintrag löschen',
        onclick: () => act({ action: 'schedule_delete', id: e.id }) }, '✕') : null))));
  } else {
    root.append(h('p', { class: 'hint' }, 'Noch keine Einträge.'));
  }
  if (me.is_admin) {
    const time = h('input', { type: 'text', maxlength: '16', placeholder: 'Uhrzeit, z. B. 18:00', 'aria-label': 'Uhrzeit' });
    const title = h('input', { type: 'text', maxlength: '80', placeholder: 'Was passiert?', 'aria-label': 'Titel' });
    const go = () => {
      if (!time.value.trim() || !title.value.trim()) { toast('Uhrzeit und Titel angeben.', true); return; }
      act({ action: 'schedule_add', time: time.value, title: title.value });
      time.value = ''; title.value = '';
    };
    root.append(h('div', { class: 'spacer' }), h('h3', null, 'Eintrag hinzufügen'),
      h('div', { class: 'row' }, time, title, h('button', { type: 'button', onclick: go }, 'Hinzufügen')));
  }
  return root;
}

function renderInfo() {
  const root = h('div', { class: 'card' }, h('h2', null, 'Info (WLAN, Server, Regeln)'));
  if (me.is_admin) {
    const ta = h('textarea', { maxlength: '5000', 'aria-label': 'Info-Text', value: state.info });
    root.append(ta, h('div', { class: 'spacer' }),
      h('button', { type: 'button', class: 'primary', onclick: () => act({ action: 'info_set', text: ta.value }).then(() => toast('Info gespeichert.')) }, 'Speichern'),
      h('p', { class: 'hint' }, 'Nur Admins können den Text ändern.'));
  } else {
    root.append(h('pre', { class: 'info' }, state.info || 'Noch keine Infos eingetragen.'));
  }
  return root;
}

function renderPlayers() {
  const rows = state.users.map((u) => {
    const ok = typeof u.steam_url === 'string' && u.steam_url.startsWith('https://steamcommunity.com/');
    return h('li', null,
      h('strong', null, u.username),
      h('span', { class: 'grow' }, u.steam_name ? 'Steam: ' + u.steam_name : ''),
      ok ? h('a', { href: u.steam_url, target: '_blank', rel: 'noopener noreferrer' }, 'Steam-Profil ↗')
         : h('span', { class: 'badge' }, 'kein Link'));
  });
  return h('div', { class: 'card' }, h('h2', null, 'Spieler & Steam'),
    rows.length ? h('ul', { class: 'list' }, rows) : h('p', { class: 'hint' }, 'Noch keine Konten.'));
}

function renderSettings() {
  const st = state;
  if (!draft.settings) {
    draft.settings = { steam_name: me.steam_name, steam_url: me.steam_url, mode: me.mode, sound: me.sound };
  }
  const d = draft.settings;
  if (d.sound && !st.sounds.includes(d.sound)) d.sound = '';

  const name = h('input', { type: 'text', maxlength: '32', value: d.steam_name, autocomplete: 'off' });
  name.addEventListener('input', () => { d.steam_name = name.value; });
  const url = h('input', { type: 'url', maxlength: '200', placeholder: 'https://steamcommunity.com/id/deinname', value: d.steam_url, autocomplete: 'off' });
  url.addEventListener('input', () => { d.steam_url = url.value; });
  const mode = h('select', null,
    h('option', { value: 'name' }, 'Nur Name ansagen'),
    h('option', { value: 'sound' }, 'Nur Sound abspielen'),
    h('option', { value: 'both' }, 'Erst Sound, dann Name'));
  mode.value = d.mode;
  mode.addEventListener('change', () => { d.mode = mode.value; });
  const sound = h('select', null, h('option', { value: '' }, '(kein Sound)'),
    st.sounds.map((s) => h('option', { value: s }, s)));
  sound.value = d.sound;
  sound.addEventListener('change', () => { d.sound = sound.value; });

  const msg = h('p', { class: 'msg', role: 'status' });
  const save = async () => {
    try {
      const st2 = await api('/api/settings', { json: Object.assign({}, d) });
      draft.settings = null;
      applyState(st2, true);
      toast('Einstellungen gespeichert.');
    } catch (e) { msg.className = 'msg error'; msg.textContent = e.message; }
  };
  const test = async () => {
    try {
      const r = await api('/api/test/announce', { json: { mode: d.mode, sound: d.sound } });
      msg.className = 'msg ok'; msg.textContent = r.message;
    } catch (e) { msg.className = 'msg error'; msg.textContent = e.message; }
  };
  const testLeader = async () => {
    try {
      const r = await api('/api/test/leader', { json: {} });
      msg.className = 'msg ok'; msg.textContent = r.message;
    } catch (e) { msg.className = 'msg error'; msg.textContent = e.message; }
  };

  const settingsCard = h('div', { class: 'card' }, h('h2', null, 'Meine Einstellungen'),
    h('label', null, 'Steam-Handle (Anzeigename)'), name,
    h('label', null, 'Steam-Community-Link'), url,
    h('label', null, 'Ansage-Modus (läuft am Host-PC)'), mode,
    h('label', null, 'Sound-Datei'), sound,
    h('div', { class: 'spacer' }),
    h('div', { class: 'row' },
      h('button', { type: 'button', class: 'primary', onclick: save }, 'Speichern'),
      h('button', { type: 'button', onclick: test }, 'Testen (am Host-PC)'),
      me.is_admin ? h('button', { type: 'button', onclick: testLeader }, 'Führungs-Ansage testen') : null),
    msg);

  // Upload
  const file = h('input', { type: 'file', accept: '.wav,.mp3,.mp4,audio/wav,audio/mpeg,video/mp4' });
  const upMsg = h('p', { class: 'msg', role: 'status' });
  const upBtn = h('button', { type: 'button', class: 'primary' }, 'Hochladen');
  upBtn.addEventListener('click', async () => {
    upMsg.className = 'msg'; upMsg.textContent = '';
    if (!file.files || !file.files[0]) { upMsg.className = 'msg error'; upMsg.textContent = 'Bitte zuerst eine Datei wählen.'; return; }
    const fd = new FormData();
    fd.append('sound', file.files[0]);
    upBtn.disabled = true;
    upMsg.textContent = 'Lade hoch …';
    try {
      const r = await api('/api/upload', { method: 'POST', body: fd });
      upMsg.className = 'msg ok';
      upMsg.textContent = 'Hochgeladen: ' + r.uploaded;
      applyState(r, true);
    } catch (e) {
      upMsg.className = 'msg error';
      upMsg.textContent = 'Upload fehlgeschlagen: ' + e.message;
    } finally { upBtn.disabled = false; }
  });

  const soundRows = st.sounds.map((s) => h('li', null,
    h('span', { class: 'grow' }, s),
    h('audio', { controls: true, preload: 'none', src: '/sounds/' + encodeURIComponent(s) }),
    me.is_admin ? h('button', { type: 'button', class: 'small danger', onclick: () => {
      if (!confirm('Sound "' + s + '" löschen?')) return;
      api('/api/sounds/delete', { json: { name: s } }).then((r) => { applyState(r, true); toast('Sound gelöscht.'); })
        .catch((e) => toast(e.message, true));
    } }, 'Löschen') : null));

  const uploadCard = h('div', { class: 'card' }, h('h2', null, 'Sound hochladen'),
    h('p', { class: 'hint' }, 'Erlaubt: .wav, .mp3, .mp4 bis 10 MB. Die Wiedergabe passiert am Host-PC, nicht auf deinem Gerät.'),
    file, h('div', { class: 'spacer' }), upBtn, upMsg,
    h('div', { class: 'spacer' }), h('h3', null, 'Vorhandene Sounds'),
    soundRows.length ? h('ul', { class: 'list' }, soundRows) : h('p', { class: 'hint' }, 'Noch keine Sounds hochgeladen.'));

  return h('div', null, settingsCard, uploadCard);
}

function renderAdmin() {
  const accounts = state.accounts || [];
  const rows = accounts.map((a) => {
    const isMe = a.id === me.id;
    const inPlayers = state.players.some((p) => p.name.toLowerCase() === a.username.toLowerCase());
    return h('li', null,
      h('strong', null, a.username),
      a.is_admin ? h('span', { class: 'badge admin' }, 'Admin') : h('span', { class: 'badge' }, 'Nutzer'),
      isMe ? h('span', { class: 'badge' }, 'du') : null,
      h('span', { class: 'grow' }),
      !inPlayers ? h('button', { type: 'button', class: 'small', onclick: () => act({ action: 'player_add', name: a.username }) }, 'Als Spieler') : null,
      h('button', { type: 'button', class: 'small', onclick: () => {
        api('/api/admin/user/admin', { json: { id: a.id, admin: !a.is_admin } })
          .then((r) => applyState(r, true)).catch((e) => toast(e.message, true));
      } }, a.is_admin ? 'Admin entziehen' : 'Zum Admin machen'),
      !isMe ? h('button', { type: 'button', class: 'small danger', onclick: () => {
        if (!confirm('Konto "' + a.username + '" löschen?')) return;
        api('/api/admin/user/delete', { json: { id: a.id } })
          .then((r) => applyState(r, true)).catch((e) => toast(e.message, true));
      } }, 'Löschen') : null);
  });
  return h('div', { class: 'card' }, h('h2', null, 'Konten verwalten'),
    h('p', { class: 'hint' }, '„Als Spieler“ legt einen Spieler mit dem Kontonamen im Punktestand an. So passt die Führungs-Ansage zum Sound des Kontos.'),
    h('ul', { class: 'list' }, rows));
}

// ---------- Start ----------
let polling = false;
async function poll() {
  if (!me || document.hidden || polling) return;
  polling = true;
  try {
    const st = await api('/api/state?rev=' + (state ? state.rev : 0));
    $('#conn').textContent = '';
    applyState(st);
  } catch (e) {
    if (me) $('#conn').textContent = '⚠ keine Verbindung';
  } finally {
    polling = false;
  }
}

async function boot() {
  setupAuth();
  const view = $('#view');
  view.addEventListener('focusout', () => setTimeout(flushPending, 200));
  view.addEventListener('pause', () => setTimeout(flushPending, 200), true);
  view.addEventListener('ended', () => setTimeout(flushPending, 200), true);
  try {
    await refresh(true);
    showApp();
  } catch (e) {
    showAuth();
  }
  setInterval(poll, 2000);
}

boot();
