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
  svgEl('path', { d: area, fill: opts.color || 'var(--accent)', 'fill-opacity': '0.10', stroke: 'none' }, svg);
  svgEl('path', { d: linePath(pts), fill: 'none', stroke: opts.color || 'var(--accent)', 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, svg);
  const last = pts[pts.length - 1];
  svgEl('circle', { cx: last[0], cy: last[1], r: 4, fill: opts.color || 'var(--accent)', stroke: 'var(--surface)', 'stroke-width': 2 }, svg);

  const cross = svgEl('line', { y1: 0, y2: height, stroke: 'var(--axis)', 'stroke-width': 1, visibility: 'hidden' }, svg);
  const dot = svgEl('circle', { r: 4, fill: opts.color || 'var(--accent)', stroke: 'var(--surface)', 'stroke-width': 2, visibility: 'hidden' }, svg);
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
  const padL = 34, padR = 10, padT = 10, padB = 24;
  const svg = svgEl('svg', { width, height, viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': opts.ariaLabel || 'Evolución temporal' }, container);
  const max = Math.max(...values, 1);
  const ticks = niceTicks(max, 3);
  const top = ticks[ticks.length - 1] || max;
  const y = (v) => padT + (height - padT - padB) * (1 - v / top);
  const step = (width - padL - padR) / (values.length - 1);
  const x = (i) => padL + i * step;
  for (const t of ticks) {
    svgEl('line', { x1: padL, x2: width - padR, y1: y(t), y2: y(t), class: t === 0 ? 'base-line' : 'grid-line' }, svg);
    const label = svgEl('text', { x: padL - 6, y: y(t) + 3.5, 'text-anchor': 'end', class: 'axis-label' }, svg);
    label.textContent = opts.yFormat ? opts.yFormat(t) : String(t);
  }
  const labelEvery = Math.max(1, Math.round(values.length / 5));
  for (let i = 0; i < values.length; i += labelEvery) {
    const anchor = i === 0 ? 'start' : x(i) > width - padR - 28 ? 'end' : 'middle';
    const label = svgEl('text', { x: x(i), y: height - 6, 'text-anchor': anchor, class: 'axis-label' }, svg);
    label.textContent = opts.xLabel ? opts.xLabel(i, values.length) : String(i);
  }
  const pts = values.map((v, i) => [x(i), y(v)]);
  const area = `${linePath(pts)}L${pts[pts.length - 1][0]},${y(0)}L${pts[0][0]},${y(0)}Z`;
  svgEl('path', { d: area, fill: 'var(--accent)', 'fill-opacity': '0.10' }, svg);
  svgEl('path', { d: linePath(pts), fill: 'none', stroke: 'var(--accent)', 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, svg);
  const last = pts[pts.length - 1];
  svgEl('circle', { cx: last[0], cy: last[1], r: 4, fill: 'var(--accent)', stroke: 'var(--surface)', 'stroke-width': 2 }, svg);
  const cross = svgEl('line', { y1: padT, y2: height - padB, stroke: 'var(--axis)', 'stroke-width': 1, visibility: 'hidden' }, svg);
  const dot = svgEl('circle', { r: 4.5, fill: 'var(--accent)', stroke: 'var(--surface)', 'stroke-width': 2, visibility: 'hidden' }, svg);
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

function roundedColumn(x, yTop, w, base, r) {
  const h = base - yTop;
  if (h <= 0) return '';
  const rr = Math.min(r, h, w / 2);
  return `M${x},${base}V${yTop + rr}Q${x},${yTop} ${x + rr},${yTop}H${x + w - rr}Q${x + w},${yTop} ${x + w},${yTop + rr}V${base}Z`;
}

export function columns(container, rows, opts = {}) {
  container.replaceChildren();
  if (!rows.length) {
    container.innerHTML = '<div class="empty small">Aún no hay datos suficientes.</div>';
    return;
  }
  const width = Math.max(260, container.clientWidth || 480);
  const height = opts.height || 170;
  const padL = 30, padR = 6, padT = 14, padB = 24;
  const svg = svgEl('svg', { width, height, viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': opts.ariaLabel || 'Gráfico de columnas' }, container);
  const max = Math.max(...rows.map((r) => r.value), 1);
  const ticks = niceTicks(max, 3);
  const top = ticks[ticks.length - 1];
  const y = (v) => padT + (height - padT - padB) * (1 - v / top);
  for (const t of ticks) {
    svgEl('line', { x1: padL, x2: width - padR, y1: y(t), y2: y(t), class: t === 0 ? 'base-line' : 'grid-line' }, svg);
    const label = svgEl('text', { x: padL - 6, y: y(t) + 3.5, 'text-anchor': 'end', class: 'axis-label' }, svg);
    label.textContent = opts.yFormat ? opts.yFormat(t) : String(t);
  }
  const band = (width - padL - padR) / rows.length;
  const w = Math.min(24, band * 0.62);
  const labelEvery = opts.labelEvery || (rows.length > 12 ? 3 : 1);
  rows.forEach((row, i) => {
    const cx = padL + band * i + band / 2;
    const d = roundedColumn(cx - w / 2, y(row.value), w, y(0), 4);
    const fill = opts.highlight && opts.highlight(row, i) ? 'var(--accent)' : (opts.dim ? 'var(--seq-3)' : 'var(--accent)');
    if (d) svgEl('path', { d, fill }, svg);
    if (i % labelEvery === 0) {
      const label = svgEl('text', { x: cx, y: height - 6, 'text-anchor': 'middle', class: 'axis-label' }, svg);
      label.textContent = row.label;
    }
    const hit = svgEl('rect', { x: padL + band * i, y: padT, width: band, height: height - padT - padB, fill: 'transparent', tabindex: 0 }, svg);
    bindTip(hit, () => [{ value: row.display ?? String(row.value), label: row.tipLabel || '' }], () => row.tip || row.label);
    if (opts.onClick) {
      hit.style.cursor = 'pointer';
      hit.addEventListener('click', () => opts.onClick(row, i));
    }
  });
}

export function barList(container, rows, opts = {}) {
  container.replaceChildren();
  if (!rows.length) {
    container.innerHTML = '<div class="empty small">Sin datos.</div>';
    return;
  }
  const max = Math.max(...rows.map((r) => Math.abs(r.value)), 1e-9);
  const wrap = document.createElement('div');
  wrap.className = 'bars';
  for (const row of rows) {
    const line = document.createElement('div');
    line.className = 'bar-row' + (opts.onClick ? ' clickable' : '');
    line.tabIndex = opts.onClick ? 0 : -1;
    const label = document.createElement('div');
    label.className = 'bar-label';
    label.textContent = row.label;
    const track = document.createElement('div');
    track.className = 'bar-track';
    const fill = document.createElement('div');
    fill.className = 'bar-fill';
    fill.style.width = `${Math.max(1.5, (Math.abs(row.value) / max) * 100)}%`;
    track.appendChild(fill);
    const value = document.createElement('div');
    value.className = 'bar-value';
    value.textContent = row.display ?? String(row.value);
    line.append(label, track, value);
    bindTip(line, () => [{ value: row.display ?? String(row.value), label: row.tipLabel || '' }], () => row.tip || row.label);
    if (opts.onClick) {
      line.addEventListener('click', () => opts.onClick(row));
      line.addEventListener('keydown', (e) => { if (e.key === 'Enter') opts.onClick(row); });
    }
    wrap.appendChild(line);
  }
  container.appendChild(wrap);
}

export function divergingBars(container, rows, opts = {}) {
  container.replaceChildren();
  if (!rows.length) {
    container.innerHTML = `<div class="empty small">${opts.emptyText || 'Aún no hay datos suficientes.'}</div>`;
    return;
  }
  const max = Math.max(...rows.map((r) => Math.abs(r.value)), 1e-9);
  const wrap = document.createElement('div');
  wrap.className = 'dbars';
  for (const row of rows) {
    const line = document.createElement('div');
    line.className = 'drow';
    line.tabIndex = 0;
    const label = document.createElement('div');
    label.className = 'bar-label';
    label.textContent = row.label;
    const track = document.createElement('div');
    track.className = 'dtrack';
    const fill = document.createElement('div');
    fill.className = `dfill ${row.value >= 0 ? 'pos' : 'neg'}`;
    fill.style.width = `${Math.max(1, (Math.abs(row.value) / max) * 50)}%`;
    track.appendChild(fill);
    const value = document.createElement('div');
    value.className = 'bar-value';
    value.textContent = row.display;
    line.append(label, track, value);
    bindTip(line, () => [{ value: row.display, label: row.tipLabel || '', color: row.value >= 0 ? 'var(--div-pos)' : 'var(--div-neg)' }], () => row.label);
    wrap.appendChild(line);
  }
  container.appendChild(wrap);
}

export function heatmap(container, data, opts = {}) {
  container.replaceChildren();
  if (!data.rows.length) {
    container.innerHTML = '<div class="empty small">Aún no hay historial suficiente.</div>';
    return;
  }
  const max = Math.max(...data.values.flat(), 1);
  const grid = document.createElement('div');
  grid.className = 'heatmap';
  grid.style.gridTemplateColumns = `150px repeat(${data.cols.length}, minmax(28px, 1fr))`;
  grid.appendChild(document.createElement('div'));
  for (const col of data.cols) {
    const head = document.createElement('div');
    head.className = 'hm-head';
    head.textContent = col;
    grid.appendChild(head);
  }
  data.rows.forEach((row, r) => {
    const label = document.createElement('div');
    label.className = 'hm-label';
    label.textContent = row.name;
    grid.appendChild(label);
    data.values[r].forEach((value, c) => {
      const cell = document.createElement('div');
      const level = value <= 0 ? 0 : Math.min(7, 1 + Math.floor((value / max) * 6.999));
      cell.className = `hm-cell s${level}`;
      cell.tabIndex = 0;
      if (value > 0) cell.textContent = String(value);
      bindTip(cell, () => [{ value: `${value} tendencia${value === 1 ? '' : 's'}`, label: data.cols[c], key: false }], () => row.name);
      if (opts.onClick) cell.addEventListener('click', () => opts.onClick(row, c));
      grid.appendChild(cell);
    });
  });
  container.appendChild(grid);
  const scale = document.createElement('div');
  scale.className = 'scale mt-8';
  scale.innerHTML = '<span>Menos</span>' + [1, 2, 3, 4, 5, 6, 7].map((s) => `<i class="hm-cell s${s}" style="height:10px"></i>`).join('') + '<span>Más</span>';
  container.appendChild(scale);
}

export function tableToggle(button, chartEl, tableEl) {
  button.addEventListener('click', () => {
    const showTable = tableEl.hidden;
    tableEl.hidden = !showTable;
    chartEl.hidden = showTable;
    button.textContent = showTable ? 'Ver gráfico' : 'Ver tabla';
  });
}
