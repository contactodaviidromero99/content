// Calendario: un mes de verdad, día a día. Tus tareas (grabar, publicar…) con su tic, tus vídeos
// publicados, las festividades y los aniversarios que merecen un vídeo.
import { icon } from '../icons.js';
import * as F from '../format.js';
import { esc, loadCalendar, on, rerender, ui } from '../core.js';
import * as U from '../ui.js';

const DOW = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];
const LAYERS = [
  ['tareas', 'Mis tareas', 'var(--violet)'],
  ['publicados', 'Publicados', 'var(--mint)'],
  ['aniversarios', 'Aniversarios', 'var(--amber)'],
  ['festividades', 'Festividades', 'var(--rose)'],
];

export function efemVisible(item) {
  if (ui.calRound && !(item.round_level >= 1)) return false;
  if (ui.calSpain && !item.spain) return false;
  return true;
}

export function festVisible(fest) {
  return !ui.calSpain || fest.spain;
}

function pills(day) {
  const out = [];
  if (ui.calLayers.festividades) {
    for (const fest of day.festivities.filter(festVisible)) {
      out.push(`<div class="cal-pill fest ${esc(fest.kind)}" title="${esc(fest.kind_label)}${fest.idea ? ` · Idea: ${esc(fest.idea)}` : ''}">${icon(fest.idea ? 'bulb' : 'flag')}<span>${esc(fest.name)}</span></div>`);
    }
  }
  if (ui.calLayers.tareas) {
    for (const item of day.items) {
      out.push(`<div class="cal-pill k-${esc(item.kind)}${item.done ? ' done' : ''}" title="${esc(U.KIND[item.kind]?.label || '')}: ${esc(item.title)}">${icon(item.done ? 'check' : U.KIND[item.kind]?.icon || 'dot')}<span>${esc(item.title)}</span></div>`);
    }
  }
  if (ui.calLayers.publicados) {
    for (const video of day.published) {
      out.push(`<div class="cal-pill pub" title="Publicado en ${esc(U.PLATFORMS[video.platform]?.label || video.platform)}${video.views ? ` · ${F.num(video.views)} visualizaciones` : ''}">${icon(U.PLATFORMS[video.platform]?.icon || 'play')}<span>${esc(video.title || 'Vídeo')}${video.views ? ` · ${F.num(video.views)}` : ''}</span></div>`);
    }
  }
  if (ui.calLayers.aniversarios) {
    const highlights = day.efemerides.filter((e) => e.highlight && efemVisible(e)).slice(0, 2);
    for (const item of highlights) {
      out.push(`<div class="cal-pill efem" title="${esc(item.text)}">${icon('star')}<span>${esc(item.years_ago)} años · ${esc(item.title || item.text)}</span></div>`);
    }
  }
  const limit = 4;
  const extra = out.length - limit;
  return out.slice(0, limit).join('') + (extra > 0 ? `<div class="cal-more">+${extra} más</div>` : '');
}

function grid(data) {
  const head = DOW.map((d) => `<div class="cal-dow">${d}</div>`).join('');
  const cells = data.days.map((day) => {
    const date = F.parseIso(day.date);
    const cls = ['cal-cell', day.in_month ? '' : 'out', day.today ? 'today' : '', day.past ? 'past' : '', ui.selectedDay === day.date ? 'selected' : ''].filter(Boolean).join(' ');
    const hasFest = day.festivities.some((f) => f.kind === 'nacional');
    return `<div class="${cls}" data-action="open-day" data-day="${esc(day.date)}" tabindex="0" aria-label="${esc(F.niceDate(day.date))}">
      <div class="cal-num"><b>${date.getDate()}</b>${hasFest ? '<i class="fest-dot" title="Festivo nacional"></i>' : ''}</div>
      ${pills(day)}</div>`;
  }).join('');
  return `<div class="panel cal-grid rise">${head}${cells}</div>`;
}

export function render() {
  const month = ui.month;
  const [year, monthIndex] = month.split('-').map(Number);
  const layerChips = LAYERS.map(([id, label, color]) => `<button class="chip${ui.calLayers[id] ? ' on' : ''}" style="--c:${color}" data-action="cal-layer" data-layer="${id}"><span class="dot"></span>${label}</button>`).join('');
  const html = `<div class="cal-top">
      <div><div class="eyebrow">Tu calendario de producción</div>
        <div class="cal-month"><h1 class="display">${esc(F.monthName(monthIndex - 1))}</h1><span class="year">${year}</span></div></div>
      <div class="cal-controls">
        <button class="icon-btn" data-action="cal-prev" aria-label="Mes anterior">${icon('chevronLeft')}</button>
        <button class="btn sm ghost" data-action="cal-today">Hoy</button>
        <button class="icon-btn" data-action="cal-next" aria-label="Mes siguiente">${icon('chevronRight')}</button>
        <button class="btn primary" data-action="plan-new">${icon('plus')}Nueva tarea</button>
      </div></div>
    <div class="cal-layers"><div class="chip-row">${layerChips}</div>
      <div class="chip-row">
        <label class="switch"><input type="checkbox" data-action-change="cal-round" ${ui.calRound ? 'checked' : ''}><span class="track"></span>Solo aniversarios redondos</label>
        <label class="switch"><input type="checkbox" data-action-change="cal-spain" ${ui.calSpain ? 'checked' : ''}><span class="track"></span>Solo España</label>
      </div></div>
    <div id="cal-root"><div class="panel skeleton" style="height:640px"></div></div>`;
  return {
    html,
    async mount(root) {
      let data;
      try {
        data = await loadCalendar(month);
      } catch {
        root.querySelector('#cal-root').innerHTML = `<div class="panel">${U.emptyState('alert', 'No se pudo cargar el calendario')}</div>`;
        return;
      }
      if (ui.month !== month || !root.querySelector('#cal-root')) return;
      root.querySelector('#cal-root').innerHTML = grid(data);
    },
  };
}

function shiftMonth(delta) {
  const [y, m] = ui.month.split('-').map(Number);
  const date = new Date(y, m - 1 + delta, 1);
  ui.month = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
  rerender({ keepScroll: true });
}

on('cal-prev', () => shiftMonth(-1));
on('cal-next', () => shiftMonth(1));
on('cal-today', () => { ui.month = F.todayIso().slice(0, 7); rerender({ keepScroll: true }); });
on('cal-layer', (el) => { ui.calLayers[el.dataset.layer] = !ui.calLayers[el.dataset.layer]; rerender({ keepScroll: true }); });
on('cal-round', (el) => { ui.calRound = el.checked; rerender({ keepScroll: true }); });
on('cal-spain', (el) => { ui.calSpain = el.checked; rerender({ keepScroll: true }); });
