from setuptools import setup, find_packages

setup(
    name="mygdrivesync",
    version="0.1.0",
    description="MyGDriveSync: Dropbox-like cross-platform Google Drive selective synchronization client with Qt tray",
    author="Developer",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "PySide6>=6.5.0",
        "watchdog>=3.0.0",
        "google-api-python-client>=2.100.0",
        "google-auth-httplib2>=0.1.0",
        "google-auth-oauthlib>=1.0.0",
        "keyring>=24.0.0",
    ],
    entry_points={
        "gui_scripts": [
            "mygdrivesync=gdrive_sync.main:main",
            "gdrive-sync=gdrive_sync.main:main",
        ],
        "console_scripts": [
            "mygdrivesync-dolphin=gdrive_sync.integrations.kde_dolphin:main",
            "gdrive-sync-dolphin=gdrive_sync.integrations.kde_dolphin:main",
        ],
    },
)
