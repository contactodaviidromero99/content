// Ventanas: el editor de tareas del calendario y la comparativa de historias.
import { icon } from './icons.js';
import * as F from './format.js';
import * as C from './charts.js';
import { $, $$, esc, invalidateCalendar, nicheName, on, post, refreshAgenda, rerender, storyByKey, toast, ui } from './core.js';
import * as U from './ui.js';

const layer = () => $('#modal');
let draft = null;

export function openModal(html, wide = false) {
  const el = layer();
  el.innerHTML = `<div class="modal${wide ? ' wide' : ''}" role="dialog" aria-modal="true">${html}</div>`;
  el.hidden = false;
  const first = el.querySelector('input:not([type=hidden]), button');
  setTimeout(() => first?.focus(), 30);
}

export function closeModal() {
  layer().hidden = true;
  layer().innerHTML = '';
  draft = null;
}

export function modalOpen() {
  return !layer().hidden;
}

/* ---------- Editor de tareas ---------- */

function linksHtml() {
  if (!draft.links.length) return '<div class="muted small">Cuando lo publiques, pega aquí sus enlaces: se rellenan el título y las visualizaciones.</div>';
  return draft.links.map((link, i) => `<div class="link-item">${U.platformIcons([link.platform].filter(Boolean)) || icon('link')}
      <span class="li-title">${esc(link.title || link.url)}</span>${link.views !== null && link.views !== undefined ? `<span class="muted">${F.num(link.views)} visualizaciones</span>` : ''}
      <button type="button" class="icon-btn" style="width:28px;height:28px" data-action="plan-remove-link" data-index="${i}" aria-label="Quitar enlace">${icon('close')}</button></div>`).join('');
}

function planHtml() {
  const kinds = Object.entries(U.KIND).map(([id, info]) => `<button type="button" class="k-${id}${draft.kind === id ? ' on' : ''}" data-action="plan-kind" data-kind="${id}">${icon(info.icon)}${esc(info.label)}</button>`).join('');
  const platforms = Object.entries(U.PLATFORMS).map(([id, info]) => `<button type="button" class="chip${draft.platforms.includes(id) ? ' on' : ''}" data-action="plan-platform" data-platform="${id}">${icon(info.icon)}${esc(info.label)}</button>`).join('');
  return `<div class="modal-head"><div><div class="eyebrow">${draft.id ? 'Editar tarea' : 'Nueva tarea'}</div><h2>${draft.id ? esc(draft.title) : 'Qué vas a hacer'}</h2></div>
      <button class="icon-btn" data-action="close-modal" aria-label="Cerrar">${icon('close')}</button></div>
    <form class="modal-body" id="plan-form" autocomplete="off">
      <label class="field"><span>Título</span><input class="input" name="title" maxlength="140" required placeholder="Por ejemplo: Ruiz-Mateos" value="${esc(draft.title)}"></label>
      <div class="field"><span>Tipo</span><div class="kind-picker">${kinds}</div></div>
      <div class="field-row"><label class="field"><span>Día</span><input class="input" type="date" name="day" required value="${esc(draft.day)}"></label>
        <label class="field"><span>Hora (opcional)</span><input class="input" type="time" name="time" value="${esc(draft.time || '')}"></label></div>
      <div class="field"><span>Dónde</span><div class="chip-row">${platforms}</div></div>
      <label class="field"><span>Notas</span><textarea class="textarea" name="notes" maxlength="2000" placeholder="Idea, fuentes, guion…">${esc(draft.notes || '')}</textarea></label>
      <div class="field"><span>Enlaces del vídeo publicado</span><div class="link-list" id="plan-links">${linksHtml()}</div>
        <div style="display:flex;gap:8px"><input class="input" id="plan-link" style="flex:1" placeholder="https://www.tiktok.com/@…/video/…"><button type="button" class="btn sm" data-action="plan-add-link">${icon('link')}Añadir</button></div></div>
      <label class="switch"><input type="checkbox" name="done" ${draft.done ? 'checked' : ''}><span class="track"></span>Hecho</label>
      ${draft.topic_title ? `<div class="muted small">${icon('link')} Ligada a la historia «${esc(draft.topic_title)}»</div>` : ''}
    </form>
    <div class="modal-foot">${draft.id ? `<button class="btn sm danger" data-action="plan-delete">${icon('trash')}Borrar</button>` : '<span></span>'}
      <div class="chip-row"><button class="btn ghost" data-action="close-modal">Cancelar</button><button class="btn primary" data-action="plan-save">${icon('check')}Guardar</button></div></div>`;
}

export function openPlan(prefill = {}) {
  draft = {
    id: null, day: F.todayIso(), time: '', kind: 'publicar', title: '', notes: '', platforms: [], links: [], done: false,
    topic_key: null, topic_title: null, ...prefill,
  };
  draft.platforms = [...(draft.platforms || [])];
  draft.links = [...(draft.links || [])];
  openModal(planHtml());
}

function readForm() {
  const form = $('#plan-form');
  if (!form || !draft) return;
  draft.title = form.title.value.trim();
  draft.day = form.day.value;
  draft.time = form.time.value;
  draft.notes = form.notes.value;
  draft.done = form.done.checked;
}

export async function afterPlanChange() {
  invalidateCalendar();
  await refreshAgenda();
  rerender({ keepScroll: true });
  if (ui.sheet?.kind === 'day') {
    const { openDay } = await import('./sheet.js');
    openDay(ui.sheet.day);
  }
}

async function savePlan() {
  readForm();
  if (!draft.title) return toast('Ponle un título');
  if (!draft.day) return toast('Elige el día');
  const body = {
    day: draft.day, time: draft.time || null, kind: draft.kind, title: draft.title, notes: draft.notes,
    platforms: draft.platforms, links: draft.links, done: draft.done, topic_key: draft.topic_key, topic_title: draft.topic_title,
  };
  if (draft.id) body.id = draft.id;
  try {
    await post('/api/plan', body);
  } catch (err) {
    return toast(err.message || 'No se pudo guardar');
  }
  const created = !draft.id;
  closeModal();
  toast(created ? `Apuntado para ${F.relDay(body.day)}` : 'Tarea guardada');
  await afterPlanChange();
}

export async function toggleTask(id) {
  const button = document.querySelector(`.tick[data-id="${CSS.escape(id)}"]`);
  const done = !(button?.classList.contains('on'));
  document.querySelectorAll(`.tick[data-id="${CSS.escape(id)}"]`).forEach((b) => {
    b.classList.toggle('on', done);
    b.closest('.task')?.classList.toggle('done', done);
  });
  try {
    await post('/api/plan', { id, done });
  } catch {
    toast('No se pudo guardar');
  }
  if (done) toast('Hecho');
  await afterPlanChange();
}

on('plan-new', (el) => openPlan({ day: el.dataset.day || ui.selectedDay || F.todayIso() }));
on('plan-story', (el) => {
  const story = storyByKey(el.dataset.key);
  if (!story) return;
  const notes = [story.synopsis?.[0]?.text, story.angle?.verdict].filter(Boolean).join('\n');
  openPlan({ title: story.title, kind: 'publicar', notes, topic_key: story.key, topic_title: story.title, platforms: ['instagram', 'tiktok', 'youtube'] });
});
on('plan-idea', (el) => openPlan({ day: el.dataset.day, title: el.dataset.title, notes: el.dataset.notes || '', kind: 'publicar', platforms: ['instagram', 'tiktok', 'youtube'] }));
on('plan-edit', async (el) => {
  const id = el.dataset.id;
  const item = findItem(id);
  if (item) openPlan({ ...item });
});
on('tick', (el) => toggleTask(el.dataset.id));
on('plan-kind', (el) => {
  readForm();
  draft.kind = el.dataset.kind;
  $$('.kind-picker button').forEach((b) => b.classList.toggle('on', b.dataset.kind === draft.kind));
});
on('plan-platform', (el) => {
  const id = el.dataset.platform;
  draft.platforms = draft.platforms.includes(id) ? draft.platforms.filter((p) => p !== id) : [...draft.platforms, id];
  el.classList.toggle('on', draft.platforms.includes(id));
});
on('plan-add-link', async () => {
  const input = $('#plan-link');
  const url = input?.value.trim();
  if (!url) return;
  if (!/^https?:\/\//i.test(url)) return toast('Pega un enlace que empiece por https://');
  input.disabled = true;
  let info = { url };
  try {
    info = await post('/api/link-preview', { url });
  } catch (err) {
    toast(err.message || 'No se pudo leer el enlace; lo guardo igualmente');
  }
  if (!draft) return;
  draft.links.push({ url, platform: info.platform || null, title: info.title || null, thumbnail: info.thumbnail || null, views: info.views ?? null });
  if (info.platform && !draft.platforms.includes(info.platform)) {
    draft.platforms.push(info.platform);
    $$('[data-action="plan-platform"]').forEach((b) => b.classList.toggle('on', draft.platforms.includes(b.dataset.platform)));
  }
  input.value = '';
  input.disabled = false;
  $('#plan-links').innerHTML = linksHtml();
});
on('plan-remove-link', (el) => {
  draft.links.splice(Number(el.dataset.index), 1);
  $('#plan-links').innerHTML = linksHtml();
});
on('plan-save', () => savePlan());
on('plan-delete', async () => {
  if (!draft?.id || !confirm('¿Borrar esta tarea?')) return;
  await post('/api/plan/delete', { id: draft.id });
  closeModal();
  toast('Tarea borrada');
  await afterPlanChange();
});
on('close-modal', () => closeModal());

function findItem(id) {
  const agenda = ui.state?.agenda || {};
  const fromAgenda = [...(agenda.today || []), ...(agenda.tomorrow || []), ...(agenda.overdue || []), ...(agenda.next || [])].find((i) => i.id === id);
  if (fromAgenda) return fromAgenda;
  for (const month of Object.values(ui.calendar)) {
    for (const day of month.days || []) {
      const item = day.items.find((i) => i.id === id);
      if (item) return item;
    }
  }
  return null;
}

/* ---------- Comparativa ---------- */

const PHASE_RANK = { explosivo: 4, subiendo: 3, temprana: 2, pico: 1, enfriandose: 0 };
const YT_RANK = { hueco: 2, moderado: 1, saturado: 0 };
const COLORS = ['#a08fff', '#62dcab', '#ffb84d', '#6cbcff'];

function bet(story) {
  const yt = { hueco: 12, moderado: 4, saturado: -8 }[story.youtube?.level] || 0;
  const marginBonus = Math.min(story.remaining_hours || 0, 12);
  return story.potential + yt + marginBonus + (story.scope === 'espana' ? 4 : 0);
}

function strengths(story) {
  const out = [];
  if (story.youtube?.level === 'hueco') out.push('hay hueco en YouTube');
  if ((story.remaining_hours || 0) >= 6) out.push(`le quedan ~${F.hours(story.remaining_hours)} de margen`);
  if (['explosivo', 'subiendo'].includes(story.phase)) out.push(story.phase === 'explosivo' ? 'está explotando' : 'sigue subiendo');
  if (story.volume >= 100000) out.push(`${F.num(story.volume)}+ búsquedas`);
  if (story.scope === 'espana') out.push('es de España');
  return out.slice(0, 3);
}

function compareHtml(list) {
  const best = (values, higher = true) => {
    const valid = values.filter((v) => v !== null && v !== undefined);
    if (!valid.length) return () => false;
    const target = higher ? Math.max(...valid) : Math.min(...valid);
    return (v) => v === target && valid.filter((x) => x === target).length < values.length;
  };
  const rows = [
    ['Potencial', (s) => s.potential, true, (s) => `<b>${s.potential}</b>`],
    ['Calor ahora', (s) => s.heat, true, (s) => U.heatbar(s.heat)],
    ['Fase', (s) => PHASE_RANK[s.phase], true, (s) => U.phase(s)],
    ['Margen', (s) => s.remaining_hours, true, (s) => `<b>${U.margin(s)}</b>`],
    ['Búsquedas', (s) => s.volume || null, true, (s) => `<b>${s.volume ? `${F.num(s.volume)}+` : '—'}</b>`],
    ['En X', (s) => s.x_rank, false, (s) => `<b>${s.x_rank ? `nº ${s.x_rank}` : '—'}</b>`],
    ['Medios', (s) => s.outlets || null, true, (s) => `<b>${s.outlets || '—'}</b>`],
    ['YouTube', (s) => YT_RANK[s.youtube?.level], true, (s) => `${U.ytLevel(s.youtube, true)}${s.youtube?.count ? `<div class="muted small">${s.youtube.count >= 20 ? '20+' : s.youtube.count} vídeos · máx. ${F.num(s.youtube.top_views)}</div>` : ''}`],
    ['Ámbito', () => null, true, (s) => (s.scope === 'mundo' ? 'Mundo' : 'España')],
    ['Qué ha pasado', () => null, true, (s) => `<span class="small">${esc(U.whyLine(s))}</span>`],
    ['Enfoque', () => null, true, (s) => `<span class="small">${esc(s.angle?.verdict || '')}</span>`],
  ];
  const body = rows.map(([label, value, higher, cell]) => {
    const isBest = best(list.map(value), higher);
    return `<tr><th>${label}</th>${list.map((s) => `<td class="${isBest(value(s)) ? 'best' : ''}">${cell(s)}</td>`).join('')}</tr>`;
  }).join('');
  const ranked = [...list].sort((a, b) => bet(b) - bet(a));
  const winner = ranked[0];
  const hottest = [...list].sort((a, b) => b.heat - a.heat)[0];
  const reasons = strengths(winner);
  const head = list.map((s, i) => `<th><div style="display:flex;justify-content:space-between;gap:8px;align-items:flex-start"><div><span class="dot" style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${COLORS[i]};margin-right:6px"></span>${U.nicheTag(s.niche)}<div class="c-title" style="margin-top:6px">${esc(s.title)}</div></div>
    <button class="icon-btn" style="width:28px;height:28px" data-action="pick" data-key="${esc(s.key)}" aria-label="Quitar">${icon('close')}</button></div></th>`).join('');
  return `<div class="modal-head"><div><div class="eyebrow">Comparativa</div><h2>¿Cuál funcionará mejor?</h2></div>
      <button class="icon-btn" data-action="close-modal" aria-label="Cerrar">${icon('close')}</button></div>
    <div class="modal-body">
      <div class="verdict-box">${icon('sparkles')}<div><b>Mejor apuesta ahora: ${esc(winner.title)}</b>
        <p>${reasons.length ? `Porque ${esc(reasons.join(', '))}.` : 'Es la que combina más potencial y margen.'}${hottest.key !== winner.key ? ` La que más se mueve ahora mismo es <b>${esc(hottest.title)}</b> (calor ${hottest.heat}), pero tiene menos recorrido o más competencia.` : ''}</p></div></div>
      <div style="overflow-x:auto"><table class="compare"><thead><tr><th></th>${head}</tr></thead><tbody>${body}</tbody></table></div>
      <div><div class="block-label">Evolución comparada (cada curva, sobre su propio máximo)</div><div class="chart-box" id="compare-chart"></div></div>
    </div>`;
}

export function openCompare() {
  const list = ui.picks.map(storyByKey).filter(Boolean);
  if (list.length < 2) return toast('Elige al menos dos historias para comparar');
  openModal(compareHtml(list), true);
  requestAnimationFrame(() => {
    const el = $('#compare-chart');
    if (!el) return;
    C.multiLine(el, list.map((s, i) => ({ values: s.series || [], color: COLORS[i], label: s.title })), { height: 170 });
  });
}

export function renderTray() {
  const tray = $('#tray');
  const list = ui.picks.map(storyByKey).filter(Boolean);
  ui.picks = list.map((s) => s.key);
  if (!list.length) {
    tray.hidden = true;
    return;
  }
  tray.hidden = false;
  tray.innerHTML = `<span class="t-names">${icon('compare')} ${esc(list.map((s) => s.title).join(' · '))}</span>
    <button class="btn sm primary" data-action="compare" ${list.length < 2 ? 'disabled' : ''}>Comparar ${list.length}</button>
    <button class="icon-btn" style="width:30px;height:30px" data-action="clear-picks" aria-label="Vaciar comparativa">${icon('close')}</button>`;
}

on('pick', (el) => {
  const key = el.dataset.key;
  if (ui.picks.includes(key)) ui.picks = ui.picks.filter((k) => k !== key);
  else if (ui.picks.length >= 4) return toast('Como mucho cuatro a la vez');
  else ui.picks = [...ui.picks, key];
  $$(`.pick[data-key="${CSS.escape(key)}"], .pick-btn[data-key="${CSS.escape(key)}"]`).forEach((b) => b.classList.toggle('on', ui.picks.includes(key)));
  renderTray();
  if (modalOpen() && $('.compare')) {
    if (ui.picks.length >= 2) openCompare();
    else closeModal();
  }
});
on('clear-picks', () => {
  ui.picks = [];
  $$('.pick.on, .pick-btn.on').forEach((b) => b.classList.remove('on'));
  renderTray();
});
on('compare', () => openCompare());
