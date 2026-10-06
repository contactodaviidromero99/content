// Ajustes: tu nombre, apariencia, fuentes, conexiones con tus redes y el estado de todo.
import { icon } from '../icons.js';
import * as F from '../format.js';
import { $, DESKTOP, copyText, esc, on, post, rerender, toast, ui } from '../core.js';
import * as U from '../ui.js';

const SOURCE_LIST = [
  ['google', 'Google Trends', 'Lo que se busca'],
  ['x', 'X (Twitter)', 'Lo que se comenta'],
  ['news', 'Medios', 'Lo que se publica'],
  ['wikipedia', 'Wikipedia', 'Lo que se quiere entender'],
  ['youtube', 'YouTube', 'Cuánta competencia hay'],
];

function connState(id) {
  const st = ui.state?.connections?.[id];
  if (!st) return '<span class="state state-off">Sin conectar</span>';
  if (!st.ok) return `<span class="state state-err" title="${esc(st.error || '')}">Con errores</span>`;
  return `<span class="state state-ok">${st.count} vídeos · ${esc(F.ago(st.checked_at))}</span>`;
}

function connectionsPanel() {
  const s = ui.settings || {};
  const ig = ui.state?.connections?.instagram;
  const yt = ui.state?.connections?.youtube;
  return `<section class="panel"><div class="panel-head"><div><h3>Tus redes</h3><p>Para ver en el calendario lo que publicas y cómo funciona.</p></div>
      <button class="btn sm" data-action="sync-now">${icon('refresh')}Sincronizar</button></div>
    <div class="panel-body" style="padding:6px 0 4px">
      <div class="conn">
        <div class="conn-head"><span class="ico">${icon('youtube')}</span><div><b>YouTube</b><div class="muted small">Tu canal público. Sin claves ni contraseñas.</div></div>${s.youtube_channel ? connState('youtube') : ''}</div>
        <div class="conn-body"><div class="row"><input class="input" id="yt-channel" placeholder="@tucanal o el enlace de tu canal" value="${esc(s.youtube_channel || '')}" autocomplete="off" spellcheck="false">
          <button class="btn sm" data-action="save-channel">Guardar</button></div>
          ${yt && !yt.ok ? `<div class="err-text">${esc(yt.error || '')}</div>` : ''}</div>
      </div>
      <div class="conn">
        <div class="conn-head"><span class="ico">${icon('instagram')}</span><div><b>Instagram</b><div class="muted small">Con la API oficial de Instagram. Gratis.</div></div>${s.instagram_token_set ? connState('instagram') : ''}</div>
        <div class="conn-body">
          ${s.instagram_token_set
            ? `<div class="row"><span class="code" style="flex:1">Conectado · token ${esc(s.instagram_token_hint || '')}</span><button class="btn sm danger" data-action="clear-ig">Desconectar</button></div>`
            : `<div class="row"><input class="input" id="ig-token" type="password" placeholder="Pega aquí tu token de Instagram" autocomplete="off" spellcheck="false"><button class="btn sm" data-action="save-ig">Conectar</button></div>`}
          ${ig && !ig.ok ? `<div class="err-text">${esc(ig.error || '')}</div>` : ''}
          <details><summary class="link" style="cursor:pointer">Cómo conseguir el token (unos 10 minutos, una sola vez)</summary>
            <ol class="guide">
              <li>Tu cuenta de Instagram tiene que ser profesional (creador o empresa). Si usas Metricool, ya lo es.</li>
              <li>Entra en <b>developers.facebook.com</b> con tu cuenta de Facebook, pulsa <b>Crear app</b> y elige el caso de uso de <b>Instagram</b> (gestionar contenido y mensajes).</li>
              <li>En <b>Roles de la app</b>, añade tu cuenta de Instagram como <b>evaluador de Instagram</b> y acepta la invitación desde Instagram: <i>Configuración → Apps y sitios web → Invitaciones de evaluador</i>.</li>
              <li>Vuelve a la app, entra en la configuración de la <b>API con inicio de sesión de Instagram</b> y, en <b>Generar identificadores de acceso</b>, añade tu cuenta y copia el token.</li>
              <li>Pégalo arriba. Dura 60 días, pero Romero lo renueva solo mientras lo uses.</li>
            </ol></details>
        </div>
      </div>
      <div class="conn">
        <div class="conn-head"><span class="ico">${icon('tiktok')}</span><div><b>TikTok</b><div class="muted small">Pegando el enlace de cada vídeo.</div></div></div>
        <div class="conn-body"><p class="note" style="margin:0">TikTok no deja leer la lista de vídeos de una cuenta sin una aplicación aprobada por TikTok. Cuando publiques, abre la tarea en el calendario y pega el enlace: el título, la miniatura y, si TikTok lo muestra, las visualizaciones se rellenan solos.</p></div>
      </div>
    </div></section>`;
}

function sourcesTable() {
  const statuses = ui.state?.sources || {};
  const rows = ['google', 'google_week', 'x', 'news', 'wikipedia', 'youtube', 'efemerides'].map((id) => {
    const st = statuses[id] || {};
    const [cls, text] = st.enabled === false ? ['state-off', 'Desactivada'] : st.stale ? ['state-warn', 'Datos antiguos'] : st.ok ? ['state-ok', 'Funciona'] : st.fetched_at ? ['state-err', 'Con errores'] : ['state-off', 'Pendiente'];
    return `<tr><td>${esc(st.label || id)}</td><td class="${cls}">${text}</td><td class="num">${st.count ?? 0}</td><td>${esc(F.ago(st.fetched_at))}</td><td class="muted">${esc(st.error || '')}</td></tr>`;
  }).join('');
  return `<section class="panel"><div class="panel-head"><div><h3>Estado de las fuentes</h3><p>Si algo falla, copia el informe y pégaselo a Claude.</p></div>
      <div class="chip-row"><button class="btn sm" data-action="copy-report">${icon('copy')}Copiar informe</button><button class="btn sm" data-action="refresh">${icon('refresh')}Actualizar</button></div></div>
    <div class="panel-body"><table class="status-table"><thead><tr><th>Fuente</th><th>Estado</th><th class="num">Datos</th><th>Última vez</th><th>Detalle</th></tr></thead><tbody>${rows}</tbody></table></div></section>`;
}

function aiState() {
  const st = ui.state?.ai || {};
  if (!st.enabled) return '';
  if (st.available === false) return '<div class="err-text">Falta el componente de Claude: vuelve a ejecutar el instalador.</div>';
  if (st.working) return '<div class="small state-warn">Pidiendo ideas a Claude…</div>';
  if (st.ok === false) return `<div class="err-text">${esc(st.error || 'Error')}</div>`;
  if (st.ok) return `<div class="small state-ok">Funcionando · última vez ${esc(F.ago(st.at))}</div>`;
  return '<div class="small muted">Se usará en la próxima actualización.</div>';
}

export function aiPanel() {
  const s = ui.settings || {};
  return `<section class="panel"><div class="panel-head"><div><h3>Ideas con Claude <span class="tag" style="margin-left:6px">Opcional</span></h3>
      <p>Con una clave de la API de Claude, cada historia de la portada trae además una sinopsis y un enfoque de vídeo escritos por Claude.</p></div></div>
    <div class="panel-body"><div class="conn-body" style="margin:0">
      ${s.ai_key_set
        ? `<div class="row"><span class="code" style="flex:1">Clave guardada ${esc(s.ai_key_hint || '')}</span><button class="btn sm danger" data-action="clear-ai">Quitar</button></div>`
        : `<div class="row"><input class="input" id="ai-key" type="password" placeholder="sk-ant-…" autocomplete="off" spellcheck="false"><button class="btn sm" data-action="save-ai">Guardar</button></div>`}
      ${aiState()}
      <p class="note" style="margin:0">Se consigue en <b>console.anthropic.com</b> (pago por uso: cada historia nueva cuesta unos céntimos y cada una se pide una sola vez). Usa Claude Opus 5.5. Sin clave, Romero funciona igual con su enfoque basado en datos.</p>
    </div></div></section>`;
}

export function render() {
  const s = ui.settings || {};
  const themeSeg = [['system', 'Automático'], ['light', 'Claro'], ['dark', 'Oscuro']]
    .map(([v, l]) => `<button class="${(s.theme || 'system') === v ? 'on' : ''}" data-action="set-theme" data-theme="${v}">${l}</button>`).join('');
  const sources = SOURCE_LIST.map(([id, label, sub]) => `<div class="setting"><div><b>${esc(label)}</b><p>${esc(sub)}</p></div>
    <label class="switch"><input type="checkbox" data-action-change="toggle-source" data-source="${id}" ${s.sources?.[id] !== false ? 'checked' : ''}><span class="track"></span></label></div>`).join('');
  const html = `<div class="page-head"><div><div class="eyebrow">Ajustes</div><h1 class="display">Tu <em>Romero</em></h1>
      <p class="lede">Todo se guarda en tu ordenador. Nada se sube a ningún sitio.</p></div></div>
    <div class="settings-grid">
      <div class="settings-col">
        <section class="panel"><div class="panel-head"><div><h3>Preferencias</h3></div></div><div class="panel-body" style="padding:6px 0 4px">
          <div class="setting"><div><b>Tu nombre</b><p>Para saludarte en la portada.</p></div>
            <input class="input" id="set-name" maxlength="40" placeholder="Por ejemplo, David" value="${esc(s.name || '')}" style="width:220px"></div>
          <div class="setting"><div><b>Apariencia</b><p>Automático sigue el modo claro u oscuro de tu Mac.</p></div><div class="seg">${themeSeg}</div></div>
          <div class="setting"><div><b>Efectos visuales</b><p>La luz que sigue al cursor, los brillos y las animaciones.</p></div>
            <label class="switch"><input type="checkbox" data-action-change="toggle-effects" ${s.effects !== false ? 'checked' : ''}><span class="track"></span></label></div>
          <div class="setting"><div><b>Actualizar cada</b><p>Mientras el programa esté abierto.</p></div>
            <select class="select" data-action-change="set-refresh">${[10, 15, 30, 60, 120].map((m) => `<option value="${m}" ${s.refresh_minutes === m ? 'selected' : ''}>${m} minutos</option>`).join('')}</select></div>
          <div class="setting"><div><b>Historias medidas en YouTube</b><p>Cuántas historias de la portada (y siguientes) se comprueban en YouTube en cada actualización.</p></div>
            <select class="select" data-action-change="set-youtube">${[0, 5, 8, 12, 16].map((m) => `<option value="${m}" ${s.youtube_topics === m ? 'selected' : ''}>${m === 0 ? 'Ninguna' : `${m} historias`}</option>`).join('')}</select></div>
          <div class="setting"><div><b>Ocultar búsquedas utilitarias</b><p>Loterías, el tiempo, horarios… Suben mucho pero no sirven para contenido.</p></div>
            <label class="switch"><input type="checkbox" data-action-change="toggle-utility" ${s.hide_utility !== false ? 'checked' : ''}><span class="track"></span></label></div>
        </div></section>
        <section class="panel"><div class="panel-head"><div><h3>Fuentes</h3><p>Cuantas más, mejor. Desactiva alguna solo si da problemas.</p></div></div>
          <div class="panel-body" style="padding:6px 0 4px">${sources}</div></section>
        ${sourcesTable()}
      </div>
      <div class="settings-col">
        ${connectionsPanel()}
        ${aiPanel()}
        <section class="panel"><div class="panel-head"><div><h3>Tus datos</h3><p>Historial, tareas y ajustes, en tu Mac.</p></div></div>
          <div class="panel-body"><div class="code">${esc(s.data_dir || '')}</div>
            <div class="chip-row" style="margin-top:12px"><button class="btn sm danger" data-action="clear-history">${icon('trash')}Borrar historial de tendencias</button></div>
            <p class="note">Borra las tendencias guardadas, no tus tareas del calendario.</p></div></section>
        <section class="panel"><div class="panel-body note">${esc(ui.state?.app?.name || 'Romero Xandre CRM')} ${esc(ui.state?.app?.version || '')}. Fuentes públicas: Google Trends, X (getdaytrends y trends24), Google News, Wikimedia y búsquedas de YouTube. Instagram y TikTok no publican sus tendencias; por eso tu cuenta solo se usa para ver tus propios vídeos.</div></section>
      </div>
    </div>`;
  return {
    html,
    mount(root) {
      const name = root.querySelector('#set-name');
      name?.addEventListener('change', () => saveSettings({ name: name.value }));
    },
  };
}

export async function saveSettings(patch, message) {
  try {
    ui.settings = await post('/api/settings', patch);
    if (message) toast(message);
    document.dispatchEvent(new CustomEvent('romero:settings'));
  } catch {
    toast('No se pudo guardar el ajuste');
  }
}

function sourcesReport() {
  const lines = [`${ui.state?.app?.name || 'Romero Xandre CRM'} ${ui.state?.app?.version || ''} · informe de fuentes · ${new Date().toLocaleString('es-ES')}`,
    `Modo: ${DESKTOP ? 'ventana propia' : 'navegador'} · ${navigator.userAgent}`];
  for (const [id, st] of Object.entries(ui.state?.sources || {})) {
    const state = st.enabled === false ? 'DESACTIVADA' : st.ok ? (st.stale ? 'DATOS ANTIGUOS' : 'OK') : 'ERROR';
    lines.push(`- ${id}: ${state} · ${st.count ?? 0} elementos · modo ${st.mode || '—'} · ${F.ago(st.fetched_at)}${st.error ? ` · ${st.error}` : ''}`);
  }
  for (const [id, st] of Object.entries(ui.state?.connections || {})) {
    if (st && typeof st === 'object') lines.push(`- conexión ${id}: ${st.ok ? 'OK' : 'ERROR'} · ${st.count} vídeos${st.error ? ` · ${st.error}` : ''}`);
  }
  if (ui.state?.last_error) lines.push(`Error interno: ${ui.state.last_error}`);
  lines.push(`Historias: ${ui.state?.stories?.length ?? 0} · temas: ${ui.state?.topics?.length ?? 0}`);
  return lines.join('\n');
}

on('set-theme', (el) => saveSettings({ theme: el.dataset.theme }).then(() => rerender({ keepScroll: true })));
on('toggle-effects', (el) => saveSettings({ effects: el.checked }));
on('toggle-utility', (el) => saveSettings({ hide_utility: el.checked }));
on('set-refresh', (el) => saveSettings({ refresh_minutes: Number(el.value) }, 'Guardado'));
on('set-youtube', (el) => saveSettings({ youtube_topics: Number(el.value) }, 'Guardado: se aplicará en la próxima actualización'));
on('toggle-source', (el) => saveSettings({ sources: { ...(ui.settings?.sources || {}), [el.dataset.source]: el.checked } }, 'Guardado: actualizando…'));
on('save-channel', () => saveSettings({ youtube_channel: $('#yt-channel')?.value || '' }, 'Canal guardado: buscando tus vídeos…').then(() => setTimeout(() => rerender({ keepScroll: true }), 4000)));
on('save-ig', () => {
  const token = $('#ig-token')?.value.trim();
  if (!token) return toast('Pega primero el token');
  return saveSettings({ instagram_token: token }, 'Instagram conectado: buscando tus vídeos…').then(() => rerender({ keepScroll: true }));
});
on('clear-ig', () => saveSettings({ instagram_token: '' }, 'Instagram desconectado').then(() => rerender({ keepScroll: true })));
on('save-ai', () => {
  const key = $('#ai-key')?.value.trim();
  if (!key) return toast('Pega primero la clave');
  return saveSettings({ ai_key: key }, 'Clave guardada').then(() => rerender({ keepScroll: true }));
});
on('clear-ai', () => saveSettings({ ai_key: '' }, 'Clave quitada').then(() => rerender({ keepScroll: true })));
on('sync-now', async () => {
  await post('/api/sync').catch(() => null);
  toast('Sincronizando tus vídeos…');
});
on('copy-report', () => copyText(sourcesReport()));
on('clear-history', async () => {
  if (!confirm('¿Borrar el historial de tendencias? Tus tareas del calendario no se tocan.')) return;
  await post('/api/clear-history');
  toast('Historial borrado');
  document.dispatchEvent(new CustomEvent('romero:poll'));
});
