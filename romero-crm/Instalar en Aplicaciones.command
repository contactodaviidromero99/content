#!/bin/bash
# Crea «Romero Xandre CRM» en tu carpeta Aplicaciones, con su icono, para abrirlo como cualquier programa.
DIR="$(cd "$(dirname "$0")" && pwd)"
NAME="Romero Xandre CRM"
APP="$HOME/Applications/$NAME.app"
ICON="$DIR/romero_crm/web/img/icon.png"

if [ "$(uname)" != "Darwin" ]; then
  echo "Este instalador es solo para Mac."
  exit 1
fi

echo ""
echo "  Preparando $NAME (la primera vez tarda 1-2 minutos)…"
/bin/bash "$DIR/scripts/run.sh" --help >/dev/null || exit 1

mkdir -p "$HOME/Applications"
# La versión anterior se llamaba «Romero CRM»: se sustituye por la nueva.
rm -rf "$APP" "$HOME/Applications/Romero CRM.app"
osacompile -o "$APP" -e "do shell script \"/bin/bash '$DIR/scripts/run.sh' > /dev/null 2>&1 &\"" 2>/dev/null || {
  echo "No se pudo crear la aplicación."
  exit 1
}

# Icono. Desde macOS 14 las apps de AppleScript traen su icono (el pergamino) dentro de Assets.car y
# el Info.plist lo pide por nombre (CFBundleIconName): mientras exista, macOS ignora cualquier otro
# icono. Por eso se quitan los dos y se deja solo el nuestro.
WORK="$(mktemp -d)"
ICONSET="$WORK/AppIcon.iconset"
mkdir -p "$ICONSET"
for size in 16 32 128 256 512; do
  sips -z "$size" "$size" "$ICON" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
  double=$((size * 2))
  sips -z "$double" "$double" "$ICON" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done
RES="$APP/Contents/Resources"
PLIST="$APP/Contents/Info.plist"
iconutil -c icns "$ICONSET" -o "$RES/applet.icns" 2>/dev/null
rm -f "$RES/Assets.car"
rm -rf "$WORK"
PB=/usr/libexec/PlistBuddy
$PB -c "Delete :CFBundleIconName" "$PLIST" >/dev/null 2>&1
$PB -c "Set :CFBundleIconFile applet" "$PLIST" >/dev/null 2>&1 || $PB -c "Add :CFBundleIconFile string applet" "$PLIST" >/dev/null 2>&1
$PB -c "Set :CFBundleName '$NAME'" "$PLIST" >/dev/null 2>&1 || $PB -c "Add :CFBundleName string '$NAME'" "$PLIST" >/dev/null 2>&1
$PB -c "Delete :CFBundleDisplayName" "$PLIST" >/dev/null 2>&1
$PB -c "Add :CFBundleDisplayName string '$NAME'" "$PLIST" >/dev/null 2>&1
$PB -c "Set :CFBundleIdentifier com.romeroxandre.crm" "$PLIST" >/dev/null 2>&1 || $PB -c "Add :CFBundleIdentifier string com.romeroxandre.crm" "$PLIST" >/dev/null 2>&1
# Tras cambiar el icono hay que volver a firmar la app (firma local, sin cuenta de Apple).
codesign --force --deep --sign - "$APP" >/dev/null 2>&1
touch "$APP"
# Que el Finder, el Dock y el Launchpad vean el icono nuevo
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
[ -x "$LSREGISTER" ] && "$LSREGISTER" -f "$APP" >/dev/null 2>&1

echo ""
echo "  Listo: tienes «$NAME» en tu carpeta Aplicaciones (dentro de tu usuario)."
echo "  Ábrelo desde Launchpad o Spotlight (Cmd + Espacio y escribe «Romero»)."
echo "  Si lo tenías en el Dock, quita el icono viejo y arrastra el nuevo."
echo "  Si mueves esta carpeta de sitio, vuelve a ejecutar este instalador."
echo ""
open -R "$APP"
