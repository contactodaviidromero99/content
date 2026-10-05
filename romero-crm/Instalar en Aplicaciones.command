#!/bin/bash
# Crea "Romero CRM" en tu carpeta Aplicaciones, con icono, para abrirlo como cualquier programa.
DIR="$(cd "$(dirname "$0")" && pwd)"
APP="$HOME/Applications/Romero CRM.app"
ICON="$DIR/romero_crm/web/img/icon.png"

if [ "$(uname)" != "Darwin" ]; then
  echo "Este instalador es solo para Mac."
  exit 1
fi

echo ""
echo "  Preparando Romero CRM (la primera vez tarda 1-2 minutos)…"
/bin/bash "$DIR/scripts/run.sh" --help >/dev/null || exit 1

mkdir -p "$HOME/Applications"
rm -rf "$APP"
osacompile -o "$APP" -e "do shell script \"/bin/bash '$DIR/scripts/run.sh' > /dev/null 2>&1 &\"" 2>/dev/null || {
  echo "No se pudo crear la aplicación."
  exit 1
}

ICONSET="$(mktemp -d)/RomeroCRM.iconset"
mkdir -p "$ICONSET"
for size in 16 32 128 256 512; do
  sips -z "$size" "$size" "$ICON" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
  double=$((size * 2))
  sips -z "$double" "$double" "$ICON" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/applet.icns" 2>/dev/null
touch "$APP"
# Que el Finder y el Launchpad muestren el icono nuevo al actualizar
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
[ -x "$LSREGISTER" ] && "$LSREGISTER" -f "$APP" >/dev/null 2>&1

echo ""
echo "  Listo: tienes «Romero CRM» en tu carpeta Aplicaciones (dentro de tu usuario)."
echo "  Ábrelo desde Launchpad o Spotlight (Cmd + Espacio y escribe «Romero»)."
echo "  Si mueves esta carpeta de sitio, vuelve a ejecutar este instalador."
echo ""
open -R "$APP"
