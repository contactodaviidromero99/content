// Búsqueda rápida (⌘K o la lupa): encuentra cualquier historia, tema o sección al instante.
import { icon } from './icons.js';
import * as F from './format.js';
import { $, esc, norm, stories, storyText, ui } from './core.js';
import * as U from './ui.js';

let results = [];
let active = 0;

const GOTO = [
  { label: 'Hoy', sub: 'La portada', icon: 'home', run: () => { location.hash = '#/hoy'; } },
  { label: 'Noticias', sub: 'Todas las historias por nichos', icon: 'news', run: () => { location.hash = '#/noticias'; } },
  { label: 'Calendario', sub: 'Tus tareas, publicados y aniversarios', icon: 'calendar', run: () => { location.hash = '#/calendario'; } },
  { label: 'Historial', sub: 'La semana en un vistazo', icon: 'history', run: () => { location.hash = '#/historial'; } },
  { label: 'Ajustes', sub: 'Nombre, fuentes y conexiones', icon: 'settings', run: () => { location.hash = '#/ajustes'; } },
  { label: 'Nueva tarea', sub: 'Apuntar algo en el calendario', icon: 'plus', action: 'plan-new' },
  { label: 'Actualizar ahora', sub: 'Volver a consultar todas las fuentes', icon: 'refresh', action: 'refresh' },
];

function search(query) {
  const q = norm(query.trim());
  const out = [];
  const list = q ? stories().filter((s) => storyText(s).includes(q)) : stories().slice(0, 6);
  for (const story of list.slice(0, 8)) {
    out.push({ group: q ? 'Historias' : 'Lo más importante ahora', label: story.title, sub: U.whyLine(story), niche: story.niche, key: story.key });
  }
  if (q) {
    const known = new Set(out.map((r) => r.key));
    const topics = (ui.state?.topics || []).filter((t) => !t.utility && !known.has(t.key) && norm(`${t.title} ${(t.related || []).join(' ')}`).includes(q));
    for (const topic of topics.slice(0, 5)) {
      out.push({ group: 'Temas', label: topic.title, sub: topic.why?.title || topic.phase_reason || '', niche: topic.niche, topic: topic.key });
    }
  }
  const actions = GOTO.filter((g) => !q || norm(`${g.label} ${g.sub}`).includes(q));
  for (const item of actions) out.push({ group: 'Ir a', ...item });
  return out;
}

function render() {
  const box = $('#pal-results');
  if (!box) return;
  let group = null;
  box.innerHTML = results.length ? results.map((r, i) => {
    const head = r.group !== group ? `<div class="pal-group">${esc(r.group)}</div>` : '';
    group = r.group;
    const lead = r.icon ? `<span class="kind-ico" style="--k:var(--violet)">${icon(r.icon)}</span>` : `<span class="kind-ico" style="--k:${r.niche ? `var(--violet)` : 'var(--muted)'}">${icon('news')}</span>`;
    return `${head}<div class="pal-item${i === active ? ' active' : ''}" data-index="${i}">${lead}
      <div class="pi-main"><div class="pi-title">${esc(r.label)}</div>${r.sub ? `<div class="pi-sub">${esc(r.sub)}</div>` : ''}</div>
      ${i === active ? `<kbd>↵</kbd>` : ''}</div>`;
  }).join('') : '<div class="empty-line" style="padding:18px">Nada con ese nombre. Prueba con otra palabra.</div>';
  box.querySelector('.pal-item.active')?.scrollIntoView({ block: 'nearest' });
}

async function choose(index) {
  const item = results[index];
  if (!item) return;
  closePalette();
  if (item.run) return item.run();
  const { actions } = await import('./core.js');
  if (item.action) return actions[item.action]?.(document.body);
  const { openStory } = await import('./sheet.js');
  if (item.key) return openStory(item.key);
  if (item.topic) return openStory(item.topic);
}

export function openPalette() {
  const layer = $('#palette');
  layer.innerHTML = `<div class="palette" role="dialog" aria-modal="true" aria-label="Buscar">
    <div class="pal-input">${icon('search')}<input id="pal-input" type="search" placeholder="Busca una historia, un tema o una sección…" autocomplete="off" spellcheck="false"><kbd>esc</kbd></div>
    <div class="pal-results" id="pal-results"></div>
    <div class="pal-foot"><span><kbd>↑</kbd> <kbd>↓</kbd> moverse</span><span><kbd>↵</kbd> abrir</span><span>${esc(F.num(stories().length))} historias en el radar</span></div></div>`;
  layer.hidden = false;
  const input = $('#pal-input');
  results = search('');
  active = 0;
  render();
  input.focus();
  input.addEventListener('input', () => {
    results = search(input.value);
    active = 0;
    render();
  });
  input.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowDown') { active = Math.min(results.length - 1, active + 1); render(); event.preventDefault(); }
    if (event.key === 'ArrowUp') { active = Math.max(0, active - 1); render(); event.preventDefault(); }
    if (event.key === 'Enter') { choose(active); event.preventDefault(); }
  });
  $('#pal-results').addEventListener('click', (event) => {
    const item = event.target.closest('.pal-item');
    if (item) choose(Number(item.dataset.index));
  });
  $('#pal-results').addEventListener('pointermove', (event) => {
    const item = event.target.closest('.pal-item');
    if (item && Number(item.dataset.index) !== active) {
      active = Number(item.dataset.index);
      render();
    }
  });
  layer.onclick = (event) => { if (event.target === layer) closePalette(); };
}

export function closePalette() {
  const layer = $('#palette');
  layer.hidden = true;
  layer.innerHTML = '';
}

export function paletteOpen() {
  return !$('#palette').hidden;
}
