#!/usr/bin/env bash
set -e

# ==============================================================================
# Script para empaquetar como AppImage universal (ejecutable portátil para Linux)
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

APP_NAME="GoogleDriveSync"
APPDIR="build/AppDir"

echo "==> 1. Verificando compilación en dist/gdrive-sync..."
if [ ! -d "dist/gdrive-sync" ]; then
    echo "Compilando con PyInstaller primero..."
    .venv/bin/pyinstaller --name "gdrive-sync" --windowed --noconfirm --clean --add-data "assets:assets" run.py
fi

echo "==> 2. Estructurando AppDir..."
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

# Copiar bundle de la aplicación a usr/bin/gdrive-sync
cp -r dist/gdrive-sync/* "$APPDIR/usr/bin/"

# Copiar iconos y desktop entry en la raíz de AppDir
cp assets/gdrive-sync.png "$APPDIR/gdrive-sync.png"
cp assets/gdrive-sync.png "$APPDIR/.DirIcon"

cat << 'EOF' > "$APPDIR/gdrive-sync.desktop"
[Desktop Entry]
Type=Application
Version=1.0
Name=Google Drive Sync
GenericName=Cliente de sincronización de Google Drive
Comment=Sincronización tipo Dropbox para Google Drive
Exec=gdrive-sync
Icon=gdrive-sync
Terminal=false
Categories=Network;FileTransfer;
EOF

# Crear AppRun
cat << 'EOF' > "$APPDIR/AppRun"
#!/bin/sh
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/bin:${LD_LIBRARY_PATH}"
exec "${HERE}/usr/bin/gdrive-sync" "$@"
EOF
chmod +x "$APPDIR/AppRun"

echo "==> 3. Descargando appimagetool si no existe..."
APPIMAGETOOL="/tmp/appimagetool-x86_64.AppImage"
if [ ! -f "$APPIMAGETOOL" ]; then
    curl -L -o "$APPIMAGETOOL" "https://github.com/AppImage/AppImageKit/releases/download/13/appimagetool-x86_64.AppImage"
    chmod +x "$APPIMAGETOOL"
fi

echo "==> 4. Generando AppImage..."
ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "dist/${APP_NAME}-x86_64.AppImage"

echo "======================================================================"
echo " ¡AppImage universal generado en dist/${APP_NAME}-x86_64.AppImage!"
echo "======================================================================"
