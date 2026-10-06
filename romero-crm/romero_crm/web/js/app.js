// Romero Xandre CRM: arranque, navegación, actualizaciones y eventos.
import { hydrateIcons, icon } from './icons.js';
import * as F from './format.js';
import * as C from './charts.js';
import { $, $$, actions, api, esc, on, openExternal, post, setRenderHook, toast, ui } from './core.js';
import { animateIn, moveNavInk, setEffects, setupFx } from './fx.js';
import { closeSheet, openStory } from './sheet.js';
import { closeModal, modalOpen, renderTray } from './modals.js';
import { closePalette, openPalette, paletteOpen } from './palette.js';
import * as Hoy from './views/hoy.js';
import * as Noticias from './views/noticias.js';
import * as Calendario from './views/calendario.js';
import * as Historial from './views/historial.js';
import * as Ajustes from './views/ajustes.js';

const VIEWS = { hoy: Hoy, noticias: Noticias, calendario: Calendario, historial: Historial, ajustes: Ajustes };
const TITLES = { hoy: 'Hoy', noticias: 'Noticias', calendario: 'Calendario', historial: 'Historial', ajustes: 'Ajustes' };
const LEGACY = { radar: 'hoy', prediccion: 'hoy', nichos: 'noticias', google: 'noticias', x: 'noticias', wikipedia: 'noticias', youtube: 'noticias', efemerides: 'calendario' };
const NEEDS_STORIES = new Set(['hoy', 'noticias']);
let polling = null;

function routeFromHash() {
  const raw = location.hash.replace(/^#\/?/, '') || 'hoy';
  return VIEWS[raw] ? raw : LEGACY[raw] || 'hoy';
}

/* ---------- Pintar ---------- */

function loadingScreen() {
  const progress = ui.state?.progress || {};
  const labels = { google: 'Google Trends', google_week: 'Google · últimos 7 días', x: 'X (Twitter)', news: 'Medios', wikipedia: 'Wikipedia', efemerides: 'Efemérides', youtube: 'YouTube' };
  const rows = Object.entries(labels).map(([id, label]) => {
    const st = progress[id];
    const text = { ok: 'Listo', error: 'Sin respuesta', running: 'Buscando…', pending: 'En cola' }[st] || 'En cola';
    return `<div>${esc(label)}<span class="st ${esc(st || '')}">${esc(text)}</span></div>`;
  }).join('');
  return `<div class="loading"><div><div class="orbit"><i></i><i></i><i></i></div></div>
    <div><h2>Leyendo lo que pasa en España…</h2><p>La primera vez tarda unos segundos: consulto Google, X, los medios y Wikipedia.</p></div>
    <div class="progress-list">${rows}</div>${ui.state?.last_error ? `<div class="err-text">Error interno: ${esc(ui.state.last_error)}</div>` : ''}</div>`;
}

function offlineScreen() {
  const minutes = ui.settings?.refresh_minutes || 30;
  return `<div class="loading">${icon('alert')}<div><h2>No he podido leer las tendencias</h2>
    <p>Puede que no haya internet o que las fuentes no respondan. Lo volveré a intentar cada ${minutes} minutos.</p></div>
    <div class="chip-row" style="justify-content:center"><button class="btn primary" data-action="refresh">${icon('refresh')}Reintentar ahora</button><a class="btn" href="#/ajustes">Ver detalles</a></div></div>`;
}

function renderView(opts = {}) {
  const view = $('#view');
  C.hideTip();
  const noData = !ui.state?.stories?.length;
  if (NEEDS_STORIES.has(ui.route) && noData) {
    view.innerHTML = ui.state?.refreshing || !ui.state?.generated_at ? loadingScreen() : offlineScreen();
    hydrateIcons(view);
    return;
  }
  const out = VIEWS[ui.route].render();
  view.innerHTML = out.html;
  hydrateIcons(view);
  if (!opts.animate) view.querySelectorAll('.rise').forEach((el) => { el.style.animation = 'none'; el.style.opacity = '1'; el.style.transform = 'none'; });
  animateIn(view);
  if (out.mount) Promise.resolve(out.mount(view)).then(() => hydrateIcons(view));
  if (opts.focus) {
    const el = $(opts.focus);
    if (el) {
      el.focus();
      if (opts.caret !== undefined && el.setSelectionRange) el.setSelectionRange(opts.caret, opts.caret);
    }
  }
}

function renderChrome() {
  $$('#nav a').forEach((a) => a.classList.toggle('active', a.dataset.route === ui.route));
  $('#settings-link').classList.toggle('active', ui.route === 'ajustes');
  requestAnimationFrame(moveNavInk);
  document.title = `${TITLES[ui.route]} · Romero Xandre CRM`;
  $('#demo-banner').hidden = !ui.state?.app?.demo;
  const refreshing = !!ui.state?.refreshing;
  const btn = $('#refresh');
  btn.classList.toggle('spinning', refreshing);
  btn.disabled = refreshing;
  const sources = Object.values(ui.state?.sources || {}).filter((s) => s.enabled !== false && !s.requires_login);
  const failing = sources.filter((s) => s.fetched_at && !s.ok).length;
  const health = $('#health');
  health.className = `health ${failing === 0 && sources.some((s) => s.ok) ? 'ok' : failing <= 1 ? 'warn' : 'err'}`;
  btn.title = refreshing ? 'Actualizando…' : `Actualizar · ${ui.state?.generated_at ? `última vez ${F.ago(ui.state.generated_at)}` : 'sin datos aún'}${failing ? ` · ${failing} fuente${failing > 1 ? 's' : ''} con errores` : ''}`;
  renderTray();
}

function render(opts = {}) {
  const scroll = window.scrollY;
  renderChrome();
  renderView(opts);
  if (opts.keepScroll) window.scrollTo(0, scroll);
}

setRenderHook((opts = {}) => render({ keepScroll: true, ...opts }));

/* ---------- Datos y actualizaciones ---------- */

async function loadState() {
  ui.state = await api('/api/state');
  ui.lastRevision = ui.state.revision;
}

function startPolling() {
  if (polling) return;
  polling = setInterval(async () => {
    try {
      const status = await api('/api/status');
      if (ui.state) Object.assign(ui.state, { refreshing: status.refreshing, progress: status.progress, last_error: status.last_error });
      renderChrome();
      if (NEEDS_STORIES.has(ui.route) && !ui.state?.stories?.length) renderView();
      if (!status.refreshing && (status.generated_at || status.last_error)) {
        clearInterval(polling);
        polling = null;
        await reloadState();
      }
    } catch (err) {
      console.error(err);
    }
  }, 1300);
}

async function reloadState() {
  await loadState();
  ui.calendar = {};
  ui.recap = {};
  if (modalOpen() || paletteOpen()) {
    renderChrome();
    return;
  }
  render({ keepScroll: true });
  if (ui.sheet?.kind === 'story') openStory(ui.sheet.key);
}

async function backgroundCheck() {
  try {
    const status = await api('/api/status');
    if (status.refreshing) {
      if (ui.state) ui.state.refreshing = true;
      renderChrome();
      startPolling();
    } else if (status.revision !== ui.lastRevision) {
      await reloadState();
    }
  } catch (err) {
    console.error(err);
  }
}

async function refreshNow() {
  try {
    await post('/api/refresh');
    if (ui.state) ui.state.refreshing = true;
    renderChrome();
    toast('Actualizando todas las fuentes…');
    startPolling();
  } catch {
    toast('No se pudo iniciar la actualización');
  }
}

function applySettings() {
  const theme = ui.settings?.theme || 'system';
  if (theme === 'system') document.documentElement.removeAttribute('data-theme');
  else document.documentElement.setAttribute('data-theme', theme);
  setEffects(ui.settings?.effects !== false);
}

on('refresh', () => refreshNow());
on('palette', () => openPalette());

/* ---------- Eventos ---------- */

document.addEventListener('click', (event) => {
  const target = event.target;
  const ext = target.closest('a[data-ext]');
  if (ext) {
    event.preventDefault();
    openExternal(ext.getAttribute('href'));
    return;
  }
  const actionEl = target.closest('[data-action]');
  if (actionEl && actions[actionEl.dataset.action]) {
    if (actionEl.tagName === 'A') event.preventDefault();
    event.stopPropagation();
    actions[actionEl.dataset.action](actionEl, event);
    return;
  }
  const extRow = target.closest('[data-ext-url]');
  if (extRow) openExternal(extRow.dataset.extUrl);
});

document.addEventListener('change', (event) => {
  const el = event.target.closest('[data-action-change]');
  if (el && actions[el.dataset.actionChange]) actions[el.dataset.actionChange](el, event);
});

document.addEventListener('keydown', (event) => {
  const typing = event.target.matches('input, textarea, select');
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault();
    if (paletteOpen()) closePalette();
    else openPalette();
    return;
  }
  if (event.key === 'Escape') {
    if (paletteOpen()) return closePalette();
    if (modalOpen()) return closeModal();
    if ($('#sheet').classList.contains('open')) return closeSheet();
  }
  if (event.key === 'Enter' && !typing && event.target.matches('[data-action]') && !event.target.matches('button, a')) {
    event.target.click();
  }
  if (!typing && !event.metaKey && !event.ctrlKey && !event.altKey && !modalOpen() && !paletteOpen()) {
    const keys = { 1: 'hoy', 2: 'noticias', 3: 'calendario', 4: 'historial' };
    if (keys[event.key]) location.hash = `#/${keys[event.key]}`;
    if (event.key === '/') {
      event.preventDefault();
      openPalette();
    }
  }
});

$('#open-palette').addEventListener('click', () => openPalette());
$('#refresh').addEventListener('click', () => refreshNow());
$('#scrim').addEventListener('click', () => closeSheet());
$('#modal').addEventListener('click', (event) => { if (event.target.id === 'modal') closeModal(); });
window.addEventListener('scroll', () => document.body.classList.toggle('scrolled', window.scrollY > 6), { passive: true });
window.addEventListener('hashchange', () => {
  const route = routeFromHash();
  if (route === ui.route) return;
  ui.route = route;
  closeSheet();
  render({ animate: true });
  window.scrollTo(0, 0);
});
let resizeTimer = null;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => moveNavInk(), 120);
});
document.addEventListener('error', (event) => {
  if (event.target instanceof HTMLImageElement) event.target.classList.add('broken');
}, true);
document.addEventListener('romero:settings', () => {
  applySettings();
  renderChrome();
});
document.addEventListener('romero:poll', () => startPolling());

/* ---------- Arranque ---------- */

async function boot() {
  C.setupTooltip($('#tooltip'));
  setupFx();
  hydrateIcons();
  ui.route = routeFromHash();
  try {
    ui.settings = await api('/api/settings');
    applySettings();
    await loadState();
  } catch (err) {
    console.error(err);
  }
  render({ animate: true });
  if (document.fonts?.ready) document.fonts.ready.then(moveNavInk);
  if (ui.state?.refreshing || !ui.state?.generated_at) startPolling();
  setInterval(backgroundCheck, 45000);
  setInterval(() => { if (!polling) renderChrome(); }, 30000);
}

boot();
