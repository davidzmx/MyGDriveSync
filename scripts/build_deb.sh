#!/usr/bin/env bash
set -e

# ==============================================================================
# Script de empaquetado .deb para Debian 12 / Ubuntu (KDE Plasma & Dolphin)
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

APP_NAME="mygdrivesync"
VERSION="0.1.0"
ARCH="amd64"
PKG_DIR="build/deb/${APP_NAME}_${VERSION}_${ARCH}"
OUTPUT_DEB="dist/${APP_NAME}_${VERSION}_${ARCH}.deb"

echo "==> 1. Verificando entorno virtual y dependencias..."
if [ -d ".venv" ]; then
    PYTHON=".venv/bin/python3"
    PYINSTALLER=".venv/bin/pyinstaller"
else
    PYTHON="$(which python3)"
    PYINSTALLER="$(which pyinstaller)"
fi

echo "==> 2. Generando icono de la aplicación..."
mkdir -p assets
$PYTHON -c "
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtWidgets import QApplication
from pathlib import Path
from gdrive_sync.ui.icons import create_tray_icon

app = QApplication([])
icon = create_tray_icon('IDLE', 256)
pixmap = icon.pixmap(256, 256)
pixmap.save('assets/gdrive-sync.png', 'PNG')
print('Icono generado en assets/gdrive-sync.png')
"

echo "==> 3. Compilando binarios con PyInstaller..."
$PYINSTALLER \
    --name "$APP_NAME" \
    --windowed \
    --noconfirm \
    --clean \
    --add-data "assets:assets" \
    run.py

echo "==> 4. Preparando árbol del paquete .deb..."
rm -rf "build/deb"
mkdir -p "$PKG_DIR/DEBIAN"
mkdir -p "$PKG_DIR/opt/$APP_NAME"
mkdir -p "$PKG_DIR/usr/bin"
mkdir -p "$PKG_DIR/usr/share/applications"
mkdir -p "$PKG_DIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$PKG_DIR/usr/share/kio/servicemenus"

# Copiar bundle de la aplicación a /opt/mygdrivesync/
cp -r dist/$APP_NAME/* "$PKG_DIR/opt/$APP_NAME/"

# Crear lanzador ejecutable en /usr/bin/mygdrivesync
cat << 'EOF' > "$PKG_DIR/usr/bin/mygdrivesync"
#!/bin/sh
exec /opt/mygdrivesync/mygdrivesync "$@"
EOF
chmod 755 "$PKG_DIR/usr/bin/mygdrivesync"

# Enlace simbolico de compatibilidad para gdrive-sync
ln -sf /usr/bin/mygdrivesync "$PKG_DIR/usr/bin/gdrive-sync"

# Iconos
cp assets/gdrive-sync.png "$PKG_DIR/usr/share/icons/hicolor/256x256/apps/mygdrivesync.png"
cp assets/gdrive-sync.png "$PKG_DIR/usr/share/icons/hicolor/256x256/apps/gdrive-sync.png"

# Archivo de escritorio (KDE Launcher / Menú de aplicaciones)
cat << 'EOF' > "$PKG_DIR/usr/share/applications/mygdrivesync.desktop"
[Desktop Entry]
Type=Application
Version=1.0
Name=MyGDriveSync
GenericName=Cliente Google Drive (tipo Dropbox)
Comment=Sincronización bidireccional local tipo Dropbox para Google Drive
Exec=/usr/bin/mygdrivesync
Icon=mygdrivesync
Terminal=false
Categories=Network;FileTransfer;Qt;
Keywords=google;drive;sync;cloud;dropbox;mygdrivesync;
StartupNotify=true
EOF
chmod 644 "$PKG_DIR/usr/share/applications/mygdrivesync.desktop"

# Integración con Dolphin (KDE Service Menu a nivel de sistema)
cat << 'EOF' > "$PKG_DIR/usr/share/kio/servicemenus/gdrive_sync_dolphin.desktop"
[Desktop Entry]
Type=Service
ServiceTypes=KonqPopupMenu/Plugin
MimeType=all/allfiles;inode/directory;
Actions=openInGDriveWeb;copyGDriveLink;
X-KDE-Submenu=MyGDriveSync
X-KDE-Priority=TopLevel

[Desktop Action openInGDriveWeb]
Name=Abrir en Google Drive (Web)
Icon=internet-web-browser
Exec=/usr/bin/mygdrivesync --dolphin-open "%u"

[Desktop Action copyGDriveLink]
Name=Copiar enlace web de Drive
Icon=edit-copy
Exec=/usr/bin/mygdrivesync --dolphin-copy "%u"
EOF
chmod 644 "$PKG_DIR/usr/share/kio/servicemenus/gdrive_sync_dolphin.desktop"

# Metadatos del paquete (DEBIAN/control)
cat << EOF > "$PKG_DIR/DEBIAN/control"
Package: $APP_NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Maintainer: David <david@localhost>
Depends: libc6, libgl1
Replaces: gdrive-sync
Conflicts: gdrive-sync
Provides: gdrive-sync
Description: MyGDriveSync Client
 Cliente de sincronización en carpeta local estilo Dropbox para Google Drive.
 Incluye soporte de sincronización selectiva, icono dinámico en la bandeja
 del sistema (System Tray) e integración con el gestor de archivos KDE Dolphin.
EOF
chmod 644 "$PKG_DIR/DEBIAN/control"

# Script postinst para actualizar cachés de iconos y menús de KDE
cat << 'EOF' > "$PKG_DIR/DEBIAN/postinst"
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q /usr/share/icons/hicolor || true
fi
exit 0
EOF
chmod 755 "$PKG_DIR/DEBIAN/postinst"

# Script postrm
cat << 'EOF' > "$PKG_DIR/DEBIAN/postrm"
#!/bin/sh
set -e
if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications || true
    fi
fi
exit 0
EOF
chmod 755 "$PKG_DIR/DEBIAN/postrm"

echo "==> 5. Construyendo paquete .deb con dpkg-deb..."
dpkg-deb --build --root-owner-group "$PKG_DIR" "$OUTPUT_DEB"

echo ""
echo "======================================================================"
echo " ¡Paquete Debian generado exitosamente!"
echo " Ubicación: $OUTPUT_DEB"
echo ""
echo " Para instalarlo en tu sistema ejecuta:"
echo "   sudo apt install ./$OUTPUT_DEB"
echo " o:"
echo "   sudo dpkg -i $OUTPUT_DEB"
echo "======================================================================"
