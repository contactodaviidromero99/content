const SVG = 'http://www.w3.org/2000/svg';
let tipEl = null;

export function setupTooltip(el) {
  tipEl = el;
}

function svgEl(name, attrs = {}, parent = null) {
  const node = document.createElementNS(SVG, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.appendChild(node);
  return node;
}

export function showTip(event, rows, title) {
  if (!tipEl) return;
  tipEl.replaceChildren();
  if (title) {
    const head = document.createElement('div');
    head.className = 'tt-label';
    head.textContent = title;
    tipEl.appendChild(head);
  }
  for (const row of rows) {
    const line = document.createElement('div');
    line.className = 'tt-row';
    if (row.key !== false) {
      const keyMark = document.createElement('i');
      if (row.color) keyMark.style.background = row.color;
      line.appendChild(keyMark);
    }
    const value = document.createElement('span');
    value.className = 'tt-value';
    value.textContent = row.value;
    line.appendChild(value);
    if (row.label) {
      const label = document.createElement('span');
      label.className = 'tt-label';
      label.textContent = row.label;
      line.appendChild(label);
    }
    tipEl.appendChild(line);
  }
  tipEl.hidden = false;
  moveTip(event);
}

export function moveTip(event) {
  if (!tipEl || tipEl.hidden) return;
  const pad = 14;
  const rect = tipEl.getBoundingClientRect();
  let x = event.clientX + pad;
  let y = event.clientY + pad;
  if (x + rect.width > window.innerWidth - 8) x = event.clientX - rect.width - pad;
  if (y + rect.height > window.innerHeight - 8) y = event.clientY - rect.height - pad;
  tipEl.style.left = `${Math.max(8, x)}px`;
  tipEl.style.top = `${Math.max(8, y)}px`;
}

export function hideTip() {
  if (tipEl) tipEl.hidden = true;
}

export function bindTip(el, rowsFn, titleFn) {
  el.addEventListener('pointerenter', (e) => showTip(e, rowsFn(), titleFn ? titleFn() : undefined));
  el.addEventListener('pointermove', moveTip);
  el.addEventListener('pointerleave', hideTip);
  el.addEventListener('focus', () => {
    const r = el.getBoundingClientRect();
    showTip({ clientX: r.right, clientY: r.top }, rowsFn(), titleFn ? titleFn() : undefined);
  });
  el.addEventListener('blur', hideTip);
}

function scaleY(values, height, padTop, padBottom, floorZero = true) {
  const max = Math.max(...values, 1e-9);
  const min = floorZero ? 0 : Math.min(...values);
  const span = max - min || 1;
  return (v) => padTop + (height - padTop - padBottom) * (1 - (v - min) / span);
}

function linePath(points) {
  return points.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join('');
}

export function sparkline(series, opts = {}) {
  const width = opts.width || 104;
  const height = opts.height || 30;
  const values = (series || []).map((v) => (Number.isFinite(v) ? v : 0));
  const wrap = document.createElement('div');
  wrap.className = 'chart';
  wrap.style.width = `${width}px`;
  if (values.length < 2 || values.every((v) => v === 0)) {
    wrap.className = 'spark-empty';
    wrap.textContent = '—';
    return wrap;
  }
  const svg = svgEl('svg', { width, height, viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': opts.ariaLabel || 'Evolución' }, wrap);
  const y = scaleY(values, height, 5, 3);
  const step = (width - 8) / (values.length - 1);
  const pts = values.map((v, i) => [4 + i * step, y(v)]);
  const area = `${linePath(pts)}L${pts[pts.length - 1][0]},${height - 1}L${pts[0][0]},${height - 1}Z`;
  svgEl('path', { d: area, fill: opts.color || 'var(--violet)', 'fill-opacity': '0.10', stroke: 'none' }, svg);
  svgEl('path', { d: linePath(pts), fill: 'none', stroke: opts.color || 'var(--violet)', 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, svg);
  const last = pts[pts.length - 1];
  svgEl('circle', { cx: last[0], cy: last[1], r: 4, fill: opts.color || 'var(--violet)', stroke: 'var(--bg)', 'stroke-width': 2 }, svg);

  const cross = svgEl('line', { y1: 0, y2: height, stroke: 'var(--line-2)', 'stroke-width': 1, visibility: 'hidden' }, svg);
  const dot = svgEl('circle', { r: 4, fill: opts.color || 'var(--violet)', stroke: 'var(--bg)', 'stroke-width': 2, visibility: 'hidden' }, svg);
  const hit = svgEl('rect', { x: 0, y: 0, width, height, fill: 'transparent' }, svg);
  hit.addEventListener('pointermove', (event) => {
    const box = svg.getBoundingClientRect();
    const i = Math.max(0, Math.min(values.length - 1, Math.round((event.clientX - box.left - 4) / step)));
    cross.setAttribute('x1', pts[i][0]);
    cross.setAttribute('x2', pts[i][0]);
    dot.setAttribute('cx', pts[i][0]);
    dot.setAttribute('cy', pts[i][1]);
    cross.setAttribute('visibility', 'visible');
    dot.setAttribute('visibility', 'visible');
    const info = opts.describe ? opts.describe(values[i], i, values.length) : { value: String(values[i]) };
    showTip(event, [{ value: info.value, label: info.label, color: opts.color }], info.title);
  });
  hit.addEventListener('pointerleave', () => {
    cross.setAttribute('visibility', 'hidden');
    dot.setAttribute('visibility', 'hidden');
    hideTip();
  });
  return wrap;
}

export function lineChart(container, series, opts = {}) {
  container.replaceChildren();
  const values = (series || []).map((v) => (Number.isFinite(v) ? v : 0));
  if (values.length < 2) {
    container.innerHTML = '<div class="empty small">Sin serie temporal disponible.</div>';
    return;
  }
  const width = Math.max(280, container.clientWidth || 480);
  const height = opts.height || 190;
  const max = Math.max(...values, 1);
  const ticks = opts.ticks || niceTicks(max, 3);
  const tickLabels = ticks.map((t) => (opts.yFormat ? opts.yFormat(t) : String(t)));
  const padL = Math.max(34, Math.ceil(Math.max(...tickLabels.map((l) => String(l).length)) * 6.6) + 12);
  const padR = 10, padT = 10, padB = 24;
  const svg = svgEl('svg', { width, height, viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': opts.ariaLabel || 'Evolución temporal' }, container);
  const top = Math.max(...ticks) || max;
  const y = (v) => padT + (height - padT - padB) * (1 - v / top);
  const step = (width - padL - padR) / (values.length - 1);
  const x = (i) => padL + i * step;
  ticks.forEach((t, index) => {
    svgEl('line', { x1: padL, x2: width - padR, y1: y(t), y2: y(t), class: t === 0 ? 'base-line' : 'grid-line' }, svg);
    const label = svgEl('text', { x: padL - 6, y: y(t) + 3.5, 'text-anchor': 'end', class: 'axis-label' }, svg);
    label.textContent = tickLabels[index];
  });
  const labelEvery = Math.max(1, Math.round(values.length / 5));
  for (let i = 0; i < values.length; i += labelEvery) {
    const anchor = i === 0 ? 'start' : x(i) > width - padR - 28 ? 'end' : 'middle';
    const label = svgEl('text', { x: x(i), y: height - 6, 'text-anchor': anchor, class: 'axis-label' }, svg);
    label.textContent = opts.xLabel ? opts.xLabel(i, values.length) : String(i);
  }
  const pts = values.map((v, i) => [x(i), y(v)]);
  const area = `${linePath(pts)}L${pts[pts.length - 1][0]},${y(0)}L${pts[0][0]},${y(0)}Z`;
  svgEl('path', { d: area, fill: 'var(--violet)', 'fill-opacity': '0.10' }, svg);
  svgEl('path', { d: linePath(pts), fill: 'none', stroke: 'var(--violet)', 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, svg);
  const last = pts[pts.length - 1];
  svgEl('circle', { cx: last[0], cy: last[1], r: 4, fill: 'var(--violet)', stroke: 'var(--bg)', 'stroke-width': 2 }, svg);
  const cross = svgEl('line', { y1: padT, y2: height - padB, stroke: 'var(--line-2)', 'stroke-width': 1, visibility: 'hidden' }, svg);
  const dot = svgEl('circle', { r: 4.5, fill: 'var(--violet)', stroke: 'var(--bg)', 'stroke-width': 2, visibility: 'hidden' }, svg);
  const hit = svgEl('rect', { x: padL, y: 0, width: width - padL - padR, height, fill: 'transparent' }, svg);
  hit.addEventListener('pointermove', (event) => {
    const box = svg.getBoundingClientRect();
    const scale = width / box.width;
    const i = Math.max(0, Math.min(values.length - 1, Math.round(((event.clientX - box.left) * scale - padL) / step)));
    cross.setAttribute('x1', pts[i][0]);
    cross.setAttribute('x2', pts[i][0]);
    dot.setAttribute('cx', pts[i][0]);
    dot.setAttribute('cy', pts[i][1]);
    cross.setAttribute('visibility', 'visible');
    dot.setAttribute('visibility', 'visible');
    const info = opts.describe ? opts.describe(values[i], i, values.length) : { value: String(values[i]) };
    showTip(event, [{ value: info.value, label: info.label }], info.title);
  });
  hit.addEventListener('pointerleave', () => {
    cross.setAttribute('visibility', 'hidden');
    dot.setAttribute('visibility', 'hidden');
    hideTip();
  });
}

function niceTicks(max, count) {
  if (max <= 0) return [0, 1];
  const raw = max / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const step = (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10) * mag;
  const ticks = [];
  for (let v = 0; v <= max + step * 0.999; v += step) ticks.push(Math.round(v * 1000) / 1000);
  return ticks;
}

export function multiLine(container, seriesList, opts = {}) {
  container.replaceChildren();
  const usable = seriesList.filter((s) => (s.values || []).filter((v) => v > 0).length >= 2);
  if (!usable.length) {
    container.innerHTML = '<div class="empty small">Todavía no hay curvas suficientes para comparar.</div>';
    return;
  }
  const width = Math.max(300, container.clientWidth || 600);
  const height = opts.height || 170;
  const padL = 10, padR = 10, padT = 12, padB = 12;
  const svg = svgEl('svg', { width, height, viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': 'Evolución comparada' }, container);
  [0.25, 0.5, 0.75].forEach((f) => svgEl('line', { x1: padL, x2: width - padR, y1: padT + (height - padT - padB) * f, y2: padT + (height - padT - padB) * f, class: 'grid-line' }, svg));
  for (const series of usable) {
    const values = series.values.map((v) => (Number.isFinite(v) ? v : 0));
    const max = Math.max(...values, 1e-9);
    const step = (width - padL - padR) / Math.max(values.length - 1, 1);
    const pts = values.map((v, i) => [padL + i * step, padT + (height - padT - padB) * (1 - v / max)]);
    svgEl('path', { d: linePath(pts), fill: 'none', stroke: series.color, 'stroke-width': 2.5, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, svg);
    const last = pts[pts.length - 1];
    svgEl('circle', { cx: last[0], cy: last[1], r: 4, fill: series.color, stroke: 'var(--bg)', 'stroke-width': 2 }, svg);
  }
  const legend = document.createElement('div');
  legend.className = 'legend';
  legend.style.marginTop = '8px';
  legend.innerHTML = usable.map((s) => `<span style="--k:${s.color}"><i></i>${s.label.replace(/[&<>"']/g, '')}</span>`).join('');
  container.appendChild(legend);
}
