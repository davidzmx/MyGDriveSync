@echo off
setlocal enabledelayedexpansion

REM =====================================================================
REM Script de compilacion y generacion de instalador para Windows
REM Ejecutar desde la raiz del proyecto en una terminal CMD de Windows
REM =====================================================================

echo =====================================================================
echo   Compilando Google Drive Sync para Windows
echo =====================================================================
echo.

REM 1. Verificar Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python no esta instalado o no se encuentra en el PATH.
    echo Descarga e instala Python desde https://www.python.org/
    exit /b 1
)

REM 2. Crear o activar entorno virtual
if not exist ".venv" (
    echo [1/4] Creando entorno virtual .venv...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

REM 3. Instalar dependencias
echo [2/4] Instalando dependencias necesarias...
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller pillow

REM 4. Generar icono si no existe
if not exist "assets\gdrive-sync.ico" (
    echo Generando icono assets\gdrive-sync.ico...
    python -c "from PIL import Image; from gdrive_sync.ui.icons import create_tray_icon; from PySide6.QtWidgets import QApplication; app=QApplication([]); icon=create_tray_icon('IDLE', 256); icon.pixmap(256, 256).save('assets/tmp.png'); img=Image.open('assets/tmp.png'); img.save('assets/gdrive-sync.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"
)

REM 5. Compilar binarios con PyInstaller
echo [3/4] Compilando binarios ejecutables con PyInstaller...
pyinstaller gdrive_sync_windows.spec --noconfirm

if not exist "dist\MyGDriveSync\MyGDriveSync.exe" (
    echo [ERROR] La compilacion con PyInstaller fallo.
    exit /b 1
)

echo.
echo [EXITO] Binario ejecutable generado en: dist\MyGDriveSync\MyGDriveSync.exe
echo.

REM 6. Buscar Inno Setup Compiler para generar el instalador .exe
echo [4/4] Buscando Inno Setup Compiler para generar el asistente de instalacion...

set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
) else if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
) else (
    where ISCC.exe >nul 2>nul
    if !ERRORLEVEL! equ 0 set "ISCC=ISCC.exe"
)

if defined ISCC (
    echo Compilando instalador Setup con Inno Setup...
    "%ISCC%" scripts\installer.iss
    echo.
    echo =====================================================================
    echo   [LISTO] Instalador de Windows generado con exito:
    echo   Ubicacion: dist\MyGDriveSync_Setup_x64.exe
    echo =====================================================================
) else (
    echo.
    echo [AVISO] Inno Setup 6 no fue detectado en las rutas habituales.
    echo Puedes descargar Inno Setup gratuitamente desde:
    echo   https://jrsoftware.org/isdl.php
    echo Y luego compilar el instalador ejecutando:
    echo   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" scripts\installer.iss
    echo.
    echo Mientras tanto, puedes usar directamente la carpeta portable:
    echo   dist\MyGDriveSync\
)

pause
