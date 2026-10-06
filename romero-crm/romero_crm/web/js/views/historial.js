// Historial: la semana en un vistazo. El tema estrella, lo grande de cada día, los nichos que
// subieron o bajaron, cuándo arrancan las tendencias y lo que publicaste tú.
import { icon } from '../icons.js';
import * as F from '../format.js';
import { api, esc, nicheColor, on, rerender, ui } from '../core.js';
import * as U from '../ui.js';

async function loadRecap(week) {
  const cached = ui.recap[week];
  if (cached && Date.now() - cached._at < 120000) return cached;
  const data = await api(`/api/recap?week=${week}`);
  data._at = Date.now();
  ui.recap[week] = data;
  return data;
}

function weekLabel(week) {
  const start = F.parseIso(week.start);
  const end = F.parseIso(week.end);
  const sameMonth = start.getMonth() === end.getMonth();
  return `${start.getDate()}${sameMonth ? '' : ` de ${F.monthName(start.getMonth())}`} – ${end.getDate()} de ${F.monthName(end.getMonth())}`;
}

function starCard(star) {
  if (!star) {
    return `<section class="panel star-card rise">${U.emptyState('history', 'Aún no hay historial de esta semana', 'Se completa solo mientras el programa está abierto.')}</section>`;
  }
  const stats = [
    star.volume ? [`${F.num(star.volume)}+`, 'búsquedas en Google'] : [String(star.heat), 'de calor máximo'],
    [String(star.days), star.days === 1 ? 'día en tendencia' : 'días en tendencia'],
    star.yt_top ? [F.num(star.yt_top), `visualizaciones del vídeo más visto${star.yt_count ? ` (${star.yt_count >= 20 ? '20+' : star.yt_count} vídeos)` : ''}`] : null,
  ].filter(Boolean);
  return `<section class="panel star-card glow rise" style="--i:0">
    <span class="burst"></span>
    <div class="eyebrow">${icon('star')}El tema de la semana</div>
    <h2>${esc(star.title)}</h2>
    <div class="brief-tags">${U.nicheTag(star.niche)}${star.scope === 'mundo' ? '<span class="tag mundo">Mundo</span>' : ''}</div>
    ${star.why ? `<p class="why">${esc(star.why)}</p>` : ''}
    ${star.members?.length ? `<p class="why">También: ${esc(star.members.join(' · '))}</p>` : ''}
    <div class="star-stats">${stats.map(([value, label]) => `<div class="big-stat"><b>${esc(value)}</b><span>${esc(label)}</span></div>`).join('')}</div>
    ${star.yt_top_title ? `<p class="why" style="margin-top:14px">${icon('youtube')} El vídeo que mejor funcionó: «${esc(star.yt_top_title)}»</p>` : ''}
  </section>`;
}

function topList(top) {
  const rows = (top || []).map((s, i) => `<div class="rank-item"><span class="ri-n">${i + 2}</span>
    <div style="min-width:0"><div class="ri-title">${esc(s.title)}</div><div class="ri-sub">${esc(s.niche_name)} · ${s.days} ${s.days === 1 ? 'día' : 'días'}</div></div>
    <div class="ri-side">${s.volume ? `${F.num(s.volume)}+` : `${s.heat}°`}</div></div>`).join('');
  return `<section class="panel rise" style="--i:1"><div class="panel-head"><div><h3>También fueron grandes</h3><p>Lo más buscado de la semana</p></div></div>
    <div class="panel-body" style="padding-top:8px"><div class="rank-list">${rows || '<div class="empty-line">Sin más temas destacados.</div>'}</div></div></section>`;
}

function weekStrip(days) {
  const max = Math.max(1, ...days.map((d) => d.count));
  return `<div class="week-strip">${days.map((d, i) => `<div class="day-tile panel glow rise${d.future ? ' future' : ''}" style="--i:${2 + i};--c:${d.top ? nicheColor(d.top.niche) : 'var(--line-2)'}">
    <div class="dt-day">${esc(d.weekday)} ${F.parseIso(d.day).getDate()}</div>
    <div class="dt-title">${d.top ? esc(d.top.title) : '<span class="muted">—</span>'}</div>
    <div class="dt-sub">${d.top?.volume ? `${F.num(d.top.volume)}+ búsquedas` : d.future ? 'Por llegar' : ''}</div>
    <div class="bar" title="${d.count} tendencias de Google"><i style="width:${Math.round((d.count / max) * 100)}%"></i></div></div>`).join('')}</div>`;
}

function nicheBars(niches) {
  if (!niches.length) return '<div class="empty-line">Aún no hay tendencias registradas esta semana.</div>';
  const max = Math.max(...niches.map((n) => n.share), 1);
  return `<div class="niche-bars">${niches.map((n, i) => {
    const delta = n.delta === null || n.delta === undefined ? '' : n.delta >= 1 ? `<small class="up">↑ ${F.num(n.delta)} pts</small>` : n.delta <= -1 ? `<small class="down">↓ ${F.num(Math.abs(n.delta))} pts</small>` : '<small class="muted">=</small>';
    return `<div class="nbar"><div style="min-width:0"><div class="nb-name">${esc(n.name)}</div><div class="nb-star">${n.star?.title ? esc(n.star.title) : ''}</div></div>
      <div class="nb-track"><i style="width:${(n.share / max) * 100}%;background:${nicheColor(n.id)};animation-delay:${i * 70}ms"></i></div>
      <div class="nb-val">${F.num(n.share)} %${delta}</div></div>`;
  }).join('')}</div>`;
}

function hoursStrip(hours, best) {
  const max = Math.max(1, ...hours);
  const inBest = (h) => best && (h === best.start || h === (best.start + 1) % 24);
  return `<div class="hours">${hours.map((v, h) => `<i class="${inBest(h) ? 'best' : ''}" style="height:${Math.max(3, (v / max) * 100)}%" title="${h}:00 · ${v} tendencias"></i>`).join('')}</div>
    <div class="hours-axis">${hours.map((_, h) => `<span>${h % 3 === 0 ? h : ''}</span>`).join('')}</div>`;
}

function mine(data) {
  const published = data.mine?.published || [];
  const done = data.mine?.done || [];
  if (!published.length && !done.length) {
    return '<div class="empty-line">Esta semana no hay vídeos tuyos registrados. Conecta tu canal de YouTube o Instagram en Ajustes, o marca tus tareas «Publicar» en el calendario.</div>';
  }
  const rows = published.map((p) => `<div class="mine-item">${U.platformBadge(p.platform)}
      <div style="min-width:0"><div class="ri-title">${esc(p.title || 'Vídeo')}</div><div class="ri-sub">${esc(F.cap(F.relDay(F.isoDate(new Date(p.published_at * 1000)))))}</div></div>
      <div class="mi-views">${p.views !== null && p.views !== undefined ? F.num(p.views) : '—'}<span>visualizaciones</span></div></div>`).join('');
  const tasks = done.length ? `<p class="muted small" style="margin:10px 8px 0">${done.length} ${done.length === 1 ? 'tarea hecha' : 'tareas hechas'}: ${esc(done.map((d) => d.title).slice(0, 6).join(' · '))}</p>` : '';
  return rows + tasks;
}

export function render() {
  const week = ui.recapWeek;
  const html = `<div id="recap-root"><div class="page-head"><div><div class="eyebrow">Historial</div><h1 class="display">La semana</h1></div></div>
    <div class="panel skeleton" style="height:360px"></div></div>`;
  return {
    html,
    async mount(root) {
      let data;
      try {
        data = await loadRecap(week);
      } catch {
        root.querySelector('#recap-root').innerHTML = `<div class="panel">${U.emptyState('alert', 'No se pudo cargar el historial')}</div>`;
        return;
      }
      if (ui.recapWeek !== week || !root.querySelector('#recap-root')) return;
      const w = data.week;
      const canBack = w.offset < Math.max(1, w.weeks_available);
      const best = data.best_window;
      root.querySelector('#recap-root').innerHTML = `
        <div class="page-head">
          <div><div class="eyebrow">${esc(w.label)} · ${esc(weekLabel(w))}</div><h1 class="display">${w.offset === 0 ? 'Esta <em>semana</em>' : w.offset === 1 ? 'La semana <em>pasada</em>' : `Hace ${w.offset} <em>semanas</em>`}</h1>
            <p class="lede">${w.trends ? `${F.num(w.trends)} tendencias de Google registradas.` : 'Todavía hay pocos datos de esta semana.'}</p></div>
          <div class="cal-controls">
            <button class="icon-btn" data-action="recap-prev" ${canBack ? '' : 'disabled'} aria-label="Semana anterior">${icon('chevronLeft')}</button>
            <button class="btn sm ghost" data-action="recap-now" ${w.offset === 0 ? 'disabled' : ''}>Esta semana</button>
            <button class="icon-btn" data-action="recap-next" ${w.offset === 0 ? 'disabled' : ''} aria-label="Semana siguiente">${icon('chevronRight')}</button>
          </div></div>
        <div class="recap-grid">${starCard(data.star)}${topList(data.top)}</div>
        <div class="section-title"><h2>Día a día</h2><p>El tema más grande de cada día</p></div>
        ${weekStrip(data.days)}
        <div class="recap-grid" style="margin-top:14px">
          <section class="panel rise" style="--i:9"><div class="panel-head"><div><h3>Por nichos</h3><p>Qué parte de las tendencias fue de cada tema, frente a la semana anterior</p></div></div>
            <div class="panel-body">${nicheBars(data.niches)}</div></section>
          <section class="panel rise" style="--i:10"><div class="panel-head"><div><h3>Cuándo arrancan</h3>
            <p>${best ? `Sobre todo entre las <b style="color:var(--text)">${best.start}:00 y las ${best.end}:00</b>: publica justo antes` : 'Hora de inicio de las tendencias'}</p></div></div>
            <div class="panel-body">${hoursStrip(data.hours, best)}
              ${data.lifetime_all ? `<div class="block-label" style="margin-top:18px">Cuánto duran</div><div class="pill-row"><span class="life-pill">De media <b>${esc(F.hours(data.lifetime_all))}</b></span>${data.lifetimes.slice(0, 5).map((l) => `<span class="life-pill">${esc(l.name)} <b>${esc(F.hours(l.median))}</b></span>`).join('')}</div>` : ''}
            </div></section>
        </div>
        <section class="panel rise" style="--i:11;margin-top:14px"><div class="panel-head"><div><h3>Tus vídeos de la semana</h3><p>Lo que publicaste y cómo funcionó</p></div><a class="btn sm ghost" href="#/calendario">${icon('calendar')}Calendario</a></div>
          <div class="panel-body" style="padding-top:8px">${mine(data)}</div></section>`;
      const { animateIn } = await import('../fx.js');
      animateIn(root);
    },
  };
}

on('recap-prev', () => { ui.recapWeek += 1; rerender(); });
on('recap-next', () => { ui.recapWeek = Math.max(0, ui.recapWeek - 1); rerender(); });
on('recap-now', () => { ui.recapWeek = 0; rerender(); });
