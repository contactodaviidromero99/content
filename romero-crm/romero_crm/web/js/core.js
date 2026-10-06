// Estado compartido, llamadas al servidor y utilidades que usan todas las pantallas.
import * as F from './format.js';

export const TOKEN = document.querySelector('meta[name="romero-token"]')?.content || '';
export const DESKTOP = new URLSearchParams(location.search).get('shell') === 'desktop';
export const { esc } = F;

export const ui = {
  state: null,
  settings: null,
  route: 'hoy',
  search: '',
  niche: 'all',
  scope: 'all',
  sort: 'score',
  newsTab: 'tendencia',
  mediaSection: 'portada',
  picks: [],
  month: F.todayIso().slice(0, 7),
  calendar: {},
  calLayers: { tareas: true, publicados: true, aniversarios: true, festividades: true },
  calRound: false,
  calSpain: false,
  selectedDay: null,
  recapWeek: 0,
  recap: {},
  sheet: null,
  lastRevision: null,
};

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

/* ---------- Acciones: cada pantalla registra las suyas ---------- */

export const actions = {};
export function on(name, handler) {
  actions[name] = handler;
}

let renderHook = () => {};
export function setRenderHook(fn) {
  renderHook = fn;
}
export function rerender(opts) {
  renderHook(opts);
}

/* ---------- Servidor ---------- */

export async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', 'X-Romero-Token': TOKEN, ...(options.headers || {}) },
  });
  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }
  if (!response.ok) {
    const error = new Error(data?.error || `HTTP ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return data;
}

export const post = (path, body = {}) => api(path, { method: 'POST', body: JSON.stringify(body) });

/* ---------- Datos ---------- */

export const NICHE_COLORS = {
  actualidad: '#ff8a65', politica: '#9aa5ff', internacional: '#6cbcff', economia: '#62dcab', deportes: '#7fd88f',
  entretenimiento: '#ff8fb8', musica: '#e08bff', historia: '#e8c27a', tecnologia: '#5fd6d6', ciencia: '#9fd0ff',
  videojuegos: '#b892ff', salud: '#ff9e9e', clima: '#7fc8f8', motor: '#f2a65a', estilo: '#f7a8d8',
  gastronomia: '#f6c177', viajes: '#80d0c7', educacion: '#c3b1e1', animales: '#b5d99c', ocio: '#f4d06f', otros: '#9a98ac',
};

export function nicheName(id) {
  return ui.state?.niches?.find((n) => n.id === id)?.name || id || '—';
}

export function nicheColor(id) {
  return NICHE_COLORS[id] || NICHE_COLORS.otros;
}

export function stories() {
  return ui.state?.stories || [];
}

export function storyByKey(key) {
  return stories().find((s) => s.key === key) || null;
}

export function storyForTopic(topicKey) {
  return stories().find((s) => s.key === topicKey || (s.topic_keys || []).includes(topicKey)) || null;
}

export function topicByKey(key) {
  return (ui.state?.topics || []).find((t) => t.key === key) || null;
}

export function norm(text) {
  return String(text || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

export function storyText(story) {
  return norm([story.title, ...(story.members || []).map((m) => m.title), story.why?.title || '', ...(story.related || []),
    story.context?.text || ''].join(' '));
}

/* ---------- Interfaz ---------- */

export function toast(message) {
  const el = $('#toast');
  el.textContent = message;
  el.hidden = false;
  el.style.animation = 'none';
  void el.offsetWidth;
  el.style.animation = '';
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { el.hidden = true; }, 2400);
}

export async function copyText(text, message = 'Copiado al portapapeles') {
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
  toast(message);
}

export function openExternal(url) {
  const safe = F.safeUrl(url);
  if (!safe) return;
  if (DESKTOP) post('/api/open', { url: safe }).catch(() => window.open(safe, '_blank', 'noopener'));
  else window.open(safe, '_blank', 'noopener');
}

export function greeting() {
  const hour = new Date().getHours();
  const hello = hour < 6 ? 'Buenas noches' : hour < 14 ? 'Buenos días' : hour < 21 ? 'Buenas tardes' : 'Buenas noches';
  const name = (ui.settings?.name || '').trim();
  return { hello, name };
}

export async function loadCalendar(month, force = false) {
  if (!force && ui.calendar[month] && Date.now() - ui.calendar[month]._at < 60000) return ui.calendar[month];
  const data = await api(`/api/calendar?month=${encodeURIComponent(month)}`);
  data._at = Date.now();
  ui.calendar[month] = data;
  return data;
}

export function invalidateCalendar() {
  ui.calendar = {};
  ui.recap = {};
}

export async function refreshAgenda() {
  try {
    const data = await api('/api/agenda');
    if (ui.state) Object.assign(ui.state, data);
  } catch (err) {
    console.error(err);
  }
}
