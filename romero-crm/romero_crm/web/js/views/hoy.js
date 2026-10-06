// Hoy: lo primero que ves. Las cinco historias que más importan ahora, qué ha pasado, cómo enfocar
// el vídeo y cuánto margen queda; tu agenda del día y lo que viene en el calendario.
import { icon } from '../icons.js';
import * as F from '../format.js';
import { esc, greeting, nicheColor, storyByKey, stories, ui } from '../core.js';
import * as U from '../ui.js';

function briefRow(story, index, alerts) {
  const isAlert = alerts.has(story.key);
  const tags = [isAlert ? U.alertTag() : '', U.nicheTag(story.niche), U.scopeTag(story), story.routine ? '<span class="tag routine">Recurrente</span>' : ''].join('');
  const facts = [
    ['Margen', U.margin(story)],
    ['Google', story.volume ? `${F.num(story.volume)}+` : '—'],
    ['YouTube', U.ytLevel(story.youtube, true)],
  ];
  if (story.x_rank) facts.push(['X', `nº ${story.x_rank}`]);
  else if ((story.outlets || 0) >= 2) facts.push(['Medios', `${story.outlets}`]);
  return `<article class="brief-row panel glow rise${index === 0 ? ' top' : ''}${isAlert ? ' alert-row' : ''}" style="--i:${index}" data-action="open-story" data-key="${esc(story.key)}" tabindex="0">
    <div class="brief-rank"><b>${String(index + 1).padStart(2, '0')}</b></div>
    <div class="brief-main">
      <div class="brief-tags">${tags}</div>
      <h3 class="brief-title">${esc(story.title)}</h3>
      ${(story.members || []).length ? `<div class="brief-members">${U.membersLine(story)}</div>` : ''}
      <div class="block-label">Qué ha pasado</div>
      ${U.synopsisHtml(story)}
      ${story.synopsis?.length < 2 ? U.contextHtml(story) : ''}
    </div>
    <div class="brief-angle">
      <div class="block-label">${icon('target')}Cómo enfocarlo</div>
      ${U.angleHtml(story)}
    </div>
    <div class="forecast">
      <div class="forecast-top">${U.ring(story.potential)}<div>${U.phase(story)}<small>Potencial · calor ${esc(story.heat)}</small></div>${U.compareButton(story.key)}</div>
      <div class="facts">${facts.map(([label, value]) => `<div class="fact"><span>${label}</span><b>${value}</b></div>`).join('')}</div>
      <div class="forecast-actions">
        <button class="btn xs primary" data-action="plan-story" data-key="${esc(story.key)}">${icon('plus')}Al calendario</button>
        <button class="btn xs ghost" data-action="copy-brief" data-key="${esc(story.key)}" title="Copiar un brief para pedirle a Claude el guion">${icon('copy')}Brief</button>
      </div>
    </div>
  </article>`;
}

function agendaPanel() {
  const agenda = ui.state?.agenda || {};
  const today = agenda.today || [];
  const tomorrow = agenda.tomorrow || [];
  const overdue = agenda.overdue || [];
  const block = (title, items, opts = {}) => (items.length ? `<div class="block-label" style="margin:12px 10px 4px">${title}</div><div class="task-list">${items.map((i) => U.taskRow(i, opts)).join('')}</div>` : '');
  const nothing = !today.length && !tomorrow.length && !overdue.length;
  return `<section class="panel glow rise" style="--i:6">
    <div class="panel-head"><div><h3>Tu día</h3><p>${esc(F.cap(F.niceDate(F.todayIso())))}</p></div>
      <button class="btn sm" data-action="plan-new" data-day="${F.todayIso()}">${icon('plus')}Tarea</button></div>
    <div class="panel-body" style="padding-top:6px">
      ${nothing ? '<div class="empty-line">Nada apuntado para hoy ni mañana. Añade lo que vas a grabar o publicar y márcalo cuando esté hecho.</div>' : ''}
      ${block('Hoy', today)}
      ${block('Mañana', tomorrow)}
      ${block('Se quedó pendiente', overdue, { showDay: true })}
    </div>
  </section>`;
}

function horizonPanel() {
  const items = (ui.state?.horizon || []).slice(0, 5);
  const rows = items.map((h) => {
    const date = F.parseIso(h.date);
    const sub = h.type === 'efem'
      ? `${h.years} años · ${esc(h.sub.length > 110 ? `${h.sub.slice(0, 108)}…` : h.sub)}`
      : esc(h.sub);
    return `<div class="horizon-item" data-action="open-day" data-day="${esc(h.date)}" style="cursor:pointer">
      <div class="date-badge"><b>${date.getDate()}</b><span>${F.monthShort(date.getMonth())}</span></div>
      <div style="min-width:0"><div class="h-title">${esc(h.title)}</div><div class="h-sub">${sub}</div>
        ${h.idea ? `<div class="h-idea">${icon('bulb')} ${esc(h.idea)}</div>` : ''}</div></div>`;
  }).join('');
  return `<section class="panel glow rise" style="--i:7">
    <div class="panel-head"><div><h3>En el horizonte</h3><p>Aniversarios y fechas de las próximas semanas que merecen un vídeo</p></div>
      <a class="btn sm ghost" href="#/calendario">${icon('calendar')}Calendario</a></div>
    <div class="panel-body" style="padding-top:8px">${rows || '<div class="empty-line">Nada destacado en las próximas tres semanas.</div>'}</div>
  </section>`;
}

function moreStories(exclude) {
  const list = stories().filter((s) => !exclude.has(s.key)).slice(0, 6);
  if (!list.length) return '';
  return `<div class="section-title"><h2>También en el radar</h2><a class="link" href="#/noticias">Todas las noticias ${icon('arrowRight')}</a></div>
    <div class="more-stories">${list.map((s, i) => `<div class="mini-story panel glow rise" style="--i:${8 + i}" data-action="open-story" data-key="${esc(s.key)}" tabindex="0">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:8px">${U.nicheTag(s.niche)}${U.phase(s)}</div>
      <div class="ms-title">${esc(s.title)}</div><div class="ms-why">${esc(U.whyLine(s))}</div></div>`).join('')}</div>`;
}

export function render() {
  const state = ui.state;
  const keys = state?.portada?.keys || [];
  const alerts = new Set(state?.portada?.alerts || []);
  const front = keys.map(storyByKey).filter(Boolean);
  const { hello, name } = greeting();
  const rising = stories().filter((s) => ['explosivo', 'subiendo', 'temprana'].includes(s.phase)).length;
  const hero = `<div class="hero">
    <div><div class="eyebrow">${esc(F.cap(F.niceDate(F.todayIso())))}${state?.generated_at ? ` · actualizado ${esc(F.ago(state.generated_at))}` : ''}</div>
      <h1 class="display">${esc(hello)}${name ? `, <em>${esc(name)}</em>` : ''}.</h1>
      <p class="lede">${front.length ? 'Las cinco historias que más importan ahora en España, explicadas y con su enfoque.' : 'Todavía no hay historias que contar.'}</p></div>
    <div class="hero-meta">
      <div class="stat-mini"><b data-count="${stories().length}">0</b><span>historias</span></div>
      <div class="stat-mini"><b data-count="${rising}">0</b><span>subiendo</span></div>
    </div></div>`;
  const list = front.length ? `<div class="brief">${front.map((s, i) => briefRow(s, i, alerts)).join('')}</div>` : '';
  const html = `${hero}${list}<div class="duo">${agendaPanel()}${horizonPanel()}</div>${moreStories(new Set(keys))}`;
  return { html };
}
