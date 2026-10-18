'use strict';

const TEXT = {
  de: { title: 'Rangliste', empty: 'Noch keine Spieler oder Punkte.', conn: '⚠ keine Verbindung' },
  en: { title: 'Leaderboard', empty: 'No players or points yet.', conn: '⚠ no connection' },
};

function startLang() {
  try {
    const saved = localStorage.getItem('lang');
    if (saved === 'de' || saved === 'en') return saved;
  } catch (e) { /* Speicher nicht verfügbar */ }
  return (navigator.language || 'de').toLowerCase().startsWith('de') ? 'de' : 'en';
}

let lang = startLang();
let rows = [];

function applyLang() {
  document.documentElement.lang = lang;
  document.getElementById('lbTitle').textContent = TEXT[lang].title;
  document.getElementById('lbEmpty').textContent = TEXT[lang].empty;
  document.querySelectorAll('[data-lang]').forEach((b) => b.classList.toggle('active', b.dataset.lang === lang));
}

function render() {
  const list = document.getElementById('lbList');
  const empty = document.getElementById('lbEmpty');
  empty.hidden = rows.length > 0;
  list.replaceChildren(...rows.map((r) => {
    const rank = 1 + rows.filter((o) => o.total > r.total).length;
    const li = document.createElement('li');
    if (r.leader) li.className = 'leader';
    const a = document.createElement('span');
    a.className = 'rank';
    a.textContent = String(rank);
    const b = document.createElement('span');
    b.textContent = (r.leader ? '★ ' : '') + r.name;
    const c = document.createElement('span');
    c.className = 'pts';
    c.textContent = String(r.total);
    li.append(a, b, c);
    return li;
  }));
}

async function load() {
  try {
    const res = await fetch('/api/leaderboard', { cache: 'no-store' });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    rows = Array.isArray(data.players) ? data.players : [];
    document.getElementById('conn').textContent = '';
    render();
  } catch (e) {
    document.getElementById('conn').textContent = TEXT[lang].conn;
  }
}

document.querySelectorAll('[data-lang]').forEach((b) => b.addEventListener('click', () => {
  lang = b.dataset.lang;
  try { localStorage.setItem('lang', lang); } catch (e) { /* ignoriert */ }
  applyLang();
  load();
}));

applyLang();
load();
setInterval(() => { if (!document.hidden) load(); }, 3000);
