import { icon, hydrateIcons } from './icons.js';
import * as F from './format.js';
import * as C from './charts.js';

const { esc } = F;
const TOKEN = document.querySelector('meta[name="romero-token"]')?.content || '';
const DESKTOP = new URLSearchParams(location.search).get('shell') === 'desktop';

const SOURCES = {
  google: { label: 'Google', long: 'Google Trends', icon: 'google' },
  youtube: { label: 'YouTube', long: 'YouTube', icon: 'play' },
  x: { label: 'X', long: 'X (Twitter)', icon: 'hash' },
  wikipedia: { label: 'Wikipedia', short: 'Wiki', long: 'Wikipedia', icon: 'book' },
  news: { label: 'Noticias', long: 'Noticias', icon: 'news' },
};
const SOURCE_ORDER = ['google', 'youtube', 'x', 'wikipedia', 'news'];
const PHASE_ICON = { explosivo: 'zap', subiendo: 'trending', temprana: 'signal', pico: 'minus', enfriandose: 'trendingDown' };
const LEVEL_TEXT = { hueco: 'Hueco claro', moderado: 'Competencia moderada', saturado: 'Muy competido' };

const ROUTES = [
  { group: 'Panorama' },
  { id: 'radar', label: 'Radar', icon: 'radar', title: 'Radar', subtitle: 'Lo que está pasando en España ahora mismo, y por qué.', filters: true },
  { id: 'prediccion', label: 'Predicción', icon: 'sparkles', title: 'Predicción', subtitle: 'Los temas con más recorrido: qué pasa, cuánto margen queda y si hay hueco para tu vídeo.', filters: true },
  { id: 'nichos', label: 'Nichos', icon: 'grid', title: 'Nichos', subtitle: 'Qué está pasando hoy en cada temática.' },
  { id: 'historial', label: 'Historial', icon: 'clock', title: 'Historial', subtitle: 'Qué funcionó cada día y qué nos enseña para publicar mejor.' },
  { group: 'Plataformas' },
  { id: 'google', label: 'Google', icon: 'google', source: 'google', title: 'Búsquedas en Google', subtitle: 'Tendencias de búsqueda en España de las últimas 24 horas (Google Trends).' },
  { id: 'youtube', label: 'YouTube', icon: 'play', source: 'youtube', title: 'YouTube: huecos de contenido', subtitle: 'Cuánta competencia hay en YouTube para cada tema caliente.' },
  { id: 'x', label: 'X', icon: 'hash', source: 'x', title: 'Tendencias en X', subtitle: 'Lo que se comenta ahora en X (Twitter) en España.' },
  { id: 'wikipedia', label: 'Wikipedia', icon: 'book', source: 'wikipedia', title: 'Curiosidad: Wikipedia', subtitle: 'Los artículos más leídos desde España: una pista de qué quiere entender la gente.' },
  { id: 'noticias', label: 'Noticias', icon: 'news', source: 'news', title: 'Noticias', subtitle: 'Las historias que más medios están contando hoy.' },
  { group: 'Planificar' },
  { id: 'efemerides', label: 'Efemérides', icon: 'calendar', title: 'Efemérides y aniversarios', subtitle: 'Lo que pasó tal día como hoy y los aniversarios redondos de las próximas semanas.' },
  { id: 'ajustes', label: 'Ajustes', icon: 'settings', title: 'Ajustes', subtitle: 'Tu nombre, frecuencia de actualización, apariencia y fuentes.' },
];

const ui = {
  state: null,
  settings: null,
  history: null,
  historyAt: 0,
  route: 'radar',
  niche: 'all',
  sort: 'heat',
  search: '',
  showAll: false,
  newsSection: 'portada',
  historyDay: null,
  wikiNiche: 'all',
  efemRound: false,
  efemSpain: false,
  nicheMetric: 'count',
  googleFilter: 'active',
  googleSort: 'volume',
  drawerKey: null,
  polling: null,
  lastGenerated: null,
};

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

/* ---------- API ---------- */

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', 'X-Romero-Token': TOKEN, ...(options.headers || {}) },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}
const post = (path, body = {}) => api(path, { method: 'POST', body: JSON.stringify(body) });

async function loadState() {
  ui.state = await api('/api/state');
  ui.lastGenerated = ui.state.generated_at || null;
}

async function loadHistory(force = false) {
  if (!force && ui.history && Date.now() - ui.historyAt < 120000) return ui.history;
  ui.history = await api('/api/history?days=7');
  ui.historyAt = Date.now();
  return ui.history;
}

function startPolling() {
  if (ui.polling) return;
  ui.polling = setInterval(async () => {
    try {
      const status = await api('/api/status');
      if (ui.state) {
        ui.state.refreshing = status.refreshing;
        ui.state.progress = status.progress;
        ui.state.last_error = status.last_error;
      }
      updateRefreshButton(status.refreshing);
      renderSidebarFoot();
      if (!ui.state?.topics?.length) renderView();
      const finished = !status.refreshing && (status.generated_at || status.last_error);
      if (finished) {
        clearInterval(ui.polling);
        ui.polling = null;
        await loadState();
        ui.history = null;
        render();
      }
    } catch (err) {
      console.error(err);
    }
  }, 1400);
}

async function backgroundCheck() {
  try {
    const status = await api('/api/status');
    if (status.refreshing) {
      updateRefreshButton(true);
      startPolling();
    } else if (status.generated_at && status.generated_at !== ui.lastGenerated) {
      await loadState();
      ui.history = null;
      render(true);
    } else {
      renderSidebarFoot();
    }
  } catch (err) {
    console.error(err);
  }
}

/* ---------- Helpers ---------- */

function norm(text) {
  return String(text || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

function capitalize(text) {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
}

function nicheName(id) {
  return ui.state?.niches?.find((n) => n.id === id)?.name || id || '—';
}

function nicheChip(id) {
  return `<span class="chip">${esc(nicheName(id))}</span>`;
}

function storyChip(topic) {
  return topic.story ? `<span class="story-chip" title="Forma parte de la historia «${esc(topic.story.title)}»">${icon('link')}${esc(topic.story.title)}</span>` : '';
}

function sourceBadges(list) {
  return `<span class="srcs">${SOURCE_ORDER.filter((s) => list.includes(s))
    .map((s) => `<span class="src src-${s}"><i></i>${esc(SOURCES[s].short || SOURCES[s].label)}</span>`).join('')}</span>`;
}

function sourceCount(list) {
  const present = SOURCE_ORDER.filter((s) => list.includes(s));
  const names = present.map((s) => SOURCES[s].long).join(', ');
  const dots = present.map((s) => `<i class="src-dot src-${s}"></i>`).join('');
  return `<span class="src-count" title="${esc(names)}"><span class="src-dots" aria-hidden="true">${dots}</span>${present.length === 1 ? esc(SOURCES[present[0]].long) : `${present.length} fuentes`}</span>`;
}

function phaseChip(topic) {
  return `<span class="phase phase-${esc(topic.phase)}" title="${esc(topic.phase_reason || '')}">${icon(PHASE_ICON[topic.phase] || 'minus')}${esc(topic.phase_label)}</span>`;
}

function meter(value, big = false) {
  return `<span class="meter${big ? ' big' : ''}"><span class="meter-track"><i style="width:${Math.max(2, Math.min(100, value))}%"></i></span><b>${esc(value)}</b></span>`;
}

function extLink(url, label, cls = '') {
  const safe = F.safeUrl(url);
  if (!safe) return esc(label);
  return `<a href="${esc(safe)}" class="${cls}" data-ext="1" target="_blank" rel="noopener noreferrer">${label}</a>`;
}

function metricMain(topic) {
  const m = topic.metric || {};
  if (m.value === null || m.value === undefined) return '—';
  return `${F.num(m.value)}${m.plus ? '+' : ''}`;
}

function metricSub(topic) {
  const m = topic.metric || {};
  const parts = [];
  if (m.kind) parts.push(m.kind);
  if (topic.growth_pct) parts.push(`<span class="up">${F.pct(topic.growth_pct)}</span>`);
  return parts.join(' · ');
}

function seriesDescriber(topic) {
  const n = (topic.series || []).length;
  return (value, i) => {
    const back = n - 1 - i;
    switch (topic.series_kind) {
      case 'google_volume': {
        const ts = (topic.series_end || Date.now() / 1000) - back * (topic.series_step || 3600);
        return { value: value > 0 ? `${F.num(value)}+` : 'Sin registrar', label: 'búsquedas acumuladas', title: back === 0 ? 'Ahora' : F.clock(ts) };
      }
      case 'x':
        return { value: value > 0 ? `Nº ${Math.round(51 - value)}` : 'Fuera del top', label: 'en X', title: back === 0 ? 'Ahora' : `Hace ${back} h` };
      case 'wikipedia':
        return { value: `${F.num(value)} lecturas`, label: 'desde España', title: back === 0 ? 'Último día' : `${back} días antes` };
      default:
        return { value: F.num(value) };
    }
  };
}

function published(video) {
  if (video.age_seconds) return ` · ${esc(F.ago(Date.now() / 1000 - video.age_seconds))}`;
  return '';
}

function topicByKey(key) {
  return ui.state?.topics?.find((t) => t.key === key);
}

function visibleTopics() {
  let list = ui.state?.topics || [];
  if (ui.settings?.hide_utility !== false) list = list.filter((t) => !t.utility);
  if (ui.niche !== 'all') list = list.filter((t) => (t.niches || [t.niche]).includes(ui.niche));
  if (ui.search) {
    const q = norm(ui.search);
    list = list.filter((t) => norm(`${t.title} ${(t.related || []).join(' ')} ${t.description || ''}`).includes(q));
  }
  return list;
}

function sortTopics(list, sort) {
  const copy = [...list];
  const by = {
    heat: (a, b) => b.heat - a.heat,
    potential: (a, b) => b.potential - a.potential,
    volume: (a, b) => (b.metric?.value || 0) - (a.metric?.value || 0),
    recent: (a, b) => (b.started_at || 0) - (a.started_at || 0),
  }[sort] || ((a, b) => b.heat - a.heat);
  return copy.sort(by);
}

function sourceStatus(id) {
  return ui.state?.sources?.[id] || {};
}

function emptyState(iconName, title, text, extra = '') {
  return `<div class="empty">${icon(iconName)}<h3>${esc(title)}</h3><p>${text}</p>${extra}</div>`;
}

function sourceError(id, extraButtons = '') {
  const st = sourceStatus(id);
  if (st.enabled === false) {
    return `<div class="card">${emptyState('settings', `${SOURCES[id]?.long || id} está desactivado`, 'Puedes activarlo en Ajustes.', '<a class="btn btn-sm" href="#/ajustes">Ir a Ajustes</a>')}</div>`;
  }
  return `<div class="card">${emptyState('alert', `No hay datos de ${SOURCES[id]?.long || id} ahora mismo`,
    'El resto del programa sigue funcionando. Se volverá a intentar en la próxima actualización.',
    `${st.error ? `<div class="err-text">${esc(st.error)}</div>` : ''}<div class="actions"><button class="btn btn-sm" data-action="refresh">${icon('refresh')}Reintentar</button>${extraButtons}</div>`)}</div>`;
}

function staleNote(id) {
  const st = sourceStatus(id);
  if (!st.stale) return '';
  return `<div class="note muted small">Mostrando los últimos datos guardados (${F.ago(st.fetched_at)}): el último intento falló.</div>`;
}

function toast(message) {
  const el = $('#toast');
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { el.hidden = true; }, 2200);
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const area = document.createElement('textarea');
    area.value = text;
    document.body.appendChild(area);
    area.select();
    document.execCommand('copy');
    area.remove();
  }
  toast('Copiado al portapapeles');
}

function openExternal(url) {
  const safe = F.safeUrl(url);
  if (!safe) return;
  if (DESKTOP) post('/api/open', { url: safe }).catch(() => window.open(safe, '_blank', 'noopener'));
  else window.open(safe, '_blank', 'noopener');
}

/* ---------- Shell ---------- */

function renderNav() {
  const counts = {
    radar: visibleTopics().length,
    google: ui.state?.platforms?.google?.filter((g) => g.active).length,
    x: ui.state?.platforms?.x?.length,
    wikipedia: ui.state?.platforms?.wikipedia?.length,
    youtube: ui.state?.platforms?.youtube?.length,
  };
  $('#nav').innerHTML = ROUTES.filter((r) => r.id !== 'ajustes').map((r) => {
    if (r.group) return `<div class="nav-group">${esc(r.group)}</div>`;
    const st = r.source ? sourceStatus(r.source) : null;
    const failing = st && st.enabled !== false && st.ok === false && st.fetched_at && !st.requires_login;
    const side = failing ? '<span class="dot err" title="Error en la fuente"></span>'
      : counts[r.id] ? `<span class="count">${counts[r.id]}</span>` : '';
    return `<a href="#/${r.id}" class="${ui.route === r.id ? 'active' : ''}">${icon(r.icon)}<span>${esc(r.label)}</span>${side}</a>`;
  }).join('');
}

function renderSidebarFoot() {
  const st = ui.state?.sources || {};
  const progress = ui.state?.progress || {};
  const refreshing = ui.state?.refreshing;
  const dots = SOURCE_ORDER.map((id) => {
    const s = st[id] || {};
    let cls = '';
    if (refreshing && ['pending', 'running'].includes(progress[id])) cls = 'run';
    else if (s.enabled === false || s.requires_login) cls = '';
    else if (s.ok) cls = 'ok';
    else if (s.fetched_at) cls = 'err';
    return `<i class="${cls}" title="${esc(SOURCES[id].long)}: ${esc(s.ok ? 'correcto' : s.requires_login ? 'requiere cuenta' : s.error || 'sin datos')}"></i>`;
  }).join('');
  const okCount = SOURCE_ORDER.filter((id) => st[id]?.ok).length;
  const usable = SOURCE_ORDER.filter((id) => st[id]?.enabled !== false && !st[id]?.requires_login).length;
  const updated = ui.state?.generated_at ? `Actualizado ${F.ago(ui.state.generated_at)}` : 'Sin datos todavía';
  $('#sidebar-foot').innerHTML = `
    <div class="health"><span class="health-dots">${dots}</span><span>${refreshing ? 'Actualizando…' : `${okCount}/${usable} fuentes`}</span></div>
    <div class="updated">${esc(updated)}</div>
    <a href="#/ajustes" class="nav-foot-link ${ui.route === 'ajustes' ? 'active' : ''}">${icon('settings')}Ajustes</a>`;
}

function renderHeader() {
  const route = ROUTES.find((r) => r.id === ui.route) || ROUTES[1];
  $('#page-title').textContent = route.title;
  $('#page-subtitle').textContent = route.subtitle;
  document.title = `${route.label} · Romero CRM`;
  $('#demo-banner').hidden = !ui.state?.app?.demo;
  const theme = ui.settings?.theme || 'system';
  $('#theme-toggle').innerHTML = icon({ system: 'monitor', light: 'sun', dark: 'moon' }[theme]);
  $('#theme-toggle').title = { system: 'Tema: automático', light: 'Tema: claro', dark: 'Tema: oscuro' }[theme];
}

function renderFilters() {
  const route = ROUTES.find((r) => r.id === ui.route);
  const el = $('#filters');
  if (!route?.filters || !ui.state?.topics?.length) {
    el.innerHTML = '';
    return;
  }
  const base = (ui.state.topics || []).filter((t) => ui.settings?.hide_utility === false || !t.utility);
  const counts = {};
  for (const t of base) for (const n of new Set(t.niches || [t.niche])) counts[n] = (counts[n] || 0) + 1;
  const niches = (ui.state.niches || []).filter((n) => counts[n.id]).sort((a, b) => counts[b.id] - counts[a.id]);
  const nicheChips = [`<button class="fchip ${ui.niche === 'all' ? 'on' : ''}" data-niche="all">Todos <span class="n">${base.length}</span></button>`]
    .concat(niches.map((n) => `<button class="fchip ${ui.niche === n.id ? 'on' : ''}" data-niche="${esc(n.id)}">${esc(n.name)} <span class="n">${counts[n.id]}</span></button>`));
  el.innerHTML = `<div class="chip-scroll" id="chip-scroll">${nicheChips.join('')}</div>`;
  const scroller = $('#chip-scroll');
  scroller.addEventListener('wheel', (event) => {
    if (Math.abs(event.deltaY) > Math.abs(event.deltaX)) {
      scroller.scrollLeft += event.deltaY;
      event.preventDefault();
    }
  }, { passive: false });
}

function updateRefreshButton(refreshing) {
  const btn = $('#refresh');
  btn.classList.toggle('spinning', !!refreshing);
  btn.disabled = !!refreshing;
  $('.label', btn).textContent = refreshing ? 'Actualizando…' : 'Actualizar';
}

function render(keepScroll = false) {
  const main = $('.main');
  const scroll = main.scrollTop;
  renderNav();
  renderSidebarFoot();
  renderHeader();
  renderFilters();
  renderView();
  updateRefreshButton(ui.state?.refreshing);
  hydrateIcons();
  if (keepScroll) main.scrollTop = scroll;
}

function renderView() {
  const view = $('#view');
  C.hideTip();
  if (!ui.state || (!ui.state.topics?.length && !ui.state.generated_at)) {
    view.innerHTML = loadingScreen();
    return;
  }
  const noTopics = !ui.state.topics?.length;
  if (noTopics && ui.state.refreshing && ['radar', 'prediccion', 'nichos'].includes(ui.route)) {
    view.innerHTML = loadingScreen();
    return;
  }
  if (noTopics && ['radar', 'prediccion', 'nichos'].includes(ui.route)) {
    view.innerHTML = offlineScreen();
    hydrateIcons(view);
    return;
  }
  const renderer = VIEWS[ui.route] || VIEWS.radar;
  const out = renderer();
  view.innerHTML = out.html;
  hydrateIcons(view);
  if (out.mount) requestAnimationFrame(() => out.mount(view));
}

function offlineScreen() {
  const st = ui.state?.sources || {};
  const rows = ['google', 'x', 'wikipedia', 'news'].map((id) => {
    const s = st[id] || {};
    const state = s.enabled === false ? 'Desactivada' : s.ok ? 'Correcto' : 'Sin respuesta';
    return `<div>${icon(SOURCES[id].icon)}${esc(SOURCES[id].long)}<span class="st ${s.ok ? 'ok' : 'error'}" title="${esc(s.error || '')}">${esc(state)}</span></div>`;
  }).join('');
  const minutes = ui.settings?.refresh_minutes || 30;
  return `<div class="loading-screen">${icon('alert')}<h2>No he podido descargar tendencias</h2>
    <p>Puede que no haya conexión a internet o que las fuentes no respondan ahora mismo.<br>Lo volveré a intentar solo cada ${minutes} minutos.</p>
    <div class="progress-list">${rows}</div>
    <div class="actions" style="justify-content:center"><button class="btn btn-primary" data-action="refresh">${icon('refresh')}Reintentar ahora</button>
    <a class="btn" href="#/ajustes">Ver detalles</a></div></div>`;
}

function loadingScreen() {
  const progress = ui.state?.progress || {};
  const labels = { google: 'Google Trends', google_week: 'Google · historial 7 días', x: 'X (Twitter)', wikipedia: 'Wikipedia', news: 'Noticias', efemerides: 'Efemérides', youtube: 'YouTube' };
  const rows = Object.keys(labels).map((id) => {
    const st = progress[id];
    const text = { ok: 'Listo', error: 'Sin respuesta', running: 'Buscando…', pending: 'En cola' }[st] || 'En cola';
    return `<div>${icon(SOURCES[id]?.icon || 'calendar')}${esc(labels[id])}<span class="st ${esc(st || '')}">${esc(text)}</span></div>`;
  }).join('');
  return `<div class="loading-screen"><div class="radar-anim"></div><h2>Buscando tendencias en España…</h2>
    <p>La primera vez tarda unos segundos: consulto Google, X, Wikipedia y los medios.</p>
    <div class="progress-list">${rows}</div>
    ${ui.state?.last_error ? `<div class="err-text">Error interno: ${esc(ui.state.last_error)}</div>` : ''}</div>`;
}

/* ---------- Explicaciones ---------- */

function greeting() {
  const hour = new Date().getHours();
  const hello = hour < 6 ? 'Buenas noches' : hour < 14 ? 'Buenos días' : hour < 21 ? 'Buenas tardes' : 'Buenas noches';
  const name = (ui.settings?.name || '').trim();
  return `${hello}${name ? `, ${name}` : ''}`;
}

function whatHtml(t) {
  if (!t.what) return '';
  if (t.what_subject) return `<p class="explain"><span class="ex-label">Contexto</span><span class="ex-text">${esc(t.what_subject)}: ${esc(t.what.charAt(0).toLowerCase() + t.what.slice(1))}</span></p>`;
  return `<p class="explain"><span class="ex-label">Qué es</span><span class="ex-text">${esc(t.what)}</span></p>`;
}

function whyHtml(t) {
  if (t.why) {
    const meta = [t.why.source, t.why.published ? F.ago(t.why.published) : ''].filter(Boolean).join(' · ');
    return `<p class="explain why"><span class="ex-label">Qué pasa</span><span class="ex-text">${esc(t.why.title)}${meta ? ` <span class="ex-src">${esc(meta)}</span>` : ''}</span></p>`;
  }
  if (t.story) return `<p class="explain why"><span class="ex-label">Qué pasa</span><span class="ex-text">Forma parte de la historia «${esc(t.story.title)}».</span></p>`;
  return `<p class="explain why muted-why"><span class="ex-label">Qué pasa</span><span class="ex-text">Todavía no hay titulares que lo expliquen: es una conversación de redes o de búsquedas. ${esc(t.phase_reason || '')}</span></p>`;
}

function shortWhy(t) {
  if (t.why) return t.why.title;
  if (t.what) return t.what_subject ? `Sobre ${t.what_subject}: ${t.what}` : t.what;
  if (t.story) return `Parte de «${t.story.title}»`;
  return t.phase_reason || '';
}

function youtubeChip(t) {
  const yt = t.youtube;
  if (!yt || !yt.level) return '';
  const text = { hueco: 'Hueco en YouTube', moderado: 'YouTube: competencia media', saturado: 'YouTube muy competido' }[yt.level] || yt.label;
  return `<span class="level level-${esc(yt.level)}"><i></i>${esc(text)}</span>`;
}

function storyCard(t, i) {
  return `<article class="story" data-topic="${esc(t.key)}" tabindex="0">
    <div class="story-top">
      <span class="story-rank">${i + 1}</span>
      <div class="story-head"><h3>${esc(t.title)}</h3><div class="story-meta">${phaseChip(t)}${nicheChip(t.niche)}${youtubeChip(t)}</div></div>
      <div class="story-heat" title="Calor: alcance, impulso, presencia en varias plataformas y frescura"><b>${t.heat}</b><span>calor</span></div>
    </div>
    ${whyHtml(t)}
    ${whatHtml(t)}
    <div class="story-foot"><span class="story-summary">${esc(t.summary || '')}</span><span class="story-spark" data-spark="${esc(t.key)}"></span></div>
  </article>`;
}

function topicList(list, limit, offset = 0) {
  if (!list.length) return emptyState('search', 'Nada con estos filtros', 'Prueba con otro nicho o borra la búsqueda.');
  const rows = list.slice(0, limit).map((t, i) => `
    <tr tabindex="0" data-topic="${esc(t.key)}">
      <td class="rank">${i + 1 + offset}</td>
      <td><div class="t-title">${esc(t.title)}</div><div class="t-why">${esc(shortWhy(t))}</div></td>
      <td class="hide-sm">${nicheChip(t.niche)}</td>
      <td>${meter(t.heat)}</td>
      <td class="num"><div class="num-main">${metricMain(t)}</div><div class="num-sub">${esc(t.metric?.kind || '')}</div></td>
      <td>${phaseChip(t)}</td>
    </tr>`).join('');
  const cols = '<colgroup><col style="width:44px"><col><col class="hide-sm" style="width:150px"><col style="width:96px"><col style="width:108px"><col style="width:128px"></colgroup>';
  return `<table class="ttable fixed">${cols}<thead><tr><th>#</th><th>Tema y por qué</th><th class="hide-sm">Nicho</th><th>Calor</th><th class="num">Volumen</th><th>Fase</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function historyInsights(history) {
  const out = [];
  const hours = history.start_hours || [];
  if (hours.some((v) => v > 0)) {
    let best = 0;
    for (let h = 0; h < 24; h += 1) if ((hours[h] || 0) + (hours[(h + 1) % 24] || 0) > (hours[best] || 0) + (hours[(best + 1) % 24] || 0)) best = h;
    out.push(`Las tendencias arrancan sobre todo entre las <b>${best}:00 y las ${(best + 2) % 24}:00</b>. Publicar justo antes te pone en la ola desde el principio.`);
  }
  const all = history.lifecycle_all;
  const life = (history.lifecycle || []).filter((l) => l.count >= 3);
  if (all) {
    let text = `Una tendencia dura de media <b>${esc(F.hours(all.median))}</b> en Google`;
    if (life.length >= 2) {
      const sorted = [...life].sort((a, b) => a.median - b.median);
      text += `: las de ${esc(sorted[0].name)} se apagan antes (~${esc(F.hours(sorted[0].median))}) y las de ${esc(sorted[sorted.length - 1].name)} aguantan más (~${esc(F.hours(sorted[sorted.length - 1].median))})`;
    }
    out.push(`${text}.`);
  }
  const hm = history.heatmap;
  if (hm?.niches?.length) {
    const totals = hm.niches.map((n, i) => ({ name: n.name, id: n.id, total: (hm.values[i] || []).reduce((a, b) => a + b, 0) }))
      .filter((n) => n.id !== 'otros').sort((a, b) => b.total - a.total).slice(0, 3);
    if (totals.length) out.push(`Los nichos con más tendencias esta semana: ${totals.map((n) => `<b>${esc(n.name)}</b> (${n.total})`).join(', ')}.`);
  }
  const recurring = (history.recurring || []).slice(0, 3);
  if (recurring.length) out.push(`Vuelven una y otra vez: ${recurring.map((r) => `<b>${esc(r.title)}</b>`).join(', ')}. Son temas con interés de fondo, buenos para piezas atemporales.`);
  return out;
}

/* ---------- Views ---------- */

function kpiTile({ label, iconName, value, sub, text = false, topic = null }) {
  return `<div class="card kpi ${topic ? 'clickable' : ''}" ${topic ? `data-topic="${esc(topic)}" tabindex="0"` : ''}>
    <div class="kpi-label">${icon(iconName)}${esc(label)}</div>
    <div class="kpi-value ${text ? 'text' : ''}">${value}</div>
    <div class="kpi-sub">${sub}</div></div>`;
}

function topicTable(list, limit) {
  if (!list.length) {
    return emptyState('search', 'Nada con estos filtros', 'Prueba con otro nicho, otra fuente o borra la búsqueda.');
  }
  const rows = list.slice(0, limit).map((t, i) => `
    <tr tabindex="0" data-topic="${esc(t.key)}">
      <td class="rank">${i + 1}</td>
      <td><div class="t-title">${esc(t.title)}</div>
        <div class="t-meta">${nicheChip(t.niche)}${storyChip(t)}${sourceCount(t.sources)}${t.started_at ? `<span>· ${esc(F.ago(t.started_at))}</span>` : ''}</div></td>
      <td>${meter(t.heat)}</td>
      <td class="num"><div class="num-main">${metricMain(t)}</div><div class="num-sub">${metricSub(t)}</div></td>
      <td class="hide-sm evo"><div data-spark="${esc(t.key)}"></div></td>
      <td>${phaseChip(t)}</td>
    </tr>`).join('');
  const cols = '<colgroup><col style="width:40px"><col><col style="width:100px"><col style="width:116px"><col class="hide-sm" style="width:124px"><col style="width:128px"></colgroup>';
  return `<table class="ttable fixed">${cols}<thead><tr><th>#</th><th>Tema</th><th>Calor</th><th class="num">Volumen</th><th class="hide-sm">Evolución</th><th>Fase</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function mountSparks(root) {
  $$('[data-spark]', root).forEach((el) => {
    const topic = topicByKey(el.dataset.spark);
    if (!topic) return;
    const wide = el.dataset.sparkWide === '1';
    el.replaceChildren(C.sparkline(topic.series, {
      describe: seriesDescriber(topic),
      ariaLabel: topic.series_label,
      width: wide ? Math.max(220, el.clientWidth) : undefined,
      height: wide ? 46 : undefined,
    }));
  });
}

function upcomingHighlights(limit) {
  return (ui.state?.efemerides?.highlights || []).slice(0, limit);
}

function efemItem(item, clickable = true) {
  const round = item.round_level >= 1;
  return `<div class="li" ${clickable && item.url ? `data-ext-url="${esc(item.url)}"` : ''}>
    <div class="year-badge ${round ? 'round' : ''}"><b>${esc(item.years_ago)}</b><span>años</span></div>
    <div class="li-main"><div class="li-title wrap">${esc(item.title || item.text)}</div>
      <div class="li-sub wrap">${esc(F.daysUntil(item.date))} · ${esc(F.day(item.date))} de ${esc(item.year)} · ${esc(item.text)}</div></div></div>`;
}

const VIEWS = {
  radar() {
    const list = sortTopics(visibleTopics(), ui.sort);
    const top = list.slice(0, 5);
    const rest = list.slice(5);
    const limit = ui.showAll ? rest.length : 20;
    const k = ui.state.kpis || {};
    const pulse = [
      `${F.full(list.length)} temas en el radar`,
      k.rising ? `${F.full(k.rising)} subiendo ahora` : '',
      k.top_volume ? `lo más buscado: ${k.top_volume.title} (${F.num(k.top_volume.value)}+)` : '',
    ].filter(Boolean).join(' · ');
    const sortSeg = ['heat', 'potential', 'recent'].map((s) =>
      `<button class="${ui.sort === s ? 'on' : ''}" data-sort="${s}">${{ heat: 'Más calientes', potential: 'Más potencial', recent: 'Más recientes' }[s]}</button>`).join('');
    const html = `
      <div class="hello"><h2>${esc(greeting())}. Esto es lo que está pasando.</h2><p>${esc(pulse)}${ui.state.generated_at ? ` · actualizado ${esc(F.ago(ui.state.generated_at))}` : ''}</p></div>
      <div class="section-head"><h2>Lo importante ahora</h2><div class="seg">${sortSeg}</div></div>
      ${top.length ? `<div class="story-grid">${top.map((t, i) => storyCard(t, i)).join('')}</div>` : `<div class="card">${emptyState('search', 'Nada con estos filtros', 'Prueba con otro nicho o borra la búsqueda.')}</div>`}
      ${rest.length ? `<div class="card mt-16"><div class="card-head"><div><h2>Más temas</h2><p>${rest.length} temas más · pulsa uno para ver la explicación completa</p></div></div>
        <div class="card-body flush">${topicList(rest, limit, 5)}
          ${rest.length > limit ? `<div style="padding:10px 18px"><button class="btn btn-sm" data-action="show-all">Ver los ${rest.length} temas</button></div>` : ''}</div></div>` : ''}`;
    return { html, mount: mountSparks };
  },

  prediccion() {
    const all = visibleTopics();
    const rising = sortTopics(all.filter((t) => ['explosivo', 'subiendo', 'temprana'].includes(t.phase)), 'potential').slice(0, 12);
    const cards = rising.length ? rising.map((t) => {
      const typical = t.typical_hours || 20;
      const elapsed = t.elapsed_hours;
      const used = elapsed !== null && elapsed !== undefined ? Math.min(100, (elapsed / typical) * 100) : null;
      const windowHtml = used !== null ? `<div class="window">
          <div class="window-head"><span>Lleva ${esc(F.hours(elapsed))}</span><span>Suele durar ~${esc(F.hours(typical))}</span></div>
          <div class="window-track"><i style="width:${used.toFixed(1)}%"></i></div>
          <div class="small muted">${t.remaining_hours > 0 ? `Margen para publicar: <b style="color:var(--text)">~${esc(F.hours(t.remaining_hours))}</b>` : 'Margen casi agotado: busca un ángulo de fondo, no de última hora.'}</div></div>`
        : '';
      return `<article class="card pred" data-topic="${esc(t.key)}" tabindex="0">
        <div class="pred-top"><div><div class="pred-title">${esc(t.title)}</div><div class="row-gap mt-8">${phaseChip(t)}${nicheChip(t.niche)}${youtubeChip(t)}</div></div>
          <div class="pred-score" title="Potencial: el calor ajustado por la fase y el margen que le queda"><b>${t.potential}</b><span>potencial</span></div></div>
        ${whyHtml(t)}
        ${whatHtml(t)}
        <p class="signal">${icon(PHASE_ICON[t.phase] || 'trending')}<span>${esc(t.phase_reason || '')}</span></p>
        ${windowHtml}
      </article>`;
    }).join('') : `<div class="card">${emptyState('sparkles', 'Ningún tema despegando con estos filtros', 'Quita filtros o vuelve en un rato.')}</div>`;
    const highlights = upcomingHighlights(8);
    const html = `
      <details class="howto"><summary>${icon('info')}¿Cómo se calcula?</summary>
        <div class="how">
          <div><b>${icon('flame')} Calor (0–100)</b><span>Alcance (volumen o posición), impulso (crecimiento), presencia en varias plataformas y frescura.</span></div>
          <div><b>${icon('sparkles')} Potencial (0–100)</b><span>El calor ajustado por la fase y por el margen que le queda. Es lo que te interesa para publicar.</span></div>
          <div><b>${icon('trending')} Fase</b><span>Explosivo, en ascenso, señal temprana, en pico o enfriándose, según cómo cambian las búsquedas, la posición en X y las lecturas.</span></div>
          <div><b>${icon('clock')} Margen</b><span>Cuánto suelen durar las tendencias de ese nicho (con tu propio historial) menos lo que ya lleva.</span></div>
        </div><p class="note mt-8">Son estimaciones con datos públicos, no adivinación: sirven para priorizar, no son una garantía.</p></details>
      <div class="pred-grid">${cards}</div>
      <div class="card"><div class="card-head"><div><h2>Para preparar con antelación</h2><p>Aniversarios redondos de las próximas semanas: los medios hablarán de ellos</p></div><a class="link small" href="#/efemerides">Calendario completo</a></div>
        <div class="card-body flush"><div class="list">${highlights.length ? highlights.map((e) => efemItem(e)).join('') : emptyState('calendar', 'Sin aniversarios redondos en 30 días', '')}</div></div></div>`;
    return { html };
  },

  nichos() {
    const stats = (ui.state.niche_stats || []).filter((n) => n.count);
    const momentum = Object.fromEntries((ui.state.predictions?.niche_momentum || []).map((m) => [m.id, m]));
    const named = stats.filter((n) => n.id !== 'otros');
    const hot = named.slice(0, 2).map((n) => `${n.name} (${n.count} temas)`);
    const rising = named.filter((n) => (momentum[n.id]?.delta || 0) >= 3).map((n) => n.name);
    const intro = named.length ? `Hoy dominan ${hot.join(' y ')}.${rising.length ? ` Más activo que de costumbre: ${rising.join(', ')}.` : ''}` : '';
    const cards = stats.map((n) => {
      const m = momentum[n.id];
      const badge = m && m.delta >= 3 ? '<span class="trend-badge up">↑ Más activo que de costumbre</span>'
        : m && m.delta <= -3 ? '<span class="trend-badge down">↓ Más flojo que de costumbre</span>' : '';
      const topics = (n.top || []).map((x) => topicByKey(x.key)).filter(Boolean).map((t) => `
        <li data-topic="${esc(t.key)}" tabindex="0"><b>${esc(t.title)}</b><span>${esc(shortWhy(t))}</span></li>`).join('');
      return `<div class="card niche-card">
        <div class="niche-head"><h3>${esc(n.name)}</h3><span class="niche-count">${n.count} ${n.count === 1 ? 'tema' : 'temas'}</span></div>
        ${badge}
        <ul class="niche-topics">${topics}</ul>
        <button class="link small" data-go-niche="${esc(n.id)}">Ver ${n.count === 1 ? 'el tema' : `los ${n.count}`} en el radar →</button>
      </div>`;
    }).join('');
    return { html: `${intro ? `<p class="intro">${esc(intro)}</p>` : ''}<div class="niche-grid">${cards || emptyState('grid', 'Sin datos todavía', '')}</div>` };
  },

  historial() {
    const html = `<div id="history-root"><div class="card"><div class="card-body"><div class="spinner"></div></div></div></div>`;
    return {
      html,
      async mount(root) {
        let history;
        try {
          history = await loadHistory();
        } catch {
          $('#history-root', root).innerHTML = `<div class="card">${emptyState('alert', 'No se pudo cargar el historial', '')}</div>`;
          return;
        }
        const container = $('#history-root', root);
        if (!container) return;
        const days = history.days || [];
        if (!ui.historyDay || !days.find((d) => d.day === ui.historyDay)) {
          ui.historyDay = (days.find((d) => d.google_count >= 5) || days.find((d) => d.google_count > 0) || days[0])?.day;
        }
        const current = days.find((d) => d.day === ui.historyDay) || { top_searches: [] };
        const dayChips = days.map((d) => `<button class="fchip ${d.day === ui.historyDay ? 'on' : ''}" data-history-day="${esc(d.day)}">${esc(F.day(d.day))} <span class="n">${d.google_count}</span></button>`).join('');
        const searches = current.top_searches.filter((s) => ui.settings?.hide_utility === false || !s.utility).slice(0, 10);
        const rows = searches.length ? searches.map((s, i) => {
          const lasted = s.duration_hours !== null ? `duró ${F.hours(s.duration_hours)}` : (s.active ? 'sigue activa' : '');
          return `<div class="li"><div class="rank">${i + 1}</div><div class="li-main"><div class="li-title">${esc(s.title)}</div>
            <div class="li-sub">${esc(nicheName(s.niche))} · empezó a las ${esc(F.clock(s.started))}${lasted ? ` · ${esc(lasted)}` : ''}</div></div>
            <div class="li-side"><b>${F.num(s.volume)}+</b><div class="small muted">búsquedas</div></div></div>`;
        }).join('') : emptyState('clock', 'Sin búsquedas registradas ese día', 'El historial se completa a medida que usas el programa.');
        const recurring = (history.recurring || []).slice(0, 8).map((r) => `
          <div class="li"><div class="li-main"><div class="li-title">${esc(r.title)}</div><div class="li-sub">${esc(nicheName(r.niche))}</div></div>
          <div class="li-side"><b>${r.days}</b> <span class="small muted">días</span></div></div>`).join('');
        container.innerHTML = `
          <div class="chip-row" style="margin-bottom:16px">${dayChips}</div>
          <div class="grid cols-12">
            <div class="card span-7"><div class="card-head"><div><h2>Lo más buscado · ${esc(F.longDate(ui.historyDay))}</h2><p>Tendencias de Google que arrancaron ese día</p></div></div>
              <div class="card-body flush"><div class="list">${rows}</div></div></div>
            <div class="stack span-5">
              <div class="card"><div class="card-head"><div><h2>Lo que nos enseña</h2><p>Conclusiones de la última semana</p></div></div>
                <div class="card-body"><ul class="insights">${historyInsights(history).map((x) => `<li>${x}</li>`).join('') || '<li>Hace falta algo más de historial para sacar conclusiones.</li>'}</ul></div></div>
              <div class="card"><div class="card-head"><div><h2>Temas que vuelven</h2><p>Se buscan varios días: interés de fondo</p></div></div>
                <div class="card-body flush"><div class="list">${recurring || emptyState('refresh', 'Todavía no hay temas repetidos', '')}</div></div></div>
            </div>
          </div>`;
        hydrateIcons(container);
      },
    };
  },

  google() {
    const st = sourceStatus('google');
    const items = ui.state.platforms?.google || [];
    if (!items.length) return { html: sourceError('google') };
    let list = ui.googleFilter === 'active' ? items.filter((i) => i.active) : items;
    if (ui.settings?.hide_utility !== false) list = list.filter((i) => !isUtilityTitle(i));
    if (ui.search) list = list.filter((i) => norm(`${i.title} ${(i.related || []).join(' ')}`).includes(norm(ui.search)));
    const sorters = { volume: (a, b) => b.volume - a.volume, growth: (a, b) => (b.growth_pct || 0) - (a.growth_pct || 0), recent: (a, b) => (b.started_at || 0) - (a.started_at || 0) };
    list = [...list].sort(sorters[ui.googleSort]);
    const rows = list.map((g, i) => {
      const topic = topicForSource('google', g.id);
      return `<tr tabindex="0" ${topic ? `data-topic="${esc(topic.key)}"` : `data-ext-url="${esc(g.url)}"`}>
        <td class="rank">${i + 1}</td>
        <td><div class="t-title">${esc(g.title)}</div><div class="t-meta">${nicheChip(g.niche)}${(g.related || []).slice(0, 3).map((r) => `<span>${esc(r)}</span>`).join(' · ')}</div></td>
        <td class="num"><div class="num-main">${F.num(g.volume)}+</div><div class="num-sub">búsquedas</div></td>
        <td class="num"><div class="num-main up">${F.pct(g.growth_pct)}</div><div class="num-sub">crecimiento</div></td>
        <td class="num"><div class="num-main">${esc(F.clock(g.started_at))}</div><div class="num-sub">${esc(F.ago(g.started_at))}</div></td>
        <td class="hide-sm"><div data-gspark="${esc(g.id)}"></div></td>
        <td>${g.active ? '<span class="chip">Activa</span>' : '<span class="chip" style="opacity:.7">Terminada</span>'}</td>
      </tr>`;
    }).join('');
    const seg = `<div class="seg"><button class="${ui.googleFilter === 'active' ? 'on' : ''}" data-gfilter="active">Activas</button><button class="${ui.googleFilter === 'all' ? 'on' : ''}" data-gfilter="all">Todas (24 h)</button></div>`;
    const sort = `<select class="select" id="gsort">${[['volume', 'Por volumen'], ['growth', 'Por crecimiento'], ['recent', 'Más recientes']].map(([v, l]) => `<option value="${v}" ${ui.googleSort === v ? 'selected' : ''}>${l}</option>`).join('')}</select>`;
    const html = `${staleNote('google')}
      <div class="card"><div class="card-head"><div><h2>${list.length} tendencias</h2><p>Fuente: Google Trends, España · ${st.mode === 'rss' ? 'modo simplificado (RSS)' : 'Trending Now'} · ${esc(F.ago(st.fetched_at))}</p></div><div class="card-tools">${seg}${sort}</div></div>
        <div class="card-body flush">${list.length ? `<table class="ttable"><thead><tr><th>#</th><th>Tendencia</th><th class="num">Volumen</th><th class="num">Subida</th><th class="num">Inicio</th><th class="hide-sm">Evolución</th><th>Estado</th></tr></thead><tbody>${rows}</tbody></table>` : emptyState('search', 'Nada con estos filtros', '')}</div></div>`;
    return {
      html,
      mount(root) {
        $$('[data-gspark]', root).forEach((el) => {
          const g = items.find((i) => i.id === el.dataset.gspark);
          if (!g) return;
          const fake = { series: g.volume_series, series_kind: 'google_volume', series_end: ui.state.generated_at, series_step: 3600 };
          el.replaceChildren(C.sparkline(g.volume_series || [], { describe: seriesDescriber(fake) }));
        });
      },
    };
  },

  youtube() {
    const items = ui.state.platforms?.youtube || [];
    const intro = `<div class="card"><div class="card-body note">${icon('info')} YouTube eliminó su página de Tendencias en julio de 2025, así que aquí hago algo más útil para ti: para cada tema caliente, busco los vídeos subidos esta semana y mido <b>cuánta competencia hay</b>. Mucha búsqueda y poco vídeo = <b>hueco</b>.</div></div>`;
    if (!items.length) return { html: intro + sourceError('youtube') };
    const cards = items.filter((y) => !ui.search || norm(y.topic || y.topic_title).includes(norm(ui.search))).map((y) => {
      const topic = topicByKey(y.topic_key);
      const videos = (y.videos || []).slice(0, 3).map((v) => `
        <div class="video">
          <span class="thumb wide thumb-box"><img src="${esc(F.safeUrl(v.thumbnail))}" alt="" loading="lazy"></span>
          <div style="min-width:0">${extLink(v.url, esc(v.title), 'v-title')}<div class="v-meta">${esc(v.channel || '')}${v.channel ? ' · ' : ''}${F.num(v.views)} visualizaciones${published(v)}${v.is_short ? ' · Short' : ''}</div></div>
        </div>`).join('');
      return `<div class="card"><div class="card-head"><div><h2 ${topic ? `data-topic="${esc(topic.key)}" style="cursor:pointer"` : ''}>${esc(y.topic || y.topic_title || y.query)}</h2><p>${topic ? `${esc(nicheName(topic.niche))} · calor ${topic.heat}` : ''}</p></div>
        <span class="level level-${esc(y.level)}"><i></i>${esc(LEVEL_TEXT[y.level] || y.label)}</span></div>
        <div class="card-body"><div class="d-stats" style="grid-template-columns:repeat(3,minmax(0,1fr));margin-bottom:12px">
          <div class="d-stat"><span>Vídeos esta semana</span><b>${y.count >= 20 ? '20+' : y.count}</b></div>
          <div class="d-stat"><span>El más visto</span><b>${F.num(y.top_views)}</b></div>
          <div class="d-stat"><span>Mediana</span><b>${F.num(y.median_views)}</b></div></div>
          ${videos || '<div class="small muted">Sin vídeos recientes: terreno libre.</div>'}
          <div class="actions mt-8">${extLink(y.search_url, `${icon('external')}Ver búsqueda en YouTube`, 'btn btn-sm')}</div></div></div>`;
    }).join('');
    return { html: `${intro}${staleNote('youtube')}<div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(420px,1fr))">${cards}</div>` };
  },

  x() {
    let items = ui.state.platforms?.x || [];
    if (!items.length) return { html: sourceError('x') };
    if (ui.search) items = items.filter((t) => norm(t.title).includes(norm(ui.search)));
    const hasVolume = items.some((t) => t.volume);
    const rows = items.map((t) => {
      const topic = topicForSource('x', t.id);
      const change = t.is_new ? '<span class="chip">Nuevo</span>' : t.rank_change > 0 ? `<span class="up">▲ ${t.rank_change}</span>` : t.rank_change < 0 ? `<span class="down">▼ ${Math.abs(t.rank_change)}</span>` : '<span class="muted">=</span>';
      return `<tr tabindex="0" ${topic && (topic.sources.length > 1 || topic.story) ? `data-topic="${esc(topic.key)}"` : `data-ext-url="${esc(t.url)}"`}>
        <td class="rank">${t.rank}</td>
        <td><div class="t-title">${esc(t.title)}</div><div class="t-meta">${nicheChip(t.niche)}${topic ? storyChip(topic) : ''}${topic && topic.sources.length > 1 ? sourceBadges(topic.sources) : ''}</div></td>
        ${hasVolume ? `<td class="num"><div class="num-main">${t.volume ? F.num(t.volume) : '—'}</div><div class="num-sub">posts</div></td>` : ''}
        <td class="num"><div class="num-main">${t.hours_in_trends ? esc(F.hours(t.hours_in_trends)) : '<1 h'}</div><div class="num-sub">en tendencias</div></td>
        <td class="hide-sm"><div data-xspark="${esc(t.id)}"></div></td>
        <td>${change}</td></tr>`;
    }).join('');
    const st = sourceStatus('x');
    return {
      html: `${staleNote('x')}<div class="card"><div class="card-head"><div><h2>Tendencias en X · España</h2><p>Vía ${esc(st.mode || 'trends24')} · ${esc(F.ago(st.fetched_at))} · la curva muestra la posición hora a hora</p></div></div>
        <div class="card-body flush"><table class="ttable"><thead><tr><th>#</th><th>Tendencia</th>${hasVolume ? '<th class="num">Posts</th>' : ''}<th class="num">Tiempo</th><th class="hide-sm">Posición por hora</th><th>Cambio</th></tr></thead><tbody>${rows}</tbody></table></div></div>`,
      mount(root) {
        $$('[data-xspark]', root).forEach((el) => {
          const t = items.find((i) => i.id === el.dataset.xspark);
          if (t) el.replaceChildren(C.sparkline(t.series || [], { describe: seriesDescriber({ series: t.series, series_kind: 'x' }) }));
        });
      },
    };
  },

  wikipedia() {
    const items = ui.state.platforms?.wikipedia || [];
    if (!items.length) return { html: sourceError('wikipedia') };
    const counts = {};
    items.forEach((i) => { counts[i.niche] = (counts[i.niche] || 0) + 1; });
    const chips = [`<button class="fchip ${ui.wikiNiche === 'all' ? 'on' : ''}" data-wiki-niche="all">Todos <span class="n">${items.length}</span></button>`]
      .concat(Object.keys(counts).sort((a, b) => counts[b] - counts[a]).map((n) => `<button class="fchip ${ui.wikiNiche === n ? 'on' : ''}" data-wiki-niche="${esc(n)}">${esc(nicheName(n))} <span class="n">${counts[n]}</span></button>`));
    let list = ui.wikiNiche === 'all' ? items : items.filter((i) => i.niche === ui.wikiNiche);
    if (ui.search) list = list.filter((i) => norm(`${i.title} ${i.description || ''}`).includes(norm(ui.search)));
    const rows = list.map((w) => {
      const change = w.is_new ? '<span class="chip">Nuevo</span>' : w.change_pct !== null && w.change_pct !== undefined ? `<span class="${w.change_pct >= 0 ? 'up' : 'down'}">${F.pct(w.change_pct)}</span>` : '';
      return `<tr tabindex="0" data-ext-url="${esc(w.url)}">
        <td class="rank">${w.rank}</td>
        <td><div class="t-title">${esc(w.title)}</div><div class="t-meta">${nicheChip(w.niche)}<span>${esc(w.description || '')}</span>${w.lang !== 'es' ? `<span class="chip">${esc(w.lang.toUpperCase())}</span>` : ''}</div></td>
        <td class="num"><div class="num-main">${F.num(w.views)}</div><div class="num-sub">lecturas</div></td>
        <td class="num">${change}<div class="num-sub">vs. día anterior</div></td>
        <td class="hide-sm"><div data-wspark="${esc(w.id + w.project)}"></div></td></tr>`;
    }).join('');
    const st = sourceStatus('wikipedia');
    return {
      html: `${staleNote('wikipedia')}<div class="chip-row">${chips.join('')}</div>
        <div class="card"><div class="card-head"><div><h2>Lo más leído desde España</h2><p>Datos de Wikimedia del ${esc(items[0]?.day ? F.longDate(items[0].day) : '')} · ${esc(F.ago(st.fetched_at))}</p></div></div>
        <div class="card-body flush"><table class="ttable"><thead><tr><th>#</th><th>Artículo</th><th class="num">Lecturas</th><th class="num">Cambio</th><th class="hide-sm">Últimos días</th></tr></thead><tbody>${rows}</tbody></table></div></div>`,
      mount(root) {
        $$('[data-wspark]', root).forEach((el) => {
          const w = items.find((i) => i.id + i.project === el.dataset.wspark);
          if (w) el.replaceChildren(C.sparkline(w.series || [], { describe: seriesDescriber({ series: w.series, series_kind: 'wikipedia' }) }));
        });
      },
    };
  },

  noticias() {
    const data = ui.state.platforms?.news || {};
    if (!data.items?.length) return { html: sourceError('news') };
    const reach = (t) => Math.max(t.news?.outlets || 0, ...(t.news?.items || []).map((n) => n.coverage || 0));
    const topics = visibleTopics().filter((t) => reach(t) >= 2 && t.why);
    topics.sort((a, b) => (reach(b) - reach(a)) || (b.heat - a.heat));
    const stories = topics.slice(0, 8).map((t) => `
      <div class="li" data-topic="${esc(t.key)}" tabindex="0">
        <div class="li-main"><div class="li-title wrap">${esc(t.title)}</div><div class="li-sub wrap">${esc(t.why.title)}</div></div>
        <div class="li-side"><span class="chip">${reach(t)} medios</span></div></div>`).join('');
    const inRadar = new Set((ui.state.topics || []).flatMap((t) => (t.news?.items || []).map((n) => n.title)));
    const covered = data.items.filter((n) => !inRadar.has(n.title) && (n.coverage || 1) >= 2)
      .sort((a, b) => (b.coverage || 1) - (a.coverage || 1) || (b.published || 0) - (a.published || 0));
    const filtered = ui.search ? covered.filter((n) => norm(n.title).includes(norm(ui.search))) : covered;
    const top = filtered.slice(0, 10).map((n) => `
      <div class="li" data-ext-url="${esc(n.url)}">
        <div class="li-main"><div class="li-title wrap">${esc(n.title)}</div><div class="li-sub">${esc(n.source || '')} · ${esc(F.ago(n.published))}</div></div>
        <div class="li-side">${n.coverage > 1 ? `<span class="chip">${n.coverage} medios</span>` : ''}</div></div>`).join('');
    const labels = data.labels || {};
    const byId = Object.fromEntries(data.items.map((i) => [i.id, i]));
    const tabs = Object.keys(labels).filter((s) => (data.sections?.[s] || []).length)
      .map((s) => `<button class="tab ${ui.newsSection === s ? 'on' : ''}" data-news="${esc(s)}">${esc(labels[s])}</button>`).join('');
    const section = (data.sections?.[ui.newsSection] || []).map((id) => byId[id]).filter(Boolean)
      .sort((a, b) => (b.coverage || 1) - (a.coverage || 1)).slice(0, 10).map((n) => `
      <div class="li" data-ext-url="${esc(n.url)}">
        <div class="li-main"><div class="li-title wrap">${esc(n.title)}</div><div class="li-sub">${esc(n.source || '')} · ${esc(F.ago(n.published))}</div></div>
        <div class="li-side">${n.coverage > 1 ? `<span class="chip">${n.coverage} medios</span>` : ''}</div></div>`).join('');
    const html = `${staleNote('news')}
      <div class="card"><div class="card-head"><div><h2>Las historias del día</h2><p>Lo que más medios están contando y además es tendencia · pulsa para ver por qué</p></div></div>
        <div class="card-body flush"><div class="list">${stories || emptyState('news', 'Ninguna historia con varios medios todavía', '')}</div></div></div>
      <div class="card mt-16"><div class="card-head"><div><h2>Aún fuera del radar</h2><p>Varios medios lo cuentan, pero todavía no es tendencia en búsquedas ni en X. Vigílalo.</p></div></div>
        <div class="card-body flush"><div class="list">${top || emptyState('news', 'Nada destacable fuera del radar', 'Todo lo que cubren varios medios ya está en el radar.')}</div></div></div>
      <details class="howto mt-16"><summary>${icon('news')}Por secciones</summary><div class="tabs mt-8">${tabs}</div>
        <div class="card"><div class="card-body flush"><div class="list">${section || emptyState('news', 'Sin titulares', '')}</div></div></div></details>`;
    return { html };
  },

  efemerides() {
    const days = ui.state.efemerides?.days || [];
    if (!days.length) return { html: sourceError('efemerides') };
    const filterItem = (i) => (!ui.efemRound || i.round_level >= 1) && (!ui.efemSpain || i.spain) && (!ui.search || norm(`${i.title} ${i.text}`).includes(norm(ui.search)));
    const highlights = (ui.state.efemerides.highlights || []).filter(filterItem);
    const dayBlocks = days.map((d) => {
      const items = d.items.filter(filterItem).slice(0, 6);
      if (!items.length) return '';
      return `<div class="card"><div class="card-head"><div><h2>${esc(F.longDate(d.date))}</h2><p>${esc(F.daysUntil(d.date))}</p></div></div>
        <div class="card-body flush"><div class="list">${items.map((i) => `
          <div class="li" ${i.url ? `data-ext-url="${esc(i.url)}"` : ''}>
            <div class="year-badge ${i.round_level >= 1 ? 'round' : ''}"><b>${esc(i.year)}</b><span>hace ${esc(i.years_ago)}</span></div>
            <div class="li-main"><div class="li-title wrap">${esc(i.text)}</div><div class="li-sub">${esc(i.kind_label)}${i.spain ? ' · España' : ''} · ${esc(nicheName(i.niche))}</div></div></div>`).join('')}</div></div></div>`;
    }).join('');
    const html = `
      <div class="row-gap"><label class="toggle"><input type="checkbox" id="efem-round" ${ui.efemRound ? 'checked' : ''}>Solo aniversarios redondos</label>
        <label class="toggle"><input type="checkbox" id="efem-spain" ${ui.efemSpain ? 'checked' : ''}>Solo relacionados con España</label></div>
      <div class="card"><div class="card-head"><div><h2>Aniversarios destacados · próximos 30 días</h2><p>Números redondos (25, 50, 100, 250 años…) y efemérides españolas: los medios hablarán de ellos</p></div></div>
        <div class="card-body flush"><div class="list">${highlights.length ? highlights.map((e) => efemItem(e)).join('') : emptyState('calendar', 'Sin aniversarios destacados con estos filtros', '')}</div></div></div>
      <div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(420px,1fr))">${dayBlocks}</div>`;
    return { html };
  },

  ajustes() {
    const s = ui.settings || {};
    const statuses = ui.state?.sources || {};
    const rows = ['google', 'google_week', 'youtube', 'x', 'wikipedia', 'news', 'efemerides'].map((id) => {
      const st = statuses[id] || {};
      const cls = st.enabled === false || st.requires_login ? 'off' : st.stale ? 'stale' : st.ok ? 'ok' : st.fetched_at ? 'err' : 'off';
      const text = st.enabled === false ? 'Desactivada' : st.requires_login ? 'Requiere cuenta' : st.stale ? 'Datos antiguos' : st.ok ? 'Funcionando' : st.fetched_at ? 'Con errores' : 'Pendiente';
      return `<tr><td>${esc(st.label || id)}</td><td><span class="status-pill ${cls}"><i></i>${text}</span></td><td class="num">${st.count ?? 0}</td><td>${esc(F.ago(st.fetched_at))}</td><td class="small muted" style="max-width:360px">${esc(st.error || '')}</td></tr>`;
    }).join('');
    const sourceToggles = SOURCE_ORDER.map((id) => `<label class="toggle"><input type="checkbox" data-source-toggle="${id}" ${s.sources?.[id] !== false ? 'checked' : ''}>${esc(SOURCES[id].long)}</label>`).join('');
    const html = `
      <div class="grid cols-12">
        <div class="card span-7"><div class="card-head"><div><h2>Preferencias</h2></div></div>
          <div class="card-body flush"><div class="settings">
            <div class="setting"><div><b>Tu nombre</b><p>Para saludarte en el Radar.</p></div>
              <input class="input" id="set-name" maxlength="40" placeholder="Por ejemplo, David" value="${esc(s.name || '')}"></div>
            <div class="setting"><div><b>Actualizar cada</b><p>Mientras el programa esté abierto. Wikipedia va más despacio porque publica datos diarios.</p></div>
              <select class="select" id="set-refresh">${[10, 15, 30, 60, 120].map((m) => `<option value="${m}" ${s.refresh_minutes === m ? 'selected' : ''}>${m} minutos</option>`).join('')}</select></div>
            <div class="setting"><div><b>Temas analizados en YouTube</b><p>Cuántos de los temas más calientes se comprueban en YouTube en cada actualización.</p></div>
              <select class="select" id="set-youtube">${[0, 4, 8, 12, 16].map((m) => `<option value="${m}" ${s.youtube_topics === m ? 'selected' : ''}>${m === 0 ? 'Ninguno' : `${m} temas`}</option>`).join('')}</select></div>
            <div class="setting"><div><b>Ocultar búsquedas utilitarias</b><p>Loterías, el tiempo, horarios y similares: suben mucho pero no sirven para contenido.</p></div>
              <label class="toggle"><input type="checkbox" id="set-utility" ${s.hide_utility !== false ? 'checked' : ''}></label></div>
            <div class="setting"><div><b>Apariencia</b><p>Automático sigue el modo claro u oscuro de tu Mac.</p></div>
              <select class="select" id="set-theme">${[['system', 'Automático'], ['light', 'Claro'], ['dark', 'Oscuro']].map(([v, l]) => `<option value="${v}" ${s.theme === v ? 'selected' : ''}>${l}</option>`).join('')}</select></div>
            <div class="setting"><div><b>Fuentes activas</b><p>Desactiva las que no quieras consultar.</p></div><div class="row-gap" style="max-width:360px;justify-content:flex-end">${sourceToggles}</div></div>
          </div></div></div>
        <div class="stack span-5">
          <div class="card"><div class="card-head"><div><h2>Tus datos</h2><p>Todo se guarda en tu ordenador; nada se sube a ningún sitio.</p></div></div>
            <div class="card-body"><div class="small muted">Carpeta</div><div class="err-text" style="margin:4px 0 12px">${esc(s.data_dir || '')}</div>
              <button class="btn btn-sm" data-action="clear-history">${icon('database')}Borrar historial</button></div></div>
          <div class="card"><div class="card-head"><div><h2>Acerca de</h2></div></div>
            <div class="card-body note">Romero CRM ${esc(ui.state?.app?.version || '')}. Usa solo fuentes públicas y gratuitas: Google Trends, getdaytrends y trends24 (X), Wikimedia, Google News y búsquedas de YouTube. TikTok no aparece porque ya no publica sus tendencias sin cuenta; en la ficha de cada tema tienes un botón para buscarlo en TikTok. Algunas son webs de terceros que cambian a menudo: si una falla, el resto sigue funcionando y aquí verás el motivo.</div></div>
        </div>
      </div>
      <div class="card"><div class="card-head"><div><h2>Estado de las fuentes</h2><p>Última consulta de cada una. Si algo falla, copia el informe y pégaselo a Claude.</p></div>
        <div class="card-tools"><button class="btn btn-sm" data-action="copy-report">${icon('copy')}Copiar informe</button><button class="btn btn-sm" data-action="refresh">${icon('refresh')}Actualizar ahora</button></div></div>
        <div class="card-body"><table class="dtable"><thead><tr><th>Fuente</th><th>Estado</th><th class="num">Elementos</th><th>Última vez</th><th>Detalle</th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
    return { html };
  },
};

function sourcesReport() {
  const lines = [`Romero CRM ${ui.state?.app?.version || ''} · informe de fuentes · ${new Date().toLocaleString('es-ES')}`,
    `Modo: ${DESKTOP ? 'ventana propia' : 'navegador'} · ${navigator.userAgent}`];
  for (const [id, st] of Object.entries(ui.state?.sources || {})) {
    const state = st.enabled === false ? 'DESACTIVADA' : st.requires_login ? 'REQUIERE CUENTA' : st.ok ? (st.stale ? 'DATOS ANTIGUOS' : 'OK') : 'ERROR';
    lines.push(`- ${id}: ${state} · ${st.count ?? 0} elementos · modo ${st.mode || '—'} · ${F.ago(st.fetched_at)}${st.error ? ` · ${st.error}` : ''}`);
  }
  if (ui.state?.last_error) lines.push(`Error interno: ${ui.state.last_error}`);
  lines.push(`Temas en el radar: ${ui.state?.topics?.length ?? 0}`);
  return lines.join('\n');
}

function isUtilityTitle(item) {
  const topic = topicForSource('google', item.id);
  return topic ? topic.utility : false;
}

function topicForSource(source, id) {
  return (ui.state?.topics || []).find((t) => t[source] && t[source].id === id);
}

/* ---------- Drawer ---------- */

function buildBrief(topic, detail) {
  const lines = [`TEMA: ${topic.title}`, `NICHO: ${nicheName(topic.niche)}`, `FASE: ${topic.phase_label} (calor ${topic.heat}/100, potencial ${topic.potential}/100)`];
  if (topic.what) lines.push(`${topic.what_subject ? `SOBRE ${topic.what_subject.toUpperCase()}` : 'QUÉ ES'}: ${topic.what}`);
  if (topic.why) lines.push(`QUÉ PASA: ${topic.why.title}${topic.why.source ? ` (${topic.why.source})` : ''}`);
  if (topic.remaining_hours) lines.push(`VENTANA ESTIMADA: ~${F.hours(topic.remaining_hours)}`);
  const signals = (topic.signals || []).map((s) => `- ${s.text}`);
  if (signals.length) lines.push('', 'DATOS:', ...signals);
  const news = (detail?.news || topic.news?.items || []).slice(0, 5).map((n) => `- ${n.title}${n.source ? ` (${n.source})` : ''}`);
  if (news.length) lines.push('', 'POR QUÉ ES TENDENCIA (titulares):', ...news);
  if (topic.related?.length) lines.push('', `BÚSQUEDAS RELACIONADAS: ${topic.related.slice(0, 8).join(', ')}`);
  if (topic.story) lines.push('', `FORMA PARTE DE LA HISTORIA: ${topic.story.title}`);
  if (topic.angles?.length) lines.push('', `TAMBIÉN SON TENDENCIA, LIGADOS A ESTA HISTORIA: ${topic.angles.map((a) => a.title).join(', ')}`);
  const yt = detail?.youtube;
  if (yt) lines.push('', yt.count
    ? `COMPETENCIA EN YOUTUBE (última semana): ${yt.count >= 20 ? '20+' : yt.count} vídeos; el más visto, ${F.num(yt.top_views)} visualizaciones (${LEVEL_TEXT[yt.level] || yt.label}).`
    : 'COMPETENCIA EN YOUTUBE (última semana): ningún vídeo sobre el tema (hueco claro).');
  lines.push('', 'Quiero un short narrativo (60-90 s) sobre este tema con mi estilo de guion. Propón 3 ángulos que NO sean los obvios, cada uno con un hook de una frase y una idea de cierre memorable. Distingue hechos verificados de interpretaciones.');
  return lines.join('\n');
}

function drawerHtml(topic, detail, loading) {
  if (!topic.why && detail?.why) topic = { ...topic, why: detail.why };
  const stats = `
    <div class="d-stats">
      <div class="d-stat"><span>Calor</span><b>${topic.heat}</b></div>
      <div class="d-stat"><span>Potencial</span><b>${topic.potential}</b></div>
      <div class="d-stat"><span>${esc(capitalize(topic.metric?.kind || 'volumen'))}</span><b>${metricMain(topic)}</b></div>
      <div class="d-stat"><span>Ventana</span><b>${topic.remaining_hours !== null && topic.remaining_hours !== undefined ? `~${esc(F.hours(topic.remaining_hours))}` : '—'}</b></div>
    </div>`;
  const signals = (topic.signals || []).map((s) => `<li><i style="background:var(--src-${esc(s.source)})"></i><span>${esc(s.text)}</span></li>`).join('');
  const leadTitle = topic.why?.title || '';
  const news = (detail?.news || topic.news?.items || []).filter((n) => !leadTitle || !n.title || !n.title.includes(leadTitle.slice(0, 40)));
  const newsHtml = news.length ? news.slice(0, 8).map((n) => `
    <div class="news-item">${extLink(n.url, esc(n.title))}<span>${esc(n.source || '')}${n.published ? ` · ${esc(F.ago(n.published))}` : ''}</span></div>`).join('')
    : loading ? '<div class="spinner"></div>' : '';
  const yt = detail?.youtube;
  const ytHtml = yt ? `
    <div class="row-gap" style="justify-content:space-between;margin-bottom:10px"><span class="level level-${esc(yt.level)}"><i></i>${esc(LEVEL_TEXT[yt.level] || yt.label)}</span>
      <span class="small muted">${yt.count ? `${yt.count >= 20 ? '20+' : yt.count} vídeos esta semana · máx. ${F.num(yt.top_views)} · mediana ${F.num(yt.median_views)}` : 'Nadie ha subido vídeos sobre esto esta semana'}</span></div>
    ${(yt.videos || []).slice(0, 5).map((v) => `
      <div class="video"><span class="thumb wide thumb-box"><img src="${esc(F.safeUrl(v.thumbnail))}" alt="" loading="lazy"></span>
        <div style="min-width:0">${extLink(v.url, esc(v.title), 'v-title')}<div class="v-meta">${esc(v.channel || '')}${v.channel ? ' · ' : ''}${F.num(v.views)} visualizaciones${published(v)}</div></div></div>`).join('')}`
    : loading ? '<div class="spinner"></div>' : '<div class="small muted">No se pudo consultar YouTube para este tema.</div>';
  const q = encodeURIComponent(topic.query || topic.title);
  const links = [
    [topic.google?.url || `https://trends.google.com/trends/explore?geo=ES&q=${q}`, 'Google Trends'],
    [`https://x.com/search?q=${q}&src=typed_query`, 'X'],
    [`https://www.tiktok.com/search?q=${q}`, 'TikTok'],
    [`https://www.youtube.com/results?search_query=${q}`, 'YouTube'],
    [topic.wikipedia?.url || `https://es.wikipedia.org/w/index.php?search=${q}`, 'Wikipedia'],
  ].map(([url, label]) => extLink(url, `${icon('external')}${esc(label)}`, 'btn btn-sm')).join('');
  const related = (topic.related || []).length ? `<div class="d-section"><h3>Búsquedas relacionadas</h3><div class="related">${topic.related.map((r) => extLink(`https://trends.google.com/trends/explore?geo=ES&q=${encodeURIComponent(r)}`, `<span class="chip">${esc(r)}</span>`)).join('')}</div></div>` : '';
  return `
    <div class="d-head">
      <div class="d-top"><h2 class="d-title">${esc(topic.title)}</h2><button class="btn btn-ghost icon-btn" data-action="close-drawer" aria-label="Cerrar">${icon('close')}</button></div>
      <div class="d-sub">${phaseChip(topic)}${nicheChip(topic.niche)}${sourceBadges(topic.sources)}</div>
    </div>
    <div class="d-body">
      <div class="d-hero">
        ${whyHtml(topic)}
        ${whatHtml(topic)}
        ${topic.summary ? `<p class="explain"><span class="ex-label">En cifras</span><span class="ex-text">${esc(topic.summary)}</span></p>` : ''}
        ${topic.why?.url ? `<div class="actions mt-8">${extLink(topic.why.url, `${icon('external')}Leer la noticia`, 'btn btn-sm')}</div>` : ''}
      </div>
      ${stats}
      <div class="d-section"><h3>Las señales</h3><p class="reason" style="margin:0 0 10px">${esc(topic.phase_reason || '')}</p><ul class="signals">${signals}</ul>
        ${topic.story ? `<p class="small" style="margin:10px 0 0">Forma parte de la historia <button class="link" data-topic="${esc(topic.story.key)}">${esc(topic.story.title)}</button>: aparece en sus búsquedas relacionadas o en los mismos titulares.</p>` : ''}</div>
      ${(topic.angles || []).length ? `<div class="d-section"><h3>Ángulos que también son tendencia</h3><p class="small muted" style="margin:0 0 8px">Temas sueltos de X o Wikipedia ligados a esta historia. Cada uno puede ser un enfoque distinto para tu vídeo.</p><div class="related">${topic.angles.map((a) => `<button class="chip" data-topic="${esc(a.key)}">${esc(a.title)}</button>`).join('')}</div></div>` : ''}
      <div class="d-section"><h3>${esc(topic.series_label || 'Evolución')}</h3><div id="d-chart"></div></div>
      ${newsHtml ? `<div class="d-section"><h3>${leadTitle ? 'Más titulares' : 'Titulares'}</h3>${newsHtml}</div>` : ''}
      <div class="d-section"><h3>Competencia en YouTube</h3>${ytHtml}</div>
      ${related}
      <div class="d-section"><h3>Llévalo a guion</h3><div class="brief" id="brief">${esc(buildBrief(topic, detail))}</div>
        <div class="actions mt-8"><button class="btn btn-primary btn-sm" data-action="copy-brief">${icon('copy')}Copiar brief para Claude</button></div></div>
      <div class="d-section"><h3>Abrir en</h3><div class="actions">${links}</div></div>
    </div>`;
}

function mountDrawerChart(topic) {
  const el = $('#d-chart');
  if (!el) return;
  const describe = seriesDescriber(topic);
  const n = (topic.series || []).length;
  const xLabel = (i) => {
    const back = n - 1 - i;
    if (topic.series_kind === 'google_volume') return back === 0 ? 'ahora' : F.clock((topic.series_end || Date.now() / 1000) - back * (topic.series_step || 3600));
    if (topic.series_kind === 'x') return back === 0 ? 'ahora' : `-${back} h`;
    return back === 0 ? 'último' : `-${back} d`;
  };
  const isX = topic.series_kind === 'x';
  C.lineChart(el, topic.series || [], { describe, xLabel, height: 180, ticks: isX ? [1, 26, 50] : null, yFormat: (v) => (isX ? (v > 0 ? `${Math.round(51 - v)}º` : '') : F.num(v)) });
}

async function openDrawer(key) {
  const topic = topicByKey(key);
  if (!topic) return;
  ui.drawerKey = key;
  const drawer = $('#drawer');
  drawer.innerHTML = drawerHtml(topic, null, true);
  hydrateIcons(drawer);
  $('#scrim').hidden = false;
  drawer.classList.add('open');
  drawer.setAttribute('aria-hidden', 'false');
  drawer.scrollTop = 0;
  drawer.focus();
  requestAnimationFrame(() => mountDrawerChart(topic));
  try {
    const detail = await api(`/api/topic?key=${encodeURIComponent(key)}`);
    if (ui.drawerKey !== key) return;
    drawer.innerHTML = drawerHtml(topic, detail.error ? null : detail, false);
    hydrateIcons(drawer);
    mountDrawerChart(topic);
  } catch (err) {
    if (ui.drawerKey === key) {
      drawer.innerHTML = drawerHtml(topic, null, false);
      mountDrawerChart(topic);
    }
  }
}

function closeDrawer() {
  ui.drawerKey = null;
  const drawer = $('#drawer');
  drawer.classList.remove('open');
  drawer.setAttribute('aria-hidden', 'true');
  $('#scrim').hidden = true;
  C.hideTip();
}

/* ---------- Events ---------- */

async function saveSettings(patch) {
  try {
    ui.settings = await post('/api/settings', patch);
    applyTheme();
  } catch (err) {
    toast('No se pudo guardar el ajuste');
  }
}

function applyTheme() {
  const theme = ui.settings?.theme || 'system';
  if (theme === 'system') document.documentElement.removeAttribute('data-theme');
  else document.documentElement.setAttribute('data-theme', theme);
}

async function refreshNow() {
  try {
    await post('/api/refresh');
    if (ui.state) ui.state.refreshing = true;
    updateRefreshButton(true);
    startPolling();
  } catch {
    toast('No se pudo iniciar la actualización');
  }
}

document.addEventListener('click', async (event) => {
  const target = event.target;
  const ext = target.closest('a[data-ext]');
  if (ext) {
    event.preventDefault();
    openExternal(ext.getAttribute('href'));
    return;
  }
  const action = target.closest('[data-action]')?.dataset.action;
  if (action === 'refresh') return refreshNow();
  if (action === 'close-drawer') return closeDrawer();
  if (action === 'show-all') { ui.showAll = true; return renderView(); }
  if (action === 'copy-brief') return copyText($('#brief')?.textContent || '');
  if (action === 'copy-report') return copyText(sourcesReport());
  if (action === 'clear-history') {
    if (confirm('¿Borrar todo el historial guardado? Las tendencias actuales se volverán a descargar.')) {
      await post('/api/clear-history');
      ui.history = null;
      toast('Historial borrado');
      startPolling();
    }
    return;
  }
  const topicEl = target.closest('[data-topic]');
  if (topicEl && !target.closest('a')) return openDrawer(topicEl.dataset.topic);
  const extRow = target.closest('[data-ext-url]');
  if (extRow) return openExternal(extRow.dataset.extUrl);
  const nicheBtn = target.closest('[data-niche]');
  if (nicheBtn) { ui.niche = nicheBtn.dataset.niche; ui.showAll = false; return render(); }
  const goNiche = target.closest('[data-go-niche]');
  if (goNiche) { ui.niche = goNiche.dataset.goNiche; location.hash = '#/radar'; return; }
  const sortBtn = target.closest('[data-sort]');
  if (sortBtn) { ui.sort = sortBtn.dataset.sort; return renderView(); }
  const metricBtn = target.closest('[data-niche-metric]');
  if (metricBtn) { ui.nicheMetric = metricBtn.dataset.nicheMetric; return renderView(); }
  const gfilter = target.closest('[data-gfilter]');
  if (gfilter) { ui.googleFilter = gfilter.dataset.gfilter; return renderView(); }
  const newsBtn = target.closest('[data-news]');
  if (newsBtn) { ui.newsSection = newsBtn.dataset.news; return renderView(); }
  const wikiBtn = target.closest('[data-wiki-niche]');
  if (wikiBtn) { ui.wikiNiche = wikiBtn.dataset.wikiNiche; return renderView(); }
  const dayBtn = target.closest('[data-history-day]');
  if (dayBtn) { ui.historyDay = dayBtn.dataset.historyDay; return renderView(); }
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && ui.drawerKey) closeDrawer();
  if (event.key === 'Enter' && event.target.matches('[data-topic], [data-ext-url]')) event.target.click();
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault();
    $('#search').focus();
  }
});

document.addEventListener('change', (event) => {
  const t = event.target;
  if (t.id === 'set-utility') { saveSettings({ hide_utility: t.checked }).then(render); return; }
  if (t.id === 'set-name') return saveSettings({ name: t.value });
  if (t.id === 'gsort') { ui.googleSort = t.value; return renderView(); }
  if (t.id === 'efem-round') { ui.efemRound = t.checked; return renderView(); }
  if (t.id === 'efem-spain') { ui.efemSpain = t.checked; return renderView(); }
  if (t.id === 'set-refresh') return saveSettings({ refresh_minutes: Number(t.value) });
  if (t.id === 'set-youtube') return saveSettings({ youtube_topics: Number(t.value) });
  if (t.id === 'set-theme') return saveSettings({ theme: t.value }).then(renderHeader).then(() => hydrateIcons());
  if (t.dataset.sourceToggle) {
    const sources = { ...(ui.settings?.sources || {}), [t.dataset.sourceToggle]: t.checked };
    return saveSettings({ sources }).then(() => { startPolling(); });
  }
});

let searchTimer = null;
$('#search').addEventListener('input', (event) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { ui.search = event.target.value.trim(); ui.showAll = false; renderNav(); renderView(); }, 140);
});

$('#refresh').addEventListener('click', refreshNow);
$('#scrim').addEventListener('click', closeDrawer);
$('#theme-toggle').addEventListener('click', async () => {
  const order = ['system', 'light', 'dark'];
  const next = order[(order.indexOf(ui.settings?.theme || 'system') + 1) % 3];
  await saveSettings({ theme: next });
  renderHeader();
  hydrateIcons();
  if (ui.route === 'ajustes') renderView();
});
$('.main').addEventListener('scroll', (event) => {
  event.currentTarget.classList.toggle('scrolled', event.currentTarget.scrollTop > 4);
});
window.addEventListener('hashchange', () => {
  ui.route = (location.hash.replace('#/', '') || 'radar');
  ui.showAll = false;
  closeDrawer();
  render();
  $('.main').scrollTop = 0;
});
let resizeTimer = null;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    renderView();
    const topic = ui.drawerKey && topicByKey(ui.drawerKey);
    if (topic) mountDrawerChart(topic);
  }, 200);
});

document.addEventListener('error', (event) => {
  if (event.target instanceof HTMLImageElement) event.target.classList.add('broken');
}, true);

/* ---------- Boot ---------- */

async function boot() {
  C.setupTooltip($('#tooltip'));
  hydrateIcons();
  ui.route = location.hash.replace('#/', '') || 'radar';
  try {
    ui.settings = await api('/api/settings');
    applyTheme();
    await loadState();
  } catch (err) {
    console.error(err);
  }
  render();
  if (ui.state?.refreshing || !ui.state?.generated_at) startPolling();
  setInterval(backgroundCheck, 60000);
  setInterval(() => { if (!ui.polling) renderSidebarFoot(); }, 30000);
}

boot();
