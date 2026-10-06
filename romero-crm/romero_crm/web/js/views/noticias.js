// Noticias: todas las historias, clasificadas por nichos (política, cine y series, deportes…), y lo
// que cuentan los medios aunque todavía no sea tendencia.
import { icon } from '../icons.js';
import * as F from '../format.js';
import { esc, nicheColor, nicheName, norm, on, rerender, stories, storyText, ui } from '../core.js';
import * as U from '../ui.js';

const SORTS = { score: 'Más importantes', heat: 'Más calientes', potential: 'Más potencial', recent: 'Más recientes' };

function filtered() {
  let list = stories();
  if (ui.niche !== 'all') list = list.filter((s) => (s.niches || [s.niche]).includes(ui.niche));
  if (ui.scope !== 'all') list = list.filter((s) => s.scope === ui.scope);
  if (ui.search) {
    const q = norm(ui.search);
    list = list.filter((s) => storyText(s).includes(q));
  }
  const by = {
    score: (a, b) => b.score - a.score,
    heat: (a, b) => b.heat - a.heat,
    potential: (a, b) => b.potential - a.potential,
    recent: (a, b) => (b.started_at || 0) - (a.started_at || 0),
  }[ui.sort] || ((a, b) => b.score - a.score);
  return [...list].sort(by);
}

function nicheChips() {
  const base = stories().filter((s) => ui.scope === 'all' || s.scope === ui.scope);
  const counts = {};
  for (const s of base) for (const n of new Set(s.niches || [s.niche])) counts[n] = (counts[n] || 0) + 1;
  const momentum = Object.fromEntries((ui.state?.niche_momentum || []).map((m) => [m.id, m.delta]));
  const ids = Object.keys(counts).sort((a, b) => (a === 'otros') - (b === 'otros') || counts[b] - counts[a]);
  const chip = (id, label, count, color) => {
    const delta = momentum[id];
    const arrow = delta >= 3 ? `<span class="trend-up" title="Más activo que de costumbre">↑</span>` : delta <= -3 ? `<span class="trend-down" title="Más flojo que de costumbre">↓</span>` : '';
    return `<button class="chip${ui.niche === id ? ' on' : ''}" style="--c:${color}" data-action="niche" data-niche="${esc(id)}">${id === 'all' ? '' : '<span class="dot"></span>'}${esc(label)} <span class="n">${count}</span>${arrow}</button>`;
  };
  return `<div class="chip-scroll niche-strip">${chip('all', 'Todas', base.length, 'var(--violet)')}${ids.map((id) => chip(id, nicheName(id), counts[id], nicheColor(id))).join('')}</div>`;
}

function storyRow(story) {
  const tags = [story.alert ? U.alertTag() : '', story.scope === 'mundo' ? U.scopeTag(story) : ''].join('');
  return `<div class="story-row" data-action="open-story" data-key="${esc(story.key)}" tabindex="0">
    ${U.pickButton(story.key)}
    <div style="min-width:0"><div class="sr-title">${esc(story.title)}${tags}</div>
      <div class="sr-why">${esc(U.whyLine(story))}</div>
      ${(story.members || []).length ? `<div class="sr-members">Incluye ${esc(story.members.slice(0, 4).map((m) => m.title).join(' · '))}</div>` : ''}</div>
    <div class="hide-sm">${U.nicheTag(story.niche)}</div>
    <div class="hide-md">${U.heatbar(story.heat)}</div>
    <div class="sr-num">${U.volume(story)}<span>${esc(story.volume ? 'búsquedas' : U.volumeLabel(story))}</span></div>
    <div class="hide-sm">${U.phase(story)}</div>
    <div class="hide-md">${U.ytLevel(story.youtube)}</div>
  </div>`;
}

function trendTab() {
  const list = filtered();
  const head = `<div class="list-head"><span></span><span>Historia</span><span class="hide-sm">Nicho</span><span class="hide-md">Calor</span><span class="r">Volumen</span><span class="hide-sm">Fase</span><span class="hide-md">YouTube</span></div>`;
  const rows = list.length ? list.map(storyRow).join('') : U.emptyState('search', 'Nada con estos filtros', 'Prueba con otro nicho o borra la búsqueda.');
  const scopes = [['all', 'Todo'], ['espana', 'España'], ['mundo', 'Mundo']]
    .map(([id, label]) => `<button class="${ui.scope === id ? 'on' : ''}" data-action="scope" data-scope="${id}">${label}</button>`).join('');
  return `<div class="toolbar"><div class="toolbar-left"><div class="seg">${scopes}</div></div>
      <div class="toolbar-right"><span class="muted small">Marca varias con ${icon('check')} para compararlas</span></div></div>
    ${nicheChips()}
    <div class="panel story-list rise">${head}${rows}</div>`;
}

function mediaTab() {
  const data = ui.state?.platforms?.news || {};
  const items = data.items || [];
  if (!items.length) return `<div class="panel">${U.emptyState('news', 'Sin titulares ahora mismo', 'Se volverá a intentar en la próxima actualización.')}</div>`;
  const inRadar = new Set(stories().flatMap((s) => (s.news || []).map((n) => n.title)));
  const labels = data.labels || {};
  const byId = Object.fromEntries(items.map((i) => [i.id, i]));
  const sections = Object.keys(labels).filter((s) => (data.sections?.[s] || []).length);
  const chips = [`<button class="chip${ui.mediaSection === 'fuera' ? ' on' : ''}" data-action="media-section" data-section="fuera">${icon('eye')}Fuera del radar</button>`]
    .concat(sections.map((s) => `<button class="chip${ui.mediaSection === s ? ' on' : ''}" data-action="media-section" data-section="${esc(s)}">${esc(labels[s])}</button>`)).join('');
  let list;
  if (ui.mediaSection === 'fuera') {
    list = items.filter((n) => !inRadar.has(n.title) && (n.coverage || 1) >= 2);
  } else {
    list = (data.sections?.[ui.mediaSection] || []).map((id) => byId[id]).filter(Boolean);
  }
  if (ui.search) list = list.filter((n) => norm(n.title).includes(norm(ui.search)));
  list = [...list].sort((a, b) => (b.coverage || 1) - (a.coverage || 1) || (b.published || 0) - (a.published || 0)).slice(0, 30);
  const rows = list.map((n) => `<div class="media-row" data-ext-url="${esc(n.url)}">
      <div style="min-width:0"><div class="m-title">${esc(n.title)}</div><div class="m-sub">${esc(n.source || '')} · ${esc(F.ago(n.published))}${inRadar.has(n.title) ? ' · ya en el radar' : ''}</div></div>
      <div class="m-side">${(n.coverage || 1) > 1 ? `<span class="tag">${n.coverage} medios</span>` : ''}</div></div>`).join('');
  const intro = ui.mediaSection === 'fuera' ? '<p class="muted small" style="margin:0 0 12px">Lo cuentan varios medios, pero aún no se busca ni se comenta: vigílalo, puede despegar.</p>' : '';
  return `<div class="chip-scroll niche-strip">${chips}</div>${intro}
    <div class="panel story-list rise">${rows || U.emptyState('news', 'Nada por aquí', 'Todo lo que cubren varios medios ya está en el radar.')}</div>`;
}

export function render() {
  const total = stories().length;
  const media = ui.state?.platforms?.news?.items?.length || 0;
  const sortSeg = Object.entries(SORTS).map(([id, label]) => `<button class="${ui.sort === id ? 'on' : ''}" data-action="sort" data-sort="${id}">${label}</button>`).join('');
  const html = `<div class="page-head">
      <div><div class="eyebrow">Todo lo que se mueve en España</div><h1 class="display">Noticias</h1>
        <p class="lede">Cada historia junta todo lo que forma parte de ella. Filtra por nicho, por ámbito o busca un tema.</p></div>
      <div class="toolbar-right">
        <label class="search-field">${icon('search')}<input class="input" id="news-search" type="search" placeholder="Buscar en noticias…" value="${esc(ui.search)}" autocomplete="off" spellcheck="false"></label>
        ${ui.newsTab === 'tendencia' ? `<div class="seg">${sortSeg}</div>` : ''}
      </div></div>
    <div class="tabs"><button class="${ui.newsTab === 'tendencia' ? 'on' : ''}" data-action="news-tab" data-tab="tendencia">En tendencia<span class="n">${total}</span></button>
      <button class="${ui.newsTab === 'medios' ? 'on' : ''}" data-action="news-tab" data-tab="medios">En los medios<span class="n">${media}</span></button></div>
    ${ui.newsTab === 'medios' ? mediaTab() : trendTab()}`;
  return {
    html,
    mount(root) {
      const input = root.querySelector('#news-search');
      if (!input) return;
      let timer = null;
      input.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(() => {
          ui.search = input.value.trim();
          const pos = input.selectionStart;
          rerender({ keepScroll: true, focus: '#news-search', caret: pos });
        }, 160);
      });
    },
  };
}

on('niche', (el) => { ui.niche = el.dataset.niche; rerender({ keepScroll: true }); });
on('scope', (el) => { ui.scope = el.dataset.scope; ui.niche = 'all'; rerender({ keepScroll: true }); });
on('sort', (el) => { ui.sort = el.dataset.sort; rerender({ keepScroll: true }); });
on('news-tab', (el) => { ui.newsTab = el.dataset.tab; rerender(); });
on('media-section', (el) => { ui.mediaSection = el.dataset.section; rerender({ keepScroll: true }); });
