#!/usr/bin/env bash
set -e

# ==============================================================================
# Script para empaquetar como AppImage universal (ejecutable portátil para Linux)
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

APP_NAME="MyGDriveSync"
BIN_NAME="mygdrivesync"
APPDIR="build/AppDir"

if [ -d ".venv" ]; then
    PYTHON=".venv/bin/python3"
    PYINSTALLER=".venv/bin/pyinstaller"
else
    PYTHON="$(which python3)"
    PYINSTALLER="$(which pyinstaller)"
fi

echo "==> 1. Verificando binarios en dist/$BIN_NAME..."
if [ ! -d "dist/$BIN_NAME" ]; then
    echo "Compilando con PyInstaller primero..."
    mkdir -p assets
    $PYTHON -c "
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtWidgets import QApplication
from gdrive_sync.ui.icons import create_tray_icon
app = QApplication([])
icon = create_tray_icon('IDLE', 256)
icon.pixmap(256, 256).save('assets/gdrive-sync.png', 'PNG')
"
    $PYINSTALLER --name "$BIN_NAME" --windowed --noconfirm --clean --add-data "assets:assets" run.py
fi

echo "==> 2. Estructurando AppDir..."
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

# Copiar bundle de la aplicación a usr/bin/
cp -r dist/$BIN_NAME/* "$APPDIR/usr/bin/"

# Copiar icono
cp assets/gdrive-sync.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/mygdrivesync.png"
cp assets/gdrive-sync.png "$APPDIR/mygdrivesync.png"
cp assets/gdrive-sync.png "$APPDIR/.DirIcon"

cat << 'EOF' > "$APPDIR/mygdrivesync.desktop"
[Desktop Entry]
Type=Application
Version=1.0
Name=MyGDriveSync
GenericName=Cliente Google Drive (tipo Dropbox)
Comment=Sincronización bidireccional local tipo Dropbox para Google Drive
Exec=mygdrivesync
Icon=mygdrivesync
Terminal=false
Categories=Network;FileTransfer;Qt;
EOF

# Crear AppRun
cat << 'EOF' > "$APPDIR/AppRun"
#!/bin/sh
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/bin:${LD_LIBRARY_PATH}"
exec "${HERE}/usr/bin/mygdrivesync" "$@"
EOF
chmod +x "$APPDIR/AppRun"

echo "==> 3. Descargando appimagetool si no existe..."
APPIMAGETOOL="/tmp/appimagetool-x86_64.AppImage"
if [ ! -f "$APPIMAGETOOL" ]; then
    curl -L -o "$APPIMAGETOOL" "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "$APPIMAGETOOL"
fi

echo "==> 4. Generando AppImage..."
mkdir -p dist
export APPIMAGE_EXTRACT_AND_RUN=1
ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "dist/${APP_NAME}-x86_64.AppImage"

echo "======================================================================"
echo " ¡AppImage universal generado en dist/${APP_NAME}-x86_64.AppImage!"
echo "======================================================================"
