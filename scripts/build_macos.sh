#!/usr/bin/env bash
set -e

# ==============================================================================
# Script para compilar y empaquetar MyGDriveSync para macOS (.app y .dmg)
# ==============================================================================

if [ "$(uname)" != "Darwin" ]; then
    echo "⚠️ Advertencia: Este script está diseñado para ejecutarse en macOS."
    echo "Para compilar el instalador de macOS desde Linux/Windows, utiliza el flujo de GitHub Actions (.github/workflows/build-macos.yml)."
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

APP_NAME="MyGDriveSync"
DMG_NAME="${DMG_NAME:-MyGDriveSync}"

if [ -d ".venv" ]; then
    PYTHON=".venv/bin/python3"
    PYINSTALLER=".venv/bin/pyinstaller"
else
    PYTHON="$(which python3)"
    PYINSTALLER="$(which pyinstaller)"
fi

echo "==> 1. Verificando entorno e iconos..."
mkdir -p assets
if [ ! -f "assets/gdrive-sync.png" ]; then
    $PYTHON -c "
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtWidgets import QApplication
from gdrive_sync.ui.icons import create_tray_icon
app = QApplication([])
icon = create_tray_icon('IDLE', 512)
icon.pixmap(512, 512).save('assets/gdrive-sync.png', 'PNG')
"
fi

# Generar archivo .icns nativo para macOS si contamos con sips e iconutil
ICON_OPT=""
if which iconutil >/dev/null 2>&1 && which sips >/dev/null 2>&1; then
    echo "Generando assets/gdrive-sync.icns con iconutil..."
    ICONSET="build/MyGDriveSync.iconset"
    rm -rf "$ICONSET"
    mkdir -p "$ICONSET"
    sips -z 16 16     assets/gdrive-sync.png --out "$ICONSET/icon_16x16.png" >/dev/null 2>&1
    sips -z 32 32     assets/gdrive-sync.png --out "$ICONSET/icon_16x16@2x.png" >/dev/null 2>&1
    sips -z 32 32     assets/gdrive-sync.png --out "$ICONSET/icon_32x32.png" >/dev/null 2>&1
    sips -z 64 64     assets/gdrive-sync.png --out "$ICONSET/icon_32x32@2x.png" >/dev/null 2>&1
    sips -z 128 128   assets/gdrive-sync.png --out "$ICONSET/icon_128x128.png" >/dev/null 2>&1
    sips -z 256 256   assets/gdrive-sync.png --out "$ICONSET/icon_128x128@2x.png" >/dev/null 2>&1
    sips -z 256 256   assets/gdrive-sync.png --out "$ICONSET/icon_256x256.png" >/dev/null 2>&1
    sips -z 512 512   assets/gdrive-sync.png --out "$ICONSET/icon_256x256@2x.png" >/dev/null 2>&1
    sips -z 512 512   assets/gdrive-sync.png --out "$ICONSET/icon_512x512.png" >/dev/null 2>&1
    iconutil -c icns "$ICONSET" -o "assets/gdrive-sync.icns"
    rm -rf "$ICONSET"
    ICON_OPT="--icon assets/gdrive-sync.icns"
elif [ -f "assets/gdrive-sync.icns" ]; then
    ICON_OPT="--icon assets/gdrive-sync.icns"
else
    ICON_OPT="--icon assets/gdrive-sync.png"
fi

echo "==> 2. Compilando bundle .app con PyInstaller..."
rm -rf "dist/$APP_NAME.app"
$PYINSTALLER \
    --name "$APP_NAME" \
    --windowed \
    --noconfirm \
    --clean \
    --add-data "assets:assets" \
    $ICON_OPT \
    --osx-bundle-identifier "com.mygdrivesync.desktop" \
    run.py

echo "==> 3. Empaquetando en imagen de disco (.dmg)..."
DMG_ROOT="build/dmg_root"
rm -rf "$DMG_ROOT"
mkdir -p "$DMG_ROOT"
cp -R "dist/$APP_NAME.app" "$DMG_ROOT/"
# Enlace simbólico estándar para arrastrar y soltar a Aplicaciones
ln -s /Applications "$DMG_ROOT/Applications"

mkdir -p dist
DMG_PATH="dist/${DMG_NAME}.dmg"
rm -f "$DMG_PATH"

hdiutil create -volname "$APP_NAME" -srcfolder "$DMG_ROOT" -ov -format UDZO "$DMG_PATH"
rm -rf "$DMG_ROOT"

echo "======================================================================"
echo " ¡Instalador macOS DMG generado en $DMG_PATH!"
echo "======================================================================"
