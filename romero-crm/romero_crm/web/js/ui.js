// Piezas de interfaz reutilizables: etiquetas, anillos, barras y filas.
import { icon } from './icons.js';
import * as F from './format.js';
import { esc, nicheColor, nicheName, ui } from './core.js';

export const PHASE_ICON = { explosivo: 'zap', subiendo: 'trending', temprana: 'signal', pico: 'minus', enfriandose: 'trendingDown' };
export const YT_TEXT = { hueco: 'Hueco claro', moderado: 'Competencia media', saturado: 'Muy competido' };
export const KIND = {
  publicar: { label: 'Publicar', icon: 'upload' },
  grabar: { label: 'Grabar', icon: 'camera' },
  editar: { label: 'Editar', icon: 'scissors' },
  guion: { label: 'Guion', icon: 'pen' },
  idea: { label: 'Idea', icon: 'bulb' },
  otro: { label: 'Otro', icon: 'dot' },
};
export const PLATFORMS = {
  instagram: { label: 'Instagram', icon: 'instagram' },
  tiktok: { label: 'TikTok', icon: 'tiktok' },
  youtube: { label: 'YouTube', icon: 'youtube' },
};
export const SOURCES = {
  google: 'Google', x: 'X', wikipedia: 'Wikipedia', news: 'Medios', youtube: 'YouTube',
};

export function nicheTag(id) {
  return `<span class="tag niche" style="--c:${nicheColor(id)}"><span class="dot"></span>${esc(nicheName(id))}</span>`;
}

export function scopeTag(story) {
  return story.scope === 'mundo' ? `<span class="tag mundo">${icon('globe')}Mundo</span>` : '<span class="tag espana">España</span>';
}

export function alertTag() {
  return `<span class="tag alert">${icon('zap')}Excepcional</span>`;
}

export function phase(item) {
  return `<span class="phase ${esc(item.phase)}" title="${esc(item.phase_reason || '')}">${icon(PHASE_ICON[item.phase] || 'minus')}${esc(item.phase_label || '')}</span>`;
}

export function ytLevel(yt, long = false) {
  if (!yt || !yt.level) return '<span class="muted small">Sin medir</span>';
  const text = long ? (YT_TEXT[yt.level] || yt.label) : { hueco: 'Hueco', moderado: 'Media', saturado: 'Saturado' }[yt.level];
  return `<span class="yt ${esc(yt.level)}"><i></i>${esc(text)}</span>`;
}

export function heatbar(value) {
  const v = Math.max(2, Math.min(100, Number(value) || 0));
  return `<span class="heatbar" title="Calor: alcance, impulso, presencia en varias plataformas y frescura"><span class="bar"><i style="width:${v}%"></i></span><b>${esc(value)}</b></span>`;
}

export function ring(value, small = false) {
  const r = 26;
  const c = 2 * Math.PI * r;
  const v = Math.max(0, Math.min(100, Number(value) || 0));
  return `<span class="ring${small ? ' sm' : ''}" title="Potencial: el calor ajustado por la fase y el margen que le queda">
    <svg viewBox="0 0 62 62"><circle class="track" cx="31" cy="31" r="${r}" fill="none" stroke-width="5"/>
    <circle class="value" cx="31" cy="31" r="${r}" fill="none" stroke-width="5" stroke-linecap="round" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${c.toFixed(1)}" data-ring="${(c * (1 - v / 100)).toFixed(1)}"/></svg>
    <b data-count="${v}">0</b></span>`;
}

export function sourceDots(list) {
  return `<span class="src-dots" title="${esc((list || []).map((s) => SOURCES[s] || s).join(', '))}">${(list || []).map((s) => `<i class="${esc(s)}"></i>`).join('')}</span>`;
}

export function volume(story) {
  if (story.volume) return `${F.num(story.volume)}+`;
  if (story.wiki_views) return F.num(story.wiki_views);
  return '—';
}

export function volumeLabel(story) {
  if (story.volume) return story.trends > 1 ? `búsquedas · ${story.trends} tendencias` : 'búsquedas';
  if (story.wiki_views) return 'lecturas';
  return story.x_rank ? `nº ${story.x_rank} en X` : '';
}

export function margin(story) {
  if (story.remaining_hours === null || story.remaining_hours === undefined) return '—';
  if (story.remaining_hours <= 0.5) return 'Casi agotado';
  return `~${F.hours(story.remaining_hours)}`;
}

export function membersLine(story, limit = 3) {
  const names = (story.members || []).map((m) => m.title).slice(0, limit);
  if (!names.length) return '';
  const extra = (story.members || []).length - names.length;
  const list = names.map((n) => `<b>${esc(n)}</b>`);
  const joined = list.length > 1 ? `${list.slice(0, -1).join(', ')} y ${list[list.length - 1]}` : list[0];
  return `Incluye ${joined}${extra > 0 ? ` y ${extra} más` : ''}`;
}

export function whyLine(story) {
  if (story.synopsis?.length) return story.synopsis[0].text;
  if (story.context) return `${story.context.subject}: ${story.context.text}`;
  return story.phase_reason || '';
}

export function synopsisHtml(story, full = false) {
  const lines = story.synopsis || [];
  if (story.ai?.que_ha_pasado) {
    const first = lines[0];
    const meta = first ? [first.source, first.published ? F.ago(first.published) : ''].filter(Boolean).join(' · ') : '';
    return `<p class="what">${esc(story.ai.que_ha_pasado)}<span class="src">${icon('sparkles')} Resumen de Claude${meta ? ` · según ${esc(meta)}` : ''}</span></p>
      ${full && first ? `<p class="what second">${esc(first.text)}</p>` : ''}`;
  }
  if (!lines.length) {
    return `<p class="what muted">Sin titulares todavía: de momento es conversación en redes y búsquedas. ${esc(story.phase_reason || '')}</p>`;
  }
  return lines.slice(0, full ? 2 : 2).map((line, i) => {
    const meta = [line.source, line.published ? F.ago(line.published) : ''].filter(Boolean).join(' · ');
    return `<p class="what${i ? ' second' : ''}">${esc(line.text)}${meta && (i === 0 || full) ? `<span class="src">${esc(meta)}</span>` : ''}</p>`;
  }).join('');
}

export function contextHtml(story) {
  if (!story.context) return '';
  const text = story.context.text.charAt(0).toLowerCase() + story.context.text.slice(1);
  return `<p class="context"><b>${esc(story.context.subject)}:</b> ${esc(text)}</p>`;
}

export function angleHtml(story) {
  const angle = story.angle || {};
  const ai = story.ai;
  return `<p class="verdict ${esc(angle.urgency || 'hoy')}">${esc(angle.verdict || '')}</p>
    ${(angle.tips || []).length ? `<ul class="tips">${angle.tips.map((t) => `<li>${esc(t)}</li>`).join('')}</ul>` : ''}
    ${ai?.enfoque ? `<div class="ai-angle"><div class="kicker">${icon('sparkles')}Idea de Claude</div>${esc(ai.enfoque)}${ai.gancho ? `<div class="muted small" style="margin-top:4px">Gancho: «${esc(ai.gancho)}»</div>` : ''}</div>` : ''}`;
}

export function pickButton(key) {
  const on = ui.picks.includes(key);
  return `<button class="pick${on ? ' on' : ''}" data-action="pick" data-key="${esc(key)}" title="${on ? 'Quitar de la comparativa' : 'Añadir a la comparativa'}" aria-pressed="${on}">${icon('check')}</button>`;
}

export function compareButton(key) {
  const on = ui.picks.includes(key);
  return `<button class="icon-btn pick-btn${on ? ' on' : ''}" data-action="pick" data-key="${esc(key)}" title="${on ? 'Quitar de la comparativa' : 'Comparar con otras'}" aria-pressed="${on}">${icon('compare')}</button>`;
}

export function platformBadge(platform) {
  const info = PLATFORMS[platform];
  return info ? `<span class="plat-badge ${esc(platform)}" title="${esc(info.label)}">${icon(info.icon)}</span>` : `<span class="plat-badge">${icon('play')}</span>`;
}

export function kindIcon(kind) {
  const info = KIND[kind] || KIND.otro;
  return `<span class="kind-ico k-${esc(kind)}" title="${esc(info.label)}">${icon(info.icon)}</span>`;
}

export function platformIcons(list) {
  if (!list?.length) return '';
  return `<span class="plat">${list.map((p) => PLATFORMS[p] ? `<span title="${esc(PLATFORMS[p].label)}">${icon(PLATFORMS[p].icon)}</span>` : '').join('')}</span>`;
}

export function taskRow(item, opts = {}) {
  const info = KIND[item.kind] || KIND.otro;
  const sub = [opts.showDay ? F.cap(F.relDay(item.day)) : info.label, item.time || ''].filter(Boolean).join(' · ');
  return `<div class="task${item.done ? ' done' : ''}">
    <button class="tick${item.done ? ' on' : ''}" data-action="tick" data-id="${esc(item.id)}" aria-pressed="${item.done}" title="${item.done ? 'Marcar como pendiente' : 'Marcar como hecho'}">${icon('check')}</button>
    ${kindIcon(item.kind)}
    <div class="t-main" data-action="plan-edit" data-id="${esc(item.id)}">
      <div class="t-title">${opts.showKind ? `${esc(info.label)}: ` : ''}${esc(item.title)}</div>
      <div class="t-sub">${esc(sub)}${platformIcons(item.platforms)}${(item.links || []).length ? `<span>${icon('link')}</span>` : ''}</div>
    </div>
  </div>`;
}

export function emptyState(iconName, title, text = '', extra = '') {
  return `<div class="empty">${icon(iconName)}<h3>${esc(title)}</h3>${text ? `<p>${text}</p>` : ''}${extra}</div>`;
}

export function extLink(url, label, cls = '') {
  const safe = F.safeUrl(url);
  if (!safe) return label;
  return `<a href="${esc(safe)}" class="${cls}" data-ext="1" target="_blank" rel="noopener noreferrer">${label}</a>`;
}
