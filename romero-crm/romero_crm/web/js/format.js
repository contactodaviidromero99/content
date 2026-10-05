const compact = new Intl.NumberFormat('es-ES', { notation: 'compact', maximumFractionDigits: 1 });
const plain = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 0 });
const relative = new Intl.RelativeTimeFormat('es', { numeric: 'auto', style: 'short' });
const dayFmt = new Intl.DateTimeFormat('es-ES', { weekday: 'short', day: 'numeric', month: 'short' });
const longDay = new Intl.DateTimeFormat('es-ES', { weekday: 'long', day: 'numeric', month: 'long' });
const timeFmt = new Intl.DateTimeFormat('es-ES', { hour: '2-digit', minute: '2-digit' });

export function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

export function safeUrl(url) {
  return typeof url === 'string' && /^https?:\/\//i.test(url) ? url : '';
}

export function num(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return Math.abs(value) >= 10000 ? compact.format(value) : plain.format(value);
}

export function full(value) {
  if (value === null || value === undefined) return '—';
  return plain.format(value);
}

export function pct(value, signed = true) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  const sign = signed && value > 0 ? '+' : value < 0 ? '−' : '';
  return `${sign}${plain.format(Math.abs(value))} %`;
}

export function ago(ts) {
  if (!ts) return '—';
  const seconds = Math.round(ts - Date.now() / 1000);
  const abs = Math.abs(seconds);
  if (abs < 60) return 'ahora';
  if (abs < 3600) return relative.format(Math.round(seconds / 60), 'minute');
  if (abs < 86400) return relative.format(Math.round(seconds / 3600), 'hour');
  return relative.format(Math.round(seconds / 86400), 'day');
}

export function hours(value) {
  if (value === null || value === undefined) return '—';
  if (value < 1) return `${Math.max(1, Math.round(value * 60))} min`;
  if (value < 48) return `${value < 10 ? value.toFixed(1).replace('.', ',').replace(',0', '') : Math.round(value)} h`;
  return `${Math.round(value / 24)} días`;
}

export function day(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  return dayFmt.format(new Date(y, m - 1, d));
}

export function dayShort(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  const weekday = new Intl.DateTimeFormat('es-ES', { weekday: 'short' }).format(new Date(y, m - 1, d)).replace('.', '');
  return `${weekday} ${d}`;
}

export function longDate(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  const text = longDay.format(new Date(y, m - 1, d));
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function clock(ts) {
  return ts ? timeFmt.format(new Date(ts * 1000)) : '—';
}

export function daysUntil(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  const target = new Date(y, m - 1, d);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.round((target - today) / 86400000);
  if (diff === 0) return 'Hoy';
  if (diff === 1) return 'Mañana';
  return `En ${diff} días`;
}
