"""
OS integration module (KDE Dolphin, Autostart).
"""

from .autostart import is_autostart_enabled, set_autostart
from .kde_dolphin import install_dolphin_service_menu, uninstall_dolphin_service_menu

__all__ = [
    "install_dolphin_service_menu",
    "is_autostart_enabled",
    "set_autostart",
    "uninstall_dolphin_service_menu",
]
