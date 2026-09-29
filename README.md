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

El proyecto incluye scripts automatizados para generar instaladores profesionales listos para distribuir en Debian, Ubuntu y cualquier distribución Linux.

### 1. Generar paquete nativo `.deb` (Debian 12 / Ubuntu / KDE)
Este instalador configura todo en el sistema operativo: binario en `/usr/bin/gdrive-sync`, acceso directo en el menú de aplicaciones de KDE Plasma, icono en alta resolución y el Service Menu para Dolphin a nivel del sistema.

Ejecuta el script:
```bash
./scripts/build_deb.sh
```

El instalador se generará en:
`dist/gdrive-sync_0.1.0_amd64.deb`

#### Cómo instalarlo en Debian 12:
```bash
sudo apt install ./dist/gdrive-sync_0.1.0_amd64.deb
```
O con `dpkg`:
```bash
sudo dpkg -i dist/gdrive-sync_0.1.0_amd64.deb
```

#### Cómo desinstalarlo:
```bash
sudo apt remove gdrive-sync
```

---

### 2. Generar paquete universal `AppImage` (Para cualquier distribución Linux)
Un solo archivo ejecutable portátil que funciona en cualquier distribución sin requerir instalación:

```bash
./scripts/build_appimage.sh
```
El archivo se generará en:  
`dist/GoogleDriveSync-x86_64.AppImage`

Para usarlo en cualquier equipo:
```bash
chmod +x dist/GoogleDriveSync-x86_64.AppImage
./dist/GoogleDriveSync-x86_64.AppImage
```

---

## 🪟 Generación del Instalador para Windows (`.exe` Setup)

Para Windows se utiliza el estándar de la industria: **Inno Setup**, el cual genera un instalador profesional con asistente gráfico (`GoogleDriveSync_Setup_x64.exe`), desinstalador automático en el Panel de Control, accesos directos e icono multi-resolución.

### Opción A: Compilar en una máquina con Windows (Script automatizado)
En tu equipo o máquina virtual con Windows:
1. Clona o copia la carpeta del proyecto.
2. Abre la consola (`CMD` o `PowerShell`) dentro de la carpeta.
3. Ejecuta el script:
   ```cmd
   scripts\build_windows.bat
   ```
4. El script se encarga de:
   * Crear el entorno virtual e instalar las dependencias (`PySide6`, `watchdog`, `google-api-python-client`, `keyring`).
   * Compilar el binario optimizado con `pyinstaller gdrive_sync_windows.spec`.
   * Invocar a Inno Setup (`ISCC.exe scripts\installer.iss`).
   * Generar el instalador final en:  
     `dist\GoogleDriveSync_Setup_x64.exe`

> **Nota:** Puedes descargar **Inno Setup** gratuitamente desde [jrsoftware.org](https://jrsoftware.org/isdl.php).

---

### Opción B: Compilación automática en la nube (GitHub Actions)
Si estás en Linux y no quieres usar una máquina Windows para compilar:
1. El proyecto ya incluye el flujo configurado en `.github/workflows/build-windows.yml`.
2. Sube el código a tu repositorio de GitHub:
   ```bash
   git add .
   git commit -m "Compilar instalador Windows"
   git push
   ```
3. En GitHub, ve a la pestaña **Actions > Build Windows Installer**.
4. Al finalizar la ejecución (toma ~2 minutos), descarga el archivo compilado `GoogleDriveSync-Windows-Installer` que contiene el ejecutable `GoogleDriveSync_Setup_x64.exe` listo para distribuir.

---

### Qué incluye el instalador de Windows:
* Asistente de instalación en español e inglés.
* Selección de ruta de instalación (por defecto `C:\Program Files\GoogleDriveSync`).
* Acceso directo en el **Menú Inicio** y en el **Escritorio**.
* Casilla opcional: *"Iniciar Google Drive Sync automáticamente al iniciar Windows"* (añade entrada en el registro `HKCU\...\Run`).
* Desinstalador completo registrado en **Configuración de Windows > Aplicaciones instaladas** (o Panel de Control).
* Icono multi-tamaño incrustado en el ejecutable (`assets/gdrive-sync.ico`).


## 🧪 Ejecución de Pruebas Unitarias

Para comprobar que todos los componentes (Base de datos SQLite, Reconciliador, Watcher, Queue y UI) funcionan correctamente:
```bash
.venv/bin/python3 -m unittest discover tests
```
Resultado: **15 pruebas completadas con éxito en ~1.5 segundos**.
