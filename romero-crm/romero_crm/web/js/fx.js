// Efectos: la luz del fondo sigue al cursor con suavidad, los bordes de las tarjetas se iluminan
// donde está el ratón, la navegación desliza su indicador y los números cuentan al aparecer.

const fxLayer = document.getElementById('fx');
const target = { x: -2000, y: -2000 };
const current = { x: -2000, y: -2000 };
let frame = null;
let enabled = true;

function tick() {
  current.x += (target.x - current.x) * 0.14;
  current.y += (target.y - current.y) * 0.14;
  fxLayer.style.setProperty('--mx', `${current.x.toFixed(1)}px`);
  fxLayer.style.setProperty('--my', `${current.y.toFixed(1)}px`);
  if (Math.abs(target.x - current.x) + Math.abs(target.y - current.y) > 0.6) frame = requestAnimationFrame(tick);
  else frame = null;
}

export function setupFx() {
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  window.addEventListener('pointermove', (event) => {
    if (!enabled || reduced.matches) return;
    if (current.x < -1000) {
      current.x = event.clientX;
      current.y = event.clientY;
    }
    target.x = event.clientX;
    target.y = event.clientY;
    if (!frame) frame = requestAnimationFrame(tick);
    const card = event.target.closest ? event.target.closest('.glow') : null;
    if (card) {
      const box = card.getBoundingClientRect();
      card.style.setProperty('--gx', `${event.clientX - box.left}px`);
      card.style.setProperty('--gy', `${event.clientY - box.top}px`);
    }
  }, { passive: true });
  document.addEventListener('pointerleave', () => {
    target.x = -2000;
    target.y = -2000;
    if (!frame) frame = requestAnimationFrame(tick);
  });
}

export function setEffects(on) {
  enabled = on;
  document.documentElement.classList.toggle('no-fx', !on);
}

export function moveNavInk() {
  const nav = document.getElementById('nav');
  const ink = document.getElementById('nav-ink');
  const active = nav?.querySelector('a.active');
  if (!ink) return;
  if (!active) {
    ink.style.opacity = '0';
    return;
  }
  ink.style.opacity = '1';
  ink.style.width = `${active.offsetWidth}px`;
  ink.style.transform = `translateX(${active.offsetLeft}px)`;
}

export function animateIn(root) {
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  root.querySelectorAll('[data-ring]').forEach((circle) => {
    requestAnimationFrame(() => requestAnimationFrame(() => { circle.style.strokeDashoffset = circle.dataset.ring; }));
  });
  root.querySelectorAll('[data-count]').forEach((el) => {
    const end = Number(el.dataset.count) || 0;
    if (reduced || !enabled) {
      el.textContent = String(end);
      return;
    }
    const start = performance.now();
    const duration = 900;
    const step = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - (1 - t) ** 3;
      el.textContent = String(Math.round(end * eased));
      if (t < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });
}
