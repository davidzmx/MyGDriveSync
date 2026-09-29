# MyGDriveSync (Cliente tipo Dropbox multiplataforma)

Una aplicación cliente de sincronización bidireccional en carpeta local para **Google Drive**, diseñada específicamente para integrarse a la perfección con **Debian 12 (KDE Plasma / Dolphin)** y **Windows**, funcionando exactamente como **Dropbox**.

---

## 🚀 Características Principales

1. **Sincronización en Carpeta Local (Estilo Dropbox):**
   * Tus archivos viven físicamente en tu disco (`~/MyGDriveSync` en Linux o `C:\Users\Usuario\MyGDriveSync` en Windows).
   * Monitoreo local en tiempo real con `watchdog` (inotify en Linux, ReadDirectoryChangesW en Windows).
   * Detección de escrituras incompletas y *debouncing* para evitar subidas prematuras de archivos en edición o copia.

2. **Sincronización Selectiva:**
   * Diálogo gráfico con vista de árbol (`QTreeWidget`) que muestra todas tus carpetas de Google Drive.
   * Puedes marcar y desmarcar qué carpetas deseas tener descargadas localmente.
   * Al desmarcar una carpeta, se elimina del disco local para liberar espacio sin tocar la copia en la nube.

3. **Icono Dinámico en la Bandeja del Sistema (System Tray):**
   * Compatible con **KDE Plasma** (StatusNotifierItem) y la **Barra de Tareas de Windows**.
   * Iconos vectoriales de alta resolución generados dinámicamente según el estado:
     * 🟢 **Al día:** Archivos sincronizados.
     * 🔵 **Sincronizando:** Transferencias activas en curso.
     * ⚪ **En pausa:** Sincronización detenida por el usuario.
     * 🔴 **Error:** Fallo de conexión o transferencia.
     * 🟡 **Requiere inicio de sesión:** Pendiente de vincular cuenta.

4. **Integración Nativa con KDE Dolphin:**
   * Instalación automática de Service Menus (`.desktop`) en `~/.local/share/kio/servicemenus/`.
   * Clic derecho en cualquier archivo o carpeta dentro de `~/MyGDriveSync`:
     * *"Abrir en Google Drive (Web)"*
     * *"Copiar enlace web de Drive"*

5. **Resolución Inteligente de Conflictos:**
   * Comparación de sumas de verificación **MD5** locales contra `md5Checksum` de Google Drive.
   * Si un archivo se modifica simultáneamente en dos equipos, crea una copia de conflicto:  
     `Nombre (Conflicto de copia AAAA-MM-DD-HHMMSS).ext`  
     sin sobreescribir ni perder el trabajo realizado.

6. **Seguridad y Persistencia:**
   * Almacenamiento seguro de tokens OAuth 2.0 con **Keyring** (**KWallet** en KDE, **Windows Credential Manager** en Windows) y respaldo en archivo con permisos restringidos `0600`.
   * Base de datos SQLite local en modo **WAL** (Write-Ahead Logging) para operaciones atómicas y concurrentes.

---

## 📂 Estructura del Proyecto

```
mytests/
├── gdrive_sync/
│   ├── auth/              # Flujo OAuth 2.0 PKCE, Keyring y token storage
│   ├── config.py          # Gestión de rutas y configuración multiplataforma
│   ├── database/          # SQLite WAL, modelos de datos y reglas de sincronización
│   ├── drive/             # Cliente de Google Drive API v3 (upload resumible, chunking)
│   ├── engine/            # SyncService, LocalFileWatcher, CloudPoller, Reconciler y Queue
│   ├── integrations/      # Service Menu de Dolphin y Autostart (Linux / Windows)
│   ├── ui/                # System Tray, Sincronización Selectiva, Preferencias, Actividad
│   └── main.py            # Punto de entrada Qt
├── tests/                 # Suite de pruebas unitarias (15 tests automatizados)
├── requirements.txt       # Dependencias
├── setup.py               # Empaquetado y comandos de consola
└── README.md
```

---

## 🛠️ Instalación y Uso en Debian 12 (KDE Plasma)

### 1. Activar el entorno virtual
En este repositorio ya se encuentra preparado el entorno virtual con Python 3.11:
```bash
source .venv/bin/activate
```

*(Si necesitas crear un nuevo entorno en otra máquina Debian 12)*:
```bash
sudo apt update && sudo apt install python3-venv python3-pip
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### 2. Ejecutar la aplicación
```bash
gdrive-sync
```
O directamente con Python:
```bash
python3 -m gdrive_sync.main
```

Aparecerá inmediatamente el icono de **Google Drive Sync** en la bandeja del sistema (junto al reloj de KDE Plasma).

---

## 🔑 Configurar tus Credenciales de Google Drive (Paso a Paso)

Para conectar tu propia cuenta personal de Google Drive:

1. Ve a la consola de [Google Cloud Console](https://console.cloud.google.com/).
2. Crea un proyecto (o selecciona uno existente).
3. En el menú lateral, ve a **APIs y servicios > Biblioteca** y habilita la **Google Drive API**.
4. Ve a **APIs y servicios > Pantalla de consentimiento de OAuth**:
   * Tipo de usuario: **Externo**.
   * Llena los datos básicos (nombre de la app, correo de contacto).
   * En "Permisos / Scopes", agrega: `.../auth/drive` (o `drive.file`).
   * En "Usuarios de prueba", añade tu correo de Gmail.
5. Ve a **APIs y servicios > Credenciales**:
   * Haz clic en **Crear credenciales > ID de cliente de OAuth**.
   * Tipo de aplicación: **App de escritorio** (Desktop application).
   * Haz clic en **Crear** y luego en **Descargar JSON**.
6. En la aplicación **Google Drive Sync**:
   * Haz clic derecho en el icono de la bandeja y abre **Preferencias...**
   * En la pestaña **Cuenta de Google**, pulsa **"Importar archivo client_secrets.json..."** y selecciona el archivo descargado.
   * Haz clic en **"Iniciar sesión con Google"**. Se abrirá tu navegador para autorizar la aplicación.
   * ¡Listo! Se iniciará la sincronización en `~/GoogleDrive`.

---

## 🗂️ Cómo usar la Sincronización Selectiva

1. Haz clic derecho en el icono de la bandeja y selecciona **🗂 Sincronización selectiva...**
2. Se cargará el árbol jerárquico de tus carpetas en Google Drive.
3. Desmarca las carpetas que no desees almacenar en el disco de tu ordenador.
4. Pulsa **Guardar cambios**: las carpetas desmarcadas se removerán de tu disco local sin ser eliminadas de la nube.

---

## 🐬 Integración con Dolphin (KDE)

Al arrancar la aplicación por primera vez en Linux, se instala automáticamente la acción para Dolphin.  
Cuando navegues con Dolphin dentro de tu carpeta de Google Drive (`~/GoogleDrive`), al hacer clic derecho en cualquier archivo verás el submenú:
* **Google Drive Sync > Abrir en Google Drive (Web)**
* **Google Drive Sync > Copiar enlace web de Drive**

---

## 📦 Generación de Instaladores para Linux (.deb y AppImage)

El proyecto incluye scripts y flujos CI automatizados para generar instaladores profesionales listos para distribuir en Debian, Ubuntu, cualquier distribución Linux y Windows.

### 1. Generar paquete nativo `.deb` (Debian 12 / Ubuntu / KDE)
Este instalador configura todo en el sistema operativo: binario en `/usr/bin/mygdrivesync`, acceso directo en el menú de aplicaciones de KDE Plasma / GNOME, icono en alta resolución y el Service Menu para Dolphin a nivel del sistema.

Ejecuta el script:
```bash
./scripts/build_deb.sh
```

El instalador se generará en:
`dist/mygdrivesync_0.1.0_amd64.deb`

#### Cómo instalarlo en Debian 12 / Ubuntu:
```bash
sudo apt install ./dist/mygdrivesync_0.1.0_amd64.deb
```
O con `dpkg`:
```bash
sudo dpkg -i dist/mygdrivesync_0.1.0_amd64.deb
```

#### Cómo desinstalarlo:
```bash
sudo apt remove mygdrivesync
```

---

### 2. Generar paquete universal `AppImage` (Para cualquier distribución Linux)
Un solo archivo ejecutable portátil que funciona en cualquier distribución (Debian, Fedora, Arch, Ubuntu, openSUSE, etc.) sin requerir instalación previa ni permisos de root:

```bash
./scripts/build_appimage.sh
```
El archivo se generará en:  
`dist/MyGDriveSync-x86_64.AppImage`

Para usarlo en cualquier equipo:
```bash
chmod +x dist/MyGDriveSync-x86_64.AppImage
./dist/MyGDriveSync-x86_64.AppImage
```

---

## ☁️ Compilación automática en la nube (GitHub Actions)

El repositorio incluye flujos automáticos de CI/CD para generar todos los instaladores sin necesidad de compilar manualmente:

### Flujo Linux (`.github/workflows/build-linux.yml`)
Genera automáticamente:
- **`MyGDriveSync-Linux-deb`**: Paquete instalable `.deb` (`mygdrivesync_0.1.0_amd64.deb`).
- **`MyGDriveSync-Linux-AppImage`**: Ejecutable portátil universal `MyGDriveSync-x86_64.AppImage`.

### Flujo Windows (`.github/workflows/build-windows.yml`)
Genera automáticamente:
- **`MyGDriveSync-Windows-Installer`**: Instalador profesional con Inno Setup (`MyGDriveSync_Setup_x64.exe`).

### Flujo macOS (`.github/workflows/build-macos.yml`)
Genera automáticamente imágenes de disco nativas (`.dmg`):
- **`MyGDriveSync-macOS-AppleSilicon-DMG`**: Para Macs con chips Apple Silicon (M1, M2, M3, M4).
- **`MyGDriveSync-macOS-Intel-DMG`**: Para Macs con procesadores Intel (x86_64).

### Cómo descargarlos desde GitHub:
1. Sube tus cambios al repositorio con `git push origin main`.
2. En GitHub, ve a la pestaña **Actions**.
3. Selecciona la ejecución del workflow deseado (**Build Linux Packages**, **Build Windows Installer** o **Build macOS Installer**).
4. En la parte inferior de la página (sección **Artifacts**), descarga directamente los instaladores listos para usar.

---

## 🚀 Cómo publicar una versión oficial (GitHub Release)

Una **Release** en GitHub publica una versión oficial descargable para el público con todos los instaladores listos en la página principal del proyecto.

### Opción A: Publicación 100% automatizada con Git Tag (Recomendado)
Simplemente crea una etiqueta de versión y súbela a GitHub:
```bash
git tag -a v0.1.0 -m "Release v0.1.0 - Sincronización bidireccional y selectiva para Google Drive"
git push origin v0.1.0
```
GitHub Actions detectará la etiqueta `v*`, compilará en paralelo para las 3 plataformas y publicará automáticamente la **Release** con los 5 instaladores adjuntos:
- `MyGDriveSync_Setup_x64.exe` (Windows)
- `mygdrivesync_0.1.0_amd64.deb` (Linux Debian / Ubuntu)
- `MyGDriveSync-x86_64.AppImage` (Linux Universal)
- `MyGDriveSync-AppleSilicon.dmg` (macOS Apple Silicon)
- `MyGDriveSync-Intel.dmg` (macOS Intel)

### Opción B: Manual desde la web de GitHub
1. Ve a tu repositorio en `https://github.com/davidzmx/MyGDriveSync/releases`.
2. Haz clic en **"Draft a new release"** (o "Create a new release").
3. En **Choose a tag**, escribe `v0.1.0` y selecciona *"Create new tag"*.
4. Escribe el título de la versión (ej. `MyGDriveSync v0.1.0`) y describe las novedades.
5. Arrastra los archivos compilados que descargaste de la sección de **Actions > Artifacts**.
6. Haz clic en **Publish release**.

---

## 🍎 Generación del Instalador para macOS (`.dmg`)

En macOS, la aplicación se distribuye como una imagen de disco estándar (`.dmg`) que contiene el paquete `MyGDriveSync.app` y el acceso directo a `/Applications` para instalación mediante arrastrar y soltar (drag & drop).

### Compilar localmente en macOS:
1. Clona o copia el proyecto en una Mac.
2. Abre la Terminal en la carpeta del proyecto.
3. Ejecuta el script:
   ```bash
   chmod +x scripts/build_macos.sh
   ./scripts/build_macos.sh
   ```
4. El archivo generado quedará en:
   `dist/MyGDriveSync.dmg`

### Instalación en macOS:
1. Haz doble clic en `MyGDriveSync.dmg`.
2. Arrastra el icono de **MyGDriveSync** hacia la carpeta **Applications**.
3. > **Nota de seguridad (Gatekeeper):** Si macOS muestra *"No se puede abrir porque proviene de un desarrollador no identificado"*, haz clic derecho (o Control + clic) sobre la aplicación en `/Applications` y selecciona **Abrir**, o ejecuta en Terminal:
   > ```bash
   > xattr -cr /Applications/MyGDriveSync.app
   > ```
---

## 🪟 Generación del Instalador para Windows (`.exe` Setup)

Para Windows se utiliza el estándar de la industria: **Inno Setup**, el cual genera un instalador profesional con asistente gráfico (`MyGDriveSync_Setup_x64.exe`), desinstalador automático en el Panel de Control, accesos directos e icono multi-resolución.

### Compilar localmente en Windows:
1. Clona o copia la carpeta del proyecto en una máquina Windows.
2. Abre la consola (`CMD` o `PowerShell`) dentro de la carpeta.
3. Ejecuta el script:
   ```cmd
   scripts\build_windows.bat
   ```
4. El script generará el instalador final en:  
   `dist\MyGDriveSync_Setup_x64.exe`

> **Nota:** Puedes descargar **Inno Setup** gratuitamente desde [jrsoftware.org](https://jrsoftware.org/isdl.php).

---

### Qué incluye el instalador de Windows:
* Asistente de instalación en español e inglés.
* Selección de ruta de instalación (por defecto `C:\Program Files\MyGDriveSync`).
* Acceso directo en el **Menú Inicio** y en el **Escritorio**.
* Casilla opcional: *"Iniciar MyGDriveSync automáticamente al iniciar Windows"* (añade entrada en el registro `HKCU\...\Run`).
* Desinstalador completo registrado en **Configuración de Windows > Aplicaciones instaladas** (o Panel de Control).
* Icono multi-tamaño incrustado en el ejecutable (`assets/gdrive-sync.ico`).


## 🧪 Ejecución de Pruebas Unitarias

Para comprobar que todos los componentes (Base de datos SQLite, Reconciliador, Watcher, Queue y UI) funcionan correctamente:
```bash
.venv/bin/python3 -m unittest discover tests
```
Resultado: **15 pruebas completadas con éxito en ~1.5 segundos**.
