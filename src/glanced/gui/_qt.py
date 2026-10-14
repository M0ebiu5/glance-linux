"""The one `QApplication` each of glance's short-lived Qt dialogs needs.

Gives it a stable Wayland app_id (`glance`) via `setDesktopFileName` before
construction. Without this, Qt falls back to the interpreter's own basename
(`python3` for every Python GUI script on the system) — useless for a
compositor window rule to float on. A Hyprland `windowrulev2` matched on the
window *title* instead was tried and does not reliably work here: Qt's
`xdg_toplevel.set_title` appears to reach the compositor after the window
has already mapped, so a rule evaluated at map time never sees it, while the
app_id (`set_app_id`) is available in time. See the "Autotype" section of
the README.
"""

from __future__ import annotations

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

APP_ID = "glance"


def app() -> QApplication:
    instance = QApplication.instance()
    if instance is None:
        QGuiApplication.setDesktopFileName(APP_ID)
        instance = QApplication([])
    return instance
