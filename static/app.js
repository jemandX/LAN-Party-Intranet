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
  const o = Object.assign({ method: 'GET', credentials: 'same-origin', headers: { 'X-Lang': lang } }, opts || {});
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
    throw new Error(t('unreachable'));
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


// ---------- Sprachen ----------
const I18N = {
  de: {
    login: 'Anmelden', register: 'Registrieren', username: 'Benutzername', username_reg: 'Benutzername (2-24 Zeichen)',
    password: 'Passwort', password_reg: 'Passwort (mind. 6 Zeichen)', create_account: 'Konto erstellen',
    first_admin: 'Der erste Account auf diesem Server wird automatisch Admin.', logout: 'Abmelden',
    admin_suffix: ' (Admin)', conn_lost: '⚠ keine Verbindung', unreachable: 'Server nicht erreichbar. Läuft der Server noch?',
    tab_scores: 'Punkte', tab_hotdogs: 'Hotdogs', tab_schedule: 'Zeitplan', tab_info: 'Info',
    tab_players: 'Spieler & Steam', tab_settings: 'Einstellungen', tab_admin: 'Admin',
    add: 'Hinzufügen', del: 'Löschen', save: 'Speichern',
    ranking: 'Rangliste', no_players_admin: 'Noch keine Spieler. Ein Admin legt sie unten an.', player: 'Spieler', sum: 'Summe',
    delete_round_title: 'Runde löschen', delete_round_aria: 'Runde {0} löschen', confirm_round: 'Runde "{0}" samt Punkten löschen?',
    delete_player_title: 'Spieler löschen', delete_player_aria: '{0} löschen', confirm_player: 'Spieler "{0}" löschen?',
    points_per_round: 'Punkte pro Runde', no_players: 'Keine Spieler vorhanden.',
    no_rounds: 'Noch keine Runden. Ein Admin legt sie unten an.',
    leader_hint: 'Der Führende (★) hat die strikt höchste Summe über 0. Bei Gleichstand an der Spitze wird niemand hervorgehoben.',
    add_player: 'Spieler hinzufügen', add_round: 'Runde hinzufügen', player_name_ph: 'Name des Spielers', round_name_ph: 'Name der Runde',
    hotdog_title: 'Hotdog-Zähler 🌭', hotdog_total: 'Insgesamt gegessen: ', less_aria: 'Ein Hotdog weniger für {0}',
    more_aria: 'Ein Hotdog mehr für {0}', no_players_short: 'Noch keine Spieler.',
    schedule_title: 'Zeitplan', time_ph: 'Uhrzeit, z. B. 18:00', what_ph: 'Was passiert?', time_aria: 'Uhrzeit', title_aria: 'Titel',
    delete_entry_aria: 'Eintrag löschen', no_entries: 'Noch keine Einträge.', need_time_title: 'Uhrzeit und Titel angeben.',
    add_entry: 'Eintrag hinzufügen',
    info_title: 'Info (WLAN, Server, Regeln)', info_aria: 'Info-Text', info_saved: 'Info gespeichert.',
    admin_only_info: 'Nur Admins können den Text ändern.', no_info: 'Noch keine Infos eingetragen.',
    players_title: 'Spieler & Steam', steam_prefix: 'Steam: ', steam_profile: 'Steam-Profil ↗', no_link: 'kein Link', no_accounts: 'Noch keine Konten.',
    my_settings: 'Meine Einstellungen', steam_handle: 'Steam-Handle (Anzeigename)', steam_link: 'Steam-Community-Link',
    mode_label: 'Ansage-Modus (läuft am Host-PC)', mode_name: 'Nur Name ansagen', mode_sound: 'Nur Sound abspielen', mode_both: 'Erst Sound, dann Name',
    sound_file: 'Sound-Datei', no_sound: '(kein Sound)', test_btn: 'Testen (am Host-PC)', test_leader_btn: 'Führungs-Ansage testen',
    saved: 'Einstellungen gespeichert.', lang_hint: 'Die Ansagen am Host-PC werden in der gewählten Sprache (DE/EN) gesprochen.',
    upload_title: 'Sound hochladen', upload_hint: 'Erlaubt: .wav, .mp3, .mp4 bis 10 MB. Die Wiedergabe passiert am Host-PC, nicht auf deinem Gerät.',
    upload_btn: 'Hochladen', choose_file: 'Bitte zuerst eine Datei wählen.', uploading: 'Lade hoch …', uploaded: 'Hochgeladen: {0}',
    upload_failed: 'Upload fehlgeschlagen: {0}', existing: 'Vorhandene Sounds', no_sounds: 'Noch keine Sounds hochgeladen.',
    confirm_sound: 'Sound "{0}" löschen?', sound_deleted: 'Sound gelöscht.',
    accounts_title: 'Konten verwalten',
    admin_hint: '„Als Spieler“ legt einen Spieler mit dem Kontonamen im Punktestand an. So passt die Führungs-Ansage zum Sound des Kontos.',
    as_player: 'Als Spieler', badge_admin: 'Admin', badge_user: 'Nutzer', badge_you: 'du', revoke_admin: 'Admin entziehen',
    make_admin: 'Zum Admin machen', confirm_account: 'Konto "{0}" löschen?',
  },
  en: {
    login: 'Log in', register: 'Register', username: 'Username', username_reg: 'Username (2-24 characters)',
    password: 'Password', password_reg: 'Password (min. 6 characters)', create_account: 'Create account',
    first_admin: 'The first account on this server automatically becomes admin.', logout: 'Log out',
    admin_suffix: ' (admin)', conn_lost: '⚠ no connection', unreachable: 'Server not reachable. Is the server still running?',
    tab_scores: 'Scores', tab_hotdogs: 'Hotdogs', tab_schedule: 'Schedule', tab_info: 'Info',
    tab_players: 'Players & Steam', tab_settings: 'Settings', tab_admin: 'Admin',
    add: 'Add', del: 'Delete', save: 'Save',
    ranking: 'Ranking', no_players_admin: 'No players yet. An admin adds them below.', player: 'Player', sum: 'Total',
    delete_round_title: 'Delete round', delete_round_aria: 'Delete round {0}', confirm_round: 'Delete round "{0}" including its points?',
    delete_player_title: 'Delete player', delete_player_aria: 'Delete {0}', confirm_player: 'Delete player "{0}"?',
    points_per_round: 'Points per round', no_players: 'No players.',
    no_rounds: 'No rounds yet. An admin adds them below.',
    leader_hint: 'The leader (★) has the strictly highest total above 0. If the top is tied, nobody is highlighted.',
    add_player: 'Add player', add_round: 'Add round', player_name_ph: 'Player name', round_name_ph: 'Round name',
    hotdog_title: 'Hotdog counter 🌭', hotdog_total: 'Eaten in total: ', less_aria: 'One hotdog less for {0}',
    more_aria: 'One hotdog more for {0}', no_players_short: 'No players yet.',
    schedule_title: 'Schedule', time_ph: 'Time, e.g. 18:00', what_ph: "What's happening?", time_aria: 'Time', title_aria: 'Title',
    delete_entry_aria: 'Delete entry', no_entries: 'No entries yet.', need_time_title: 'Please enter a time and a title.',
    add_entry: 'Add entry',
    info_title: 'Info (Wi-Fi, servers, rules)', info_aria: 'Info text', info_saved: 'Info saved.',
    admin_only_info: 'Only admins can edit this text.', no_info: 'No info entered yet.',
    players_title: 'Players & Steam', steam_prefix: 'Steam: ', steam_profile: 'Steam profile ↗', no_link: 'no link', no_accounts: 'No accounts yet.',
    my_settings: 'My settings', steam_handle: 'Steam handle (display name)', steam_link: 'Steam Community link',
    mode_label: 'Announcement mode (plays on the host PC)', mode_name: 'Announce name only', mode_sound: 'Play sound only', mode_both: 'Sound first, then name',
    sound_file: 'Sound file', no_sound: '(no sound)', test_btn: 'Test (on host PC)', test_leader_btn: 'Test leader announcement',
    saved: 'Settings saved.', lang_hint: 'Announcements on the host PC are spoken in the selected language (DE/EN).',
    upload_title: 'Upload sound', upload_hint: 'Allowed: .wav, .mp3, .mp4 up to 10 MB. Playback happens on the host PC, not on your device.',
    upload_btn: 'Upload', choose_file: 'Please choose a file first.', uploading: 'Uploading …', uploaded: 'Uploaded: {0}',
    upload_failed: 'Upload failed: {0}', existing: 'Available sounds', no_sounds: 'No sounds uploaded yet.',
    confirm_sound: 'Delete sound "{0}"?', sound_deleted: 'Sound deleted.',
    accounts_title: 'Manage accounts',
    admin_hint: '"As player" adds a player with the account name to the scoreboard, so the leader announcement matches the account\'s sound.',
    as_player: 'As player', badge_admin: 'Admin', badge_user: 'User', badge_you: 'you', revoke_admin: 'Remove admin',
    make_admin: 'Make admin', confirm_account: 'Delete account "{0}"?',
  },
};

function detectLang() {
  try {
    const saved = localStorage.getItem('lang');
    if (saved === 'de' || saved === 'en') return saved;
  } catch (e) { /* Speicher nicht verfügbar */ }
  return (navigator.language || 'de').toLowerCase().startsWith('de') ? 'de' : 'en';
}

let lang = detectLang();

function t(key, ...args) {
  const s = (I18N[lang] && I18N[lang][key]) || I18N.de[key] || key;
  return s.replace(/\{(\d)\}/g, (m, i) => (args[Number(i)] === undefined ? '' : String(args[Number(i)])));
}

function applyStaticI18n() {
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-i18n]').forEach((el) => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll('[data-lang]').forEach((b) => b.classList.toggle('active', b.dataset.lang === lang));
}

function adoptLang(l) {
  if (l !== 'de' && l !== 'en') return;
  lang = l;
  try { localStorage.setItem('lang', l); } catch (e) { /* ignoriert */ }
  applyStaticI18n();
}

async function chooseLang(l) {
  adoptLang(l);
  if (me) {
    try { applyState(await api('/api/lang', { json: { lang: l } }), true); } catch (e) { toast(e.message, true); }
  } else if (state) {
    render();
  }
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
  if (me && me.lang && me.lang !== lang) adoptLang(me.lang);
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
      await api(path, { json: { username: form.elements.username.value, password: form.elements.password.value, lang } });
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
  ['scores', 'tab_scores'],
  ['hotdogs', 'tab_hotdogs'],
  ['schedule', 'tab_schedule'],
  ['info', 'tab_info'],
  ['players', 'tab_players'],
  ['settings', 'tab_settings'],
  ['admin', 'tab_admin'],
];

function render() {
  if (!state || !me) return;
  showApp();
  $('#whoami').textContent = me.username + (me.is_admin ? t('admin_suffix') : '');
  const tabs = $('#tabs');
  const list = TABS.filter(([id]) => id !== 'admin' || me.is_admin);
  if (!list.some(([id]) => id === tab)) tab = 'scores';
  tabs.replaceChildren(...list.map(([id, label]) =>
    h('button', { type: 'button', class: id === tab ? 'active' : '', onclick: () => { tab = id; render(); } }, t(label))));
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
  return h('div', { class: 'row' }, input, h('button', { type: 'button', onclick: go }, t('add')));
}

function renderScores() {
  const st = state;
  const t = totalsOf();
  const root = h('div');
  const ranked = st.players.slice().sort((a, b) => t[b.id] - t[a.id]);

  root.append(h('div', { class: 'card' }, h('h2', null, t('ranking')),
    ranked.length
      ? h('ol', { class: 'rank' }, ranked.map((p) =>
          h('li', { class: p.id === st.top ? 'leader' : '' },
            h('span', null, (p.id === st.top ? '★ ' : '') + p.name),
            h('span', null, String(t[p.id])))))
      : h('p', { class: 'hint' }, t('no_players_admin'))));

  const head = h('tr', null, h('th', { class: 'name' }, t('player')),
    st.rounds.map((r) => h('th', { class: 'num' }, r.name, me.is_admin
      ? h('button', { type: 'button', class: 'small danger', title: t('delete_round_title'), 'aria-label': t('delete_round_aria', r.name),
          onclick: () => { if (confirm(t('confirm_round', r.name))) act({ action: 'round_delete', id: r.id }); } }, '✕')
      : null)),
    h('th', { class: 'num' }, t('sum')),
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
    me.is_admin ? h('td', null, h('button', { type: 'button', class: 'small danger', title: t('delete_player_title'),
      'aria-label': t('delete_player_aria', p.name),
      onclick: () => { if (confirm(t('confirm_player', p.name))) act({ action: 'player_delete', id: p.id }); } }, '✕')) : null));

  root.append(h('div', { class: 'card' }, h('h2', null, t('points_per_round')),
    st.players.length
      ? h('div', { class: 'tablewrap' }, h('table', null, h('thead', null, head), h('tbody', null, body)))
      : h('p', { class: 'hint' }, t('no_players')),
    st.players.length && !st.rounds.length ? h('p', { class: 'hint' }, t('no_rounds')) : null,
    h('p', { class: 'hint' }, t('leader_hint'))));

  if (me.is_admin) {
    root.append(h('div', { class: 'card' }, h('h2', null, t('add_player')),
      askText(t('player_name_ph'), (v) => ({ action: 'player_add', name: v }))));
    root.append(h('div', { class: 'card' }, h('h2', null, t('add_round')),
      askText(t('round_name_ph'), (v) => ({ action: 'round_add', name: v }))));
  }
  return root;
}

function renderHotdogs() {
  const st = state;
  let sum = 0;
  for (const p of st.players) sum += st.hotdogs[p.id] || 0;
  const items = st.players.map((p) => h('li', null,
    h('span', { class: 'grow' }, p.name),
    h('button', { type: 'button', 'aria-label': t('less_aria', p.name), onclick: () => act({ action: 'hotdog_add', player: p.id, delta: -1 }) }, '−'),
    h('span', { class: 'counter' }, String(st.hotdogs[p.id] || 0)),
    h('button', { type: 'button', class: 'primary', 'aria-label': t('more_aria', p.name), onclick: () => act({ action: 'hotdog_add', player: p.id, delta: 1 }) }, '+')));
  return h('div', { class: 'card' }, h('h2', null, t('hotdog_title')),
    h('p', null, t('hotdog_total'), h('strong', null, String(sum))),
    items.length ? h('ul', { class: 'list' }, items) : h('p', { class: 'hint' }, t('no_players_short')));
}

function renderSchedule() {
  const st = state;
  const root = h('div', { class: 'card' }, h('h2', null, t('schedule_title')));
  if (st.schedule.length) {
    root.append(h('ul', { class: 'list' }, st.schedule.map((e) => h('li', null,
      h('span', { class: 'time' }, e.time), h('span', { class: 'grow' }, e.title),
      me.is_admin ? h('button', { type: 'button', class: 'small danger', 'aria-label': t('delete_entry_aria'),
        onclick: () => act({ action: 'schedule_delete', id: e.id }) }, '✕') : null))));
  } else {
    root.append(h('p', { class: 'hint' }, t('no_entries')));
  }
  if (me.is_admin) {
    const time = h('input', { type: 'text', maxlength: '16', placeholder: t('time_ph'), 'aria-label': t('time_aria') });
    const title = h('input', { type: 'text', maxlength: '80', placeholder: t('what_ph'), 'aria-label': t('title_aria') });
    const go = () => {
      if (!time.value.trim() || !title.value.trim()) { toast(t('need_time_title'), true); return; }
      act({ action: 'schedule_add', time: time.value, title: title.value });
      time.value = ''; title.value = '';
    };
    root.append(h('div', { class: 'spacer' }), h('h3', null, t('add_entry')),
      h('div', { class: 'row' }, time, title, h('button', { type: 'button', onclick: go }, t('add'))));
  }
  return root;
}

function renderInfo() {
  const root = h('div', { class: 'card' }, h('h2', null, t('info_title')));
  if (me.is_admin) {
    const ta = h('textarea', { maxlength: '5000', 'aria-label': t('info_aria'), value: state.info });
    root.append(ta, h('div', { class: 'spacer' }),
      h('button', { type: 'button', class: 'primary', onclick: () => act({ action: 'info_set', text: ta.value }).then(() => toast(t('info_saved'))) }, t('save')),
      h('p', { class: 'hint' }, t('admin_only_info')));
  } else {
    root.append(h('pre', { class: 'info' }, state.info || t('no_info')));
  }
  return root;
}

function renderPlayers() {
  const rows = state.users.map((u) => {
    const ok = typeof u.steam_url === 'string' && u.steam_url.startsWith('https://steamcommunity.com/');
    return h('li', null,
      h('strong', null, u.username),
      h('span', { class: 'grow' }, u.steam_name ? t('steam_prefix') + u.steam_name : ''),
      ok ? h('a', { href: u.steam_url, target: '_blank', rel: 'noopener noreferrer' }, t('steam_profile'))
         : h('span', { class: 'badge' }, t('no_link')));
  });
  return h('div', { class: 'card' }, h('h2', null, t('players_title')),
    rows.length ? h('ul', { class: 'list' }, rows) : h('p', { class: 'hint' }, t('no_accounts')));
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
    h('option', { value: 'name' }, t('mode_name')),
    h('option', { value: 'sound' }, t('mode_sound')),
    h('option', { value: 'both' }, t('mode_both')));
  mode.value = d.mode;
  mode.addEventListener('change', () => { d.mode = mode.value; });
  const sound = h('select', null, h('option', { value: '' }, t('no_sound')),
    st.sounds.map((s) => h('option', { value: s }, s)));
  sound.value = d.sound;
  sound.addEventListener('change', () => { d.sound = sound.value; });

  const msg = h('p', { class: 'msg', role: 'status' });
  const save = async () => {
    try {
      const st2 = await api('/api/settings', { json: Object.assign({}, d) });
      draft.settings = null;
      applyState(st2, true);
      toast(t('saved'));
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

  const settingsCard = h('div', { class: 'card' }, h('h2', null, t('my_settings')),
    h('label', null, t('steam_handle')), name,
    h('label', null, t('steam_link')), url,
    h('label', null, t('mode_label')), mode,
    h('label', null, t('sound_file')), sound,
    h('div', { class: 'spacer' }),
    h('div', { class: 'row' },
      h('button', { type: 'button', class: 'primary', onclick: save }, t('save')),
      h('button', { type: 'button', onclick: test }, t('test_btn')),
      me.is_admin ? h('button', { type: 'button', onclick: testLeader }, t('test_leader_btn')) : null),
    h('p', { class: 'hint' }, t('lang_hint')),
    msg);

  // Upload
  const file = h('input', { type: 'file', accept: '.wav,.mp3,.mp4,audio/wav,audio/mpeg,video/mp4' });
  const upMsg = h('p', { class: 'msg', role: 'status' });
  const upBtn = h('button', { type: 'button', class: 'primary' }, t('upload_btn'));
  upBtn.addEventListener('click', async () => {
    upMsg.className = 'msg'; upMsg.textContent = '';
    if (!file.files || !file.files[0]) { upMsg.className = 'msg error'; upMsg.textContent = t('choose_file'); return; }
    const fd = new FormData();
    fd.append('sound', file.files[0]);
    upBtn.disabled = true;
    upMsg.textContent = t('uploading');
    try {
      const r = await api('/api/upload', { method: 'POST', body: fd });
      upMsg.className = 'msg ok';
      upMsg.textContent = t('uploaded', r.uploaded);
      applyState(r, true);
    } catch (e) {
      upMsg.className = 'msg error';
      upMsg.textContent = t('upload_failed', e.message);
    } finally { upBtn.disabled = false; }
  });

  const soundRows = st.sounds.map((s) => h('li', null,
    h('span', { class: 'grow' }, s),
    h('audio', { controls: true, preload: 'none', src: '/sounds/' + encodeURIComponent(s) }),
    me.is_admin ? h('button', { type: 'button', class: 'small danger', onclick: () => {
      if (!confirm(t('confirm_sound', s))) return;
      api('/api/sounds/delete', { json: { name: s } }).then((r) => { applyState(r, true); toast(t('sound_deleted')); })
        .catch((e) => toast(e.message, true));
    } }, t('del')) : null));

  const uploadCard = h('div', { class: 'card' }, h('h2', null, t('upload_title')),
    h('p', { class: 'hint' }, t('upload_hint')),
    file, h('div', { class: 'spacer' }), upBtn, upMsg,
    h('div', { class: 'spacer' }), h('h3', null, t('existing')),
    soundRows.length ? h('ul', { class: 'list' }, soundRows) : h('p', { class: 'hint' }, t('no_sounds')));

  return h('div', null, settingsCard, uploadCard);
}

function renderAdmin() {
  const accounts = state.accounts || [];
  const rows = accounts.map((a) => {
    const isMe = a.id === me.id;
    const inPlayers = state.players.some((p) => p.name.toLowerCase() === a.username.toLowerCase());
    return h('li', null,
      h('strong', null, a.username),
      a.is_admin ? h('span', { class: 'badge admin' }, t('badge_admin')) : h('span', { class: 'badge' }, t('badge_user')),
      isMe ? h('span', { class: 'badge' }, t('badge_you')) : null,
      h('span', { class: 'grow' }),
      !inPlayers ? h('button', { type: 'button', class: 'small', onclick: () => act({ action: 'player_add', name: a.username }) }, t('as_player')) : null,
      h('button', { type: 'button', class: 'small', onclick: () => {
        api('/api/admin/user/admin', { json: { id: a.id, admin: !a.is_admin } })
          .then((r) => applyState(r, true)).catch((e) => toast(e.message, true));
      } }, a.is_admin ? t('revoke_admin') : t('make_admin')),
      !isMe ? h('button', { type: 'button', class: 'small danger', onclick: () => {
        if (!confirm(t('confirm_account', a.username))) return;
        api('/api/admin/user/delete', { json: { id: a.id } })
          .then((r) => applyState(r, true)).catch((e) => toast(e.message, true));
      } }, t('del')) : null);
  });
  return h('div', { class: 'card' }, h('h2', null, t('accounts_title')),
    h('p', { class: 'hint' }, t('admin_hint')),
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
    if (me) $('#conn').textContent = t('conn_lost');
  } finally {
    polling = false;
  }
}

async function boot() {
  applyStaticI18n();
  document.querySelectorAll('[data-lang]').forEach((b) => b.addEventListener('click', () => chooseLang(b.dataset.lang)));
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
