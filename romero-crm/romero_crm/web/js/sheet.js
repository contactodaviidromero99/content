// Ficha lateral: la de una historia (todo lo que hay que saber para hacer el vídeo) y la de un día
// del calendario (tareas, publicados, festividades y aniversarios).
import { icon } from './icons.js';
import * as F from './format.js';
import * as C from './charts.js';
import { $, api, copyText, esc, loadCalendar, nicheName, on, post, storyByKey, storyForTopic, toast, topicByKey, ui } from './core.js';
import * as U from './ui.js';
import { efemVisible, festVisible } from './views/calendario.js';

const sheet = () => $('#sheet');

export function openSheet(html, kind) {
  const el = sheet();
  el.innerHTML = html;
  el.dataset.kind = kind;
  $('#scrim').hidden = false;
  el.classList.add('open');
  el.setAttribute('aria-hidden', 'false');
  el.scrollTop = 0;
  el.focus({ preventScroll: true });
}

export function closeSheet() {
  ui.sheet = null;
  ui.selectedDay = null;
  const el = sheet();
  el.classList.remove('open');
  el.setAttribute('aria-hidden', 'true');
  $('#scrim').hidden = true;
  $$selected().forEach((c) => c.classList.remove('selected'));
  C.hideTip();
}

function $$selected() {
  return [...document.querySelectorAll('.cal-cell.selected')];
}

/* ---------- Brief para Claude ---------- */

export function buildBrief(story, detail) {
  const lines = [`HISTORIA: ${story.title}`, `NICHO: ${nicheName(story.niche)} · ${story.scope === 'mundo' ? 'internacional' : 'España'}`,
    `FASE: ${story.phase_label} (calor ${story.heat}/100, potencial ${story.potential}/100)`];
  if (story.members?.length) lines.push(`INCLUYE: ${story.members.map((m) => m.title).join(', ')}`);
  for (const line of story.synopsis || []) lines.push(`QUÉ HA PASADO: ${line.text}${line.source ? ` (${line.source})` : ''}`);
  if (story.context) lines.push(`CONTEXTO: ${story.context.subject}: ${story.context.text}`);
  if (story.remaining_hours) lines.push(`MARGEN ESTIMADO: ~${F.hours(story.remaining_hours)}`);
  if (story.summary) lines.push(`CIFRAS: ${story.summary}`);
  const news = (detail?.news || story.news || []).slice(0, 6).map((n) => `- ${n.title}${n.source ? ` (${n.source})` : ''}`);
  if (news.length) lines.push('', 'TITULARES:', ...news);
  if (story.related?.length) lines.push('', `LO QUE BUSCA LA GENTE: ${story.related.slice(0, 8).join(', ')}`);
  const yt = detail?.youtube || story.youtube;
  if (yt) {
    lines.push('', yt.count
      ? `COMPETENCIA EN YOUTUBE (última semana): ${yt.count >= 20 ? '20+' : yt.count} vídeos; el más visto, ${F.num(yt.top_views)} visualizaciones (${U.YT_TEXT[yt.level] || yt.label}).`
      : 'COMPETENCIA EN YOUTUBE (última semana): ningún vídeo sobre el tema (hueco claro).');
    if (yt.top_title) lines.push(`EL VÍDEO QUE MÁS FUNCIONA: «${yt.top_title}»`);
  }
  if (story.angle?.verdict) lines.push('', `ENFOQUE SEGÚN LOS DATOS: ${story.angle.verdict}`, ...(story.angle.tips || []).map((t) => `- ${t}`));
  lines.push('', 'Quiero un short narrativo (60-90 s) sobre esta historia con mi estilo de guion. Propón 3 ángulos que NO sean los obvios, cada uno con un hook de una frase y una idea de cierre memorable. Distingue hechos verificados de interpretaciones.');
  return lines.join('\n');
}

/* ---------- Ficha de una historia ---------- */

function storyHtml(story, detail, loading) {
  const lead = topicByKey(story.key) || {};
  const typical = story.typical_hours || 20;
  const elapsed = story.elapsed_hours;
  const used = elapsed !== null && elapsed !== undefined ? Math.min(100, (elapsed / typical) * 100) : null;
  const yt = detail?.youtube || null;
  const news = (detail?.news || story.news || []).slice(0, 8);
  const q = encodeURIComponent(lead.query || story.title);
  const links = [
    [lead.google?.url || `https://trends.google.com/trends/explore?geo=ES&q=${q}`, 'Google Trends', 'google'],
    [`https://www.tiktok.com/search?q=${q}`, 'TikTok', 'tiktok'],
    [`https://www.instagram.com/explore/search/keyword/?q=${q}`, 'Instagram', 'instagram'],
    [`https://www.youtube.com/results?search_query=${q}`, 'YouTube', 'youtube'],
    [`https://x.com/search?q=${q}&src=typed_query`, 'X', 'xlogo'],
    [lead.wikipedia?.url || `https://es.wikipedia.org/w/index.php?search=${q}`, 'Wikipedia', 'book'],
  ].map(([url, label, ico]) => U.extLink(url, `${icon(ico)}${esc(label)}`, 'btn sm ghost')).join('');
  const members = (story.members || []).map((m) => m.key
    ? `<button class="chip" data-action="open-topic" data-key="${esc(m.key)}">${esc(m.title)}</button>`
    : `<span class="chip">${esc(m.title)}</span>`).join('');
  const ytHtml = yt ? `
      <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:6px">${U.ytLevel(yt, true)}
        <span class="muted small">${yt.count ? `${yt.count >= 20 ? '20+' : yt.count} vídeos esta semana · el más visto ${F.num(yt.top_views)}` : 'Nadie ha subido vídeos sobre esto esta semana'}</span></div>
      ${(yt.videos || []).slice(0, 4).map((v) => `<div class="video"><span class="thumb"><img src="${esc(F.safeUrl(v.thumbnail))}" alt="" loading="lazy"></span>
        <div style="min-width:0">${U.extLink(v.url, `<span class="v-title">${esc(v.title)}</span>`)}<div class="v-meta">${esc(v.channel || '')}${v.channel ? ' · ' : ''}${F.num(v.views)} visualizaciones</div></div></div>`).join('')}`
    : loading ? '<div class="skeleton" style="height:90px"></div>' : (story.youtube ? `${U.ytLevel(story.youtube, true)}` : '<div class="muted small">No se pudo consultar YouTube para esta historia.</div>');
  return `
    <div class="sheet-head"><div class="row"><div class="brief-tags">${story.alert ? U.alertTag() : ''}${U.nicheTag(story.niche)}${U.scopeTag(story)}${U.phase(story)}</div>
      <button class="icon-btn" data-action="close-sheet" aria-label="Cerrar">${icon('close')}</button></div>
      <h2 class="sheet-title">${esc(story.title)}</h2></div>
    <div class="sheet-body">
      <section class="sheet-section"><h3>Qué ha pasado</h3>${U.synopsisHtml(story, true)}${U.contextHtml(story)}
        ${story.why?.url ? `<div class="chip-row" style="margin-top:12px">${U.extLink(story.why.url, `${icon('external')}Leer la noticia`, 'btn sm')}</div>` : ''}</section>
      <section class="sheet-section"><h3>${icon('target')}Cómo enfocarlo</h3>${U.angleHtml(story)}
        ${ui.settings?.ai_key_set && !story.ai ? `<div class="chip-row" style="margin-top:12px"><button class="btn sm" data-action="ask-ai" data-key="${esc(story.key)}">${icon('sparkles')}Pedir ideas a Claude</button></div>` : ''}</section>
      <section class="sheet-section"><h3>Predicción</h3>
        <div class="forecast-top">${U.ring(story.potential)}<div>${U.phase(story)}<small>${esc(story.phase_reason || '')}</small></div></div>
        ${used !== null ? `<div class="window"><div class="window-head"><span>Lleva ${esc(F.hours(elapsed))}</span><span>Suele durar ~${esc(F.hours(typical))}</span></div>
          <div class="window-track"><i style="width:${used.toFixed(1)}%"></i></div>
          <div class="small muted">${story.remaining_hours > 0.5 ? `Margen para publicar: <b style="color:var(--text)">~${esc(F.hours(story.remaining_hours))}</b>` : 'Margen casi agotado: mejor un ángulo de fondo que no caduque.'}</div></div>` : ''}
        <div class="stat-grid" style="margin-top:14px">
          <div><span>Calor</span><b>${story.heat}</b></div><div><span>${(story.trends || 0) > 1 ? 'Búsquedas (total)' : 'Búsquedas'}</span><b>${U.volume(story)}</b></div>
          <div><span>En X</span><b>${story.x_rank ? `nº ${story.x_rank}` : '—'}</b></div><div><span>Medios</span><b>${story.outlets || '—'}</b></div></div>
      </section>
      ${members ? `<section class="sheet-section"><h3>Forma parte de esta historia</h3><div class="member-chips">${members}</div></section>` : ''}
      <section class="sheet-section"><h3>${esc(story.series_label || 'Evolución')}</h3><div class="chart-box" id="sheet-chart"></div></section>
      ${news.length ? `<section class="sheet-section"><h3>Titulares</h3>${news.map((n) => U.extLink(n.url, `<b>${esc(n.title)}</b><span>${esc(n.source || '')}${n.published ? ` · ${esc(F.ago(n.published))}` : ''}</span>`, 'news-item')).join('')}</section>` : ''}
      <section class="sheet-section"><h3>${icon('youtube')}Competencia en YouTube</h3>${ytHtml}</section>
      ${story.related?.length ? `<section class="sheet-section"><h3>Lo que busca la gente</h3><div class="member-chips">${story.related.map((r) => U.extLink(`https://trends.google.com/trends/explore?geo=ES&q=${encodeURIComponent(r)}`, `<span class="chip">${esc(r)}</span>`)).join('')}</div></section>` : ''}
      <section class="sheet-section"><h3>Llévalo a guion</h3><div class="brief-box" id="brief-box">${esc(buildBrief(story, detail))}</div>
        <div class="chip-row" style="margin-top:10px"><button class="btn sm primary" data-action="copy-brief" data-key="${esc(story.key)}">${icon('copy')}Copiar brief para Claude</button>
          <button class="btn sm" data-action="plan-story" data-key="${esc(story.key)}">${icon('plus')}Al calendario</button>
          <button class="btn sm ghost" data-action="pick" data-key="${esc(story.key)}">${icon('compare')}${ui.picks.includes(story.key) ? 'Quitar de comparar' : 'Comparar'}</button></div></section>
      <section class="sheet-section"><h3>Buscar en</h3><div class="chip-row">${links}</div></section>
    </div>`;
}

function mountChart(story) {
  const el = $('#sheet-chart');
  if (!el) return;
  const n = (story.series || []).length;
  const describe = (value, i) => {
    const back = n - 1 - i;
    if (story.series_kind === 'google_volume') {
      const ts = (story.series_end || Date.now() / 1000) - back * (story.series_step || 3600);
      return { value: value > 0 ? `${F.num(value)}+` : 'Sin registrar', label: 'búsquedas', title: back === 0 ? 'Ahora' : F.clock(ts) };
    }
    if (story.series_kind === 'x') return { value: value > 0 ? `Nº ${Math.round(51 - value)}` : 'Fuera', label: 'en X', title: back === 0 ? 'Ahora' : `Hace ${back} h` };
    return { value: `${F.num(value)}`, label: 'lecturas', title: back === 0 ? 'Último día' : `${back} días antes` };
  };
  const xLabel = (i) => {
    const back = n - 1 - i;
    if (story.series_kind === 'google_volume') return back === 0 ? 'ahora' : F.clock((story.series_end || Date.now() / 1000) - back * (story.series_step || 3600));
    if (story.series_kind === 'x') return back === 0 ? 'ahora' : `-${back} h`;
    return back === 0 ? 'último' : `-${back} d`;
  };
  const isX = story.series_kind === 'x';
  C.lineChart(el, story.series || [], { describe, xLabel, height: 170, ticks: isX ? [1, 26, 50] : null, yFormat: (v) => (isX ? (v > 0 ? `${Math.round(51 - v)}º` : '') : F.num(v)) });
}

export async function openStory(key) {
  const story = storyByKey(key) || storyForTopic(key);
  if (!story) return;
  ui.sheet = { kind: 'story', key: story.key };
  openSheet(storyHtml(story, null, true), 'story');
  const { animateIn } = await import('./fx.js');
  animateIn(sheet());
  requestAnimationFrame(() => mountChart(story));
  try {
    const detail = await api(`/api/topic?key=${encodeURIComponent(story.key)}`);
    if (ui.sheet?.key !== story.key) return;
    const scroll = sheet().scrollTop;
    sheet().innerHTML = storyHtml(story, detail.error ? null : detail, false);
    sheet().scrollTop = scroll;
    sheet().querySelectorAll('[data-ring]').forEach((c) => { c.style.transition = 'none'; c.style.strokeDashoffset = c.dataset.ring; });
    sheet().querySelectorAll('[data-count]').forEach((b) => { b.textContent = b.dataset.count; });
    ui.sheet.detail = detail;
    mountChart(story);
  } catch {
    // La ficha ya muestra lo que hay en el estado.
  }
}

/* ---------- Ficha de un día ---------- */

function dayHtml(day) {
  const tasks = day.items.map((i) => U.taskRow(i, { showKind: true })).join('');
  const published = day.published.map((p) => `<div class="mine-item">${U.platformBadge(p.platform)}
      <div style="min-width:0"><div class="ri-title">${U.extLink(p.url, esc(p.title || 'Vídeo'))}</div><div class="ri-sub">${esc(U.PLATFORMS[p.platform]?.label || p.platform)}</div></div>
      <div class="mi-views">${p.views !== null && p.views !== undefined ? F.num(p.views) : '—'}<span>visualizaciones</span></div></div>`).join('');
  const fests = day.festivities.filter(festVisible).map((f) => `<div class="efem-card">
      <div class="e-top"><span class="tag" style="color:var(--${f.kind === 'internacional' ? 'sky' : 'rose'})">${esc(f.kind_label)}</span></div>
      <div class="e-title">${esc(f.name)}</div>
      ${f.idea ? `<div class="e-idea">${icon('bulb')}<span>${esc(f.idea)}</span></div>
        <div class="e-actions"><button class="btn xs primary" data-action="plan-idea" data-day="${esc(day.date)}" data-title="${esc(f.idea)}">${icon('plus')}Planificar vídeo</button></div>` : ''}
    </div>`).join('');
  const efems = day.efemerides.filter(efemVisible);
  const highlights = efems.filter((e) => e.highlight);
  const others = efems.filter((e) => !e.highlight);
  const efemCard = (e) => `<div class="efem-card">
      <div class="e-top"><span class="years-badge"><b>${esc(e.years_ago)}</b> años</span>${(e.reasons || []).filter((r) => !r.endsWith('años')).map((r) => `<span class="tag">${esc(r)}</span>`).join('')}<span class="muted small">${esc(e.year)}</span></div>
      <div class="e-title">${esc(e.title || '')}</div><div class="e-text">${esc(e.text)}</div>
      <div class="e-actions"><button class="btn xs primary" data-action="plan-idea" data-day="${esc(day.date)}" data-title="${esc(`${e.years_ago} años de ${e.title || e.text.slice(0, 60)}`)}" data-notes="${esc(`${e.text}${e.url ? `\n${e.url}` : ''}`)}">${icon('plus')}Planificar vídeo</button>
        ${e.url ? U.extLink(e.url, `${icon('book')}Wikipedia`, 'btn xs ghost') : ''}</div></div>`;
  const date = F.parseIso(day.date);
  return `
    <div class="sheet-head"><div class="row"><div><div class="eyebrow">${esc(F.cap(F.dayDistance(day.date)))}</div>
      <h2 class="sheet-title">${esc(F.cap(F.weekday(day.date)))} ${date.getDate()} de ${esc(F.monthName(date.getMonth()))}</h2></div>
      <button class="icon-btn" data-action="close-sheet" aria-label="Cerrar">${icon('close')}</button></div></div>
    <div class="sheet-body">
      <section class="sheet-section"><h3>Tus tareas <button class="btn xs" data-action="plan-new" data-day="${esc(day.date)}">${icon('plus')}Añadir</button></h3>
        ${tasks ? `<div class="task-list">${tasks}</div>` : '<div class="empty-line" style="padding-left:0">Nada apuntado este día.</div>'}</section>
      ${published ? `<section class="sheet-section"><h3>Publicado</h3>${published}</section>` : ''}
      ${fests ? `<section class="sheet-section"><h3>Festividades</h3>${fests}</section>` : ''}
      ${highlights.length ? `<section class="sheet-section"><h3>Aniversarios que merecen un vídeo</h3>${highlights.map(efemCard).join('')}</section>` : ''}
      ${others.length ? `<section class="sheet-section"><details><summary class="link" style="cursor:pointer">Más efemérides de este día (${others.length})</summary><div style="margin-top:10px">${others.map(efemCard).join('')}</div></details></section>` : ''}
      ${!highlights.length && !others.length && !fests ? '<section class="sheet-section"><div class="muted small">Sin aniversarios ni festividades destacadas este día.</div></section>' : ''}
    </div>`;
}

export async function openDay(iso) {
  ui.selectedDay = iso;
  ui.sheet = { kind: 'day', day: iso };
  document.querySelectorAll('.cal-cell').forEach((c) => c.classList.toggle('selected', c.dataset.day === iso));
  let data;
  try {
    data = await loadCalendar(iso.slice(0, 7));
  } catch {
    return;
  }
  const day = data.days.find((d) => d.date === iso);
  if (!day || ui.sheet?.day !== iso) return;
  const open = sheet().classList.contains('open');
  const scroll = sheet().scrollTop;
  openSheet(dayHtml(day), 'day');
  if (open) sheet().scrollTop = scroll;
}

on('open-story', (el) => openStory(el.dataset.key));
on('open-topic', (el) => {
  const story = storyForTopic(el.dataset.key);
  if (story && story.key !== ui.sheet?.key) openStory(story.key);
});
on('open-day', (el) => openDay(el.dataset.day));
on('close-sheet', () => closeSheet());
on('copy-brief', (el) => {
  const story = storyByKey(el.dataset.key);
  if (!story) return;
  const detail = ui.sheet?.key === story.key ? ui.sheet.detail : null;
  copyText(buildBrief(story, detail), 'Brief copiado: pégalo en Claude');
});

on('ask-ai', async (el) => {
  const story = storyByKey(el.dataset.key);
  if (!story) return;
  el.disabled = true;
  el.innerHTML = `${icon('sparkles')}Pensando…`;
  try {
    const res = await post('/api/ai/story', { key: story.key });
    if (res.error) throw new Error(res.error);
    story.ai = res.ai;
    if (ui.sheet?.key === story.key) openStory(story.key);
  } catch (err) {
    toast(err.message || 'Claude no respondió');
    el.disabled = false;
    el.innerHTML = `${icon('sparkles')}Pedir ideas a Claude`;
  }
});
