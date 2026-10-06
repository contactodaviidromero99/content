#!/bin/bash
# Instala o actualiza Romero Xandre CRM en un Mac con un solo comando:
#   curl -fsSL https://raw.githubusercontent.com/contactodaviidromero99/content/main/romero-crm/scripts/instalar.sh | bash
# Descarga la última versión, la deja en tu carpeta personal («Romero Xandre CRM»), crea la
# aplicación en Aplicaciones y la abre. Tus datos, tu historial y tus tareas no se tocan.

main() {
  local repo="contactodaviidromero99/content"
  local branch="${ROMERO_BRANCH:-main}"
  local url="${ROMERO_ZIP_URL:-https://codeload.github.com/$repo/zip/refs/heads/$branch}"
  local dest="$HOME/Romero Xandre CRM"
  local legacy="$HOME/Romero CRM"
  local tmp src

  if [ "$(uname)" != "Darwin" ]; then
    echo "Este instalador es para Mac."
    return 1
  fi
  if pgrep -f "[-]m romero_crm" >/dev/null 2>&1; then
    echo ""
    echo "  Romero Xandre CRM está abierto. Ciérralo y vuelve a pegar el comando para actualizarlo."
    echo ""
    return 1
  fi

  tmp="$(mktemp -d)" || return 1
  echo ""
  echo "  Descargando Romero Xandre CRM…"
  if ! curl -fsSL "$url" -o "$tmp/romero.zip" || ! unzip -q "$tmp/romero.zip" -d "$tmp"; then
    echo "  No se pudo descargar. Comprueba tu conexión a internet y vuelve a intentarlo."
    rm -rf "$tmp"
    return 1
  fi
  src="$(find "$tmp" -maxdepth 2 -type d -name romero-crm | head -n 1)"
  if [ -z "$src" ]; then
    echo "  La descarga no contiene Romero Xandre CRM. ¿Has fusionado el PR en GitHub?"
    rm -rf "$tmp"
    return 1
  fi

  rm -rf "$dest"
  mv "$src" "$dest"
  rm -rf "$tmp"
  # La versión anterior vivía en «~/Romero CRM»: si es una instalación nuestra, se retira.
  if [ -f "$legacy/romero_crm/__init__.py" ]; then
    rm -rf "$legacy"
  fi

  /bin/bash "$dest/Instalar en Aplicaciones.command" </dev/null || return 1
  open "$HOME/Applications/Romero Xandre CRM.app"
  echo "  Romero Xandre CRM se está abriendo. Ya puedes cerrar esta ventana de Terminal."
  echo ""
}

main "$@"
