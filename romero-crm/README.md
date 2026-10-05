# Romero CRM

Radar de tendencias de España para creadores de contenido. Junta en una sola ventana lo que se busca, se comenta y se lee **ahora mismo** en Google, X, TikTok, Wikipedia y los medios. Clasifica cada tema por nicho, mide su calor, estima cuánto recorrido le queda y te dice si en YouTube hay hueco para un vídeo sobre él.

Es gratuito, funciona en tu ordenador y no necesita cuentas ni claves de API.

![Radar](docs/radar.jpg)

> Las capturas usan **datos de demostración**. Con el programa abierto en tu Mac verás las tendencias reales.

## Qué tiene

| Sección | Para qué sirve |
|---|---|
| **Radar** | Los temas más calientes, fusionados entre plataformas: si algo es tendencia en Google, X y Wikipedia a la vez, aparece una sola vez con todas sus señales. Índice de calor de 0 a 100, volumen, crecimiento, curva de las últimas horas y fase. |
| **Predicción** | Qué temas tienen recorrido: fase (explosivo, en ascenso, señal temprana, en pico, enfriándose), potencial y ventana estimada según cuánto suelen durar las tendencias de ese nicho. Incluye qué nichos están al alza frente a su media semanal. |
| **Nichos** | Reparto por temática (deportes, política, historia, TV, tecnología…) y mapa de la semana. |
| **Historial** | Lo más buscado cada día, a qué hora arrancan las tendencias, cuánto duran y qué temas se repiten. |
| **Google** | Tendencias de búsqueda de las últimas 24 h, con volumen, subida y búsquedas relacionadas. |
| **YouTube** | Para cada tema caliente, cuántos vídeos se han subido esta semana y cuántas visualizaciones tienen: **hueco claro**, competencia moderada o muy competido. |
| **TikTok** | Hashtags y canciones en tendencia en España (últimos 7 días). |
| **X** | Tendencias de X en España, con cuánto tiempo llevan y su posición hora a hora. |
| **Wikipedia** | Los artículos más leídos desde España: una pista de lo que la gente quiere entender a fondo. |
| **Noticias** | Titulares de los medios españoles por sección. |
| **Efemérides** | Qué pasó tal día como hoy y los aniversarios redondos de los próximos 30 días (25, 50, 100, 250 años…), con prioridad a los de España. |

Al pulsar un tema se abre su ficha: por qué es tendencia, titulares que lo explican, curva de interés, competencia en YouTube, búsquedas relacionadas y un **brief listo para pegar en Claude** y pedirle ángulos para un guion.

![Ficha de un tema](docs/detalle.jpg)

## Cómo abrirlo en tu Mac

### Opción A: pídeselo a Claude Code en tu ordenador (la más fácil)

Abre Claude Code en tu Mac y pega esto:

```
Descarga el repositorio contactodaviidromero99/content de GitHub (rama claude/upbeat-carson-tq3p5m),
entra en la carpeta romero-crm y ejecuta «Instalar en Aplicaciones.command».
Después abre Romero CRM.
```

### Opción B: a mano

1. En GitHub, entra en el repositorio, elige la rama `claude/upbeat-carson-tq3p5m`, pulsa **Code → Download ZIP** y descomprímelo.
2. Abre la carpeta `romero-crm`.
3. Haz **clic derecho → Abrir** sobre **`Abrir Romero CRM.command`** (la primera vez macOS pregunta porque el archivo viene de internet; pulsa *Abrir*).
4. La primera vez tarda 1-2 minutos en prepararse. Las siguientes, unos segundos.

Si quieres tenerlo como una aplicación más (en Launchpad y Spotlight, con su icono), ejecuta una vez **`Instalar en Aplicaciones.command`** de la misma forma.

**Necesita Python 3.9 o superior.** Si no lo tienes, el programa te lo dice y abre la página de descarga (python.org → *Download Python*). Si macOS te pide instalar las «herramientas de línea de comandos», acepta: también sirven.

### Versión en el navegador

Si prefieres usarlo en el navegador en lugar de en su propia ventana:

```
./scripts/run.sh --web
```

y entra en `http://127.0.0.1:8765`.

## Sin la nube

Romero CRM funciona entero en tu ordenador: no depende de Claude ni de ningún servidor propio. Necesita **internet** para descargar las tendencias, pero el historial se guarda en tu Mac y lo puedes consultar aunque te quedes sin conexión.

Tus datos están en `~/Library/Application Support/Romero CRM/`. Desde **Ajustes** puedes borrar el historial.

## Fuentes y límites, sin adornos

| Fuente | Cómo se obtiene | Fiabilidad |
|---|---|---|
| Google Trends | Datos públicos de *Trending Now* (España), con respaldo por RSS | Alta |
| Wikipedia | API oficial de Wikimedia: lo más leído desde España | Alta |
| Google News | RSS público por secciones | Alta |
| Efemérides | API oficial de Wikipedia «tal día como hoy» | Alta |
| X (Twitter) | Webs públicas trends24.in y getdaytrends.com (la API de X es de pago) | Media: son webs de terceros |
| TikTok | Página pública de TikTok Creative Center | Media: TikTok la cambia a menudo |
| YouTube | Búsqueda pública de vídeos de la última semana | Media |

- **Instagram y Facebook no publican tendencias**, ni gratis ni pagando. Las tendencias de TikTok son la mejor aproximación para formato vertical.
- **YouTube eliminó su página de Tendencias en julio de 2025.** Por eso la sección de YouTube mide competencia en lugar de mostrar «lo más visto».
- Si una fuente falla, el resto sigue funcionando y en **Ajustes → Estado de las fuentes** verás el motivo.
- La **predicción** son estimaciones transparentes (crecimiento, curva de las últimas horas, presencia en varias plataformas y duración típica por nicho calculada con tu propio historial), no adivinación. Úsala para priorizar.
- Cuanto más tiempo tengas el programa abierto, más historial acumula y mejores son las estimaciones de duración.

## Para desarrolladores

```
romero-crm/
├── Abrir Romero CRM.command      lanzador para Mac
├── Instalar en Aplicaciones.command
├── scripts/run.sh                prepara el entorno y arranca
├── romero_crm/
│   ├── app.py                    ventana nativa (pywebview) o navegador
│   ├── server.py                 servidor local + API JSON
│   ├── engine.py                 actualizaciones programadas
│   ├── analysis.py               fusión multiplataforma, calor, fases, ventanas
│   ├── niches.py                 clasificación por nichos
│   ├── storage.py                historial en SQLite
│   ├── sources/                  una fuente por archivo
│   └── web/                      interfaz (HTML, CSS y JS sin dependencias)
└── tests/
```

- Pruebas: `python3 -m unittest discover -s tests`
- Modo demostración (datos de ejemplo, sin internet): `python3 -m romero_crm --demo --web`
