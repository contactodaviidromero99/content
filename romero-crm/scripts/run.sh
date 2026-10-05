#!/bin/bash
# Prepara el entorno de Python la primera vez y abre Romero CRM.
DIR="$(cd "$(dirname "$0")/.." && pwd)"
SUPPORT="$HOME/Library/Application Support/Romero CRM"
[ "$(uname)" = "Darwin" ] || SUPPORT="$HOME/.local/share/romero-crm"
VENV="$SUPPORT/venv"
mkdir -p "$SUPPORT"

aviso() {
  if command -v osascript >/dev/null 2>&1; then
    osascript -e "display dialog \"$1\" buttons {\"OK\"} default button 1 with title \"Romero CRM\"" >/dev/null 2>&1
  fi
  echo "$1"
}

find_python() {
  for candidate in "$ROMERO_PYTHON" /opt/homebrew/bin/python3 /usr/local/bin/python3 \
      /Library/Frameworks/Python.framework/Versions/Current/bin/python3 "$(command -v python3)" /usr/bin/python3; do
    [ -n "$candidate" ] && [ -x "$candidate" ] || continue
    if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

if [ ! -x "$VENV/bin/python" ]; then
  PY="$(find_python)"
  if [ -z "$PY" ] && [ "$(uname)" = "Darwin" ] && ! xcode-select -p >/dev/null 2>&1; then
    xcode-select --install >/dev/null 2>&1
    aviso "Romero CRM necesita Python, que viene con las «herramientas de línea de comandos» de Apple. Pulsa «Instalar» en la ventana de Apple, espera a que termine (unos minutos) y vuelve a intentarlo."
    exit 1
  fi
  if [ -z "$PY" ]; then
    aviso "Romero CRM necesita Python 3.9 o superior. Se abrirá python.org: descarga el instalador para macOS, instálalo y vuelve a abrir Romero CRM."
    open "https://www.python.org/downloads/macos/" 2>/dev/null
    exit 1
  fi
  echo "Preparando Romero CRM por primera vez (1-2 minutos)…"
  "$PY" -m venv "$VENV" || { aviso "No se pudo crear el entorno de Python."; exit 1; }
fi

STAMP="$VENV/.romero-requirements"
WANT="$(cat "$DIR/requirements.txt" "$DIR/requirements-desktop.txt" 2>/dev/null | cksum | cut -d" " -f1)"
if [ "$(cat "$STAMP" 2>/dev/null)" != "$WANT" ]; then
  echo "Instalando lo necesario…"
  "$VENV/bin/python" -m pip install --quiet --disable-pip-version-check --upgrade pip >/dev/null 2>&1
  if ! "$VENV/bin/python" -m pip install --quiet --disable-pip-version-check -r "$DIR/requirements.txt"; then
    aviso "No se pudieron instalar los componentes. Comprueba tu conexión a internet y vuelve a intentarlo."
    exit 1
  fi
  "$VENV/bin/python" -m pip install --quiet --disable-pip-version-check -r "$DIR/requirements-desktop.txt" \
    || echo "Aviso: no se pudo instalar la ventana propia; Romero CRM se abrirá en tu navegador."
  echo "$WANT" > "$STAMP"
fi

cd "$DIR" || exit 1
exec "$VENV/bin/python" -m romero_crm "$@"
