"""The "save a new autotype password" prompt, for `glancectl autotype` run
from a hotkey with no terminal attached.

Structurally the same dialog as `passphrase.py`'s, with a label field, a
match-title field and a "press Enter after typing" checkbox added, since the
two things this asks for — a passphrase, and a site password to remember —
never appear together.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from .enroll_window import ACCENT, DANGER, SURFACE, TEXT_PRIMARY, TEXT_SECONDARY

_APP = None


class SecretDialog(QDialog):
    """Password + label + title-match + send-Enter fields; accepts only a
    non-empty, matching password pair."""

    def __init__(self, *, app_hint: str, window_title: str = "", error: str = "") -> None:
        super().__init__()
        self.setWindowTitle("Glance — save a password")
        self.setStyleSheet(f"background: {SURFACE.name()}; color: {TEXT_PRIMARY.name()};")
        self.setMinimumWidth(440)
        self.setModal(True)

        self.value: Optional[tuple[str, str, str, bool]] = None

        title = QLabel("No saved password for this window", self)
        title.setFont(QFont(self.font().family(), 15, QFont.Medium))

        # Class and title, up front and in that order of prominence — the
        # class alone (e.g. "google-chrome") is the same for every site a
        # browser has open, so the title is the part that actually says what
        # this password is for.
        window_info = QLabel(f"{app_hint}\n“{window_title or '(no title)'}”", self)
        window_info.setWordWrap(True)
        window_info.setFont(QFont(self.font().family(), 12))

        detail = QLabel(
            "Type it once and Glance will remember it for this app, gated on a "
            "face scan each time — see the README before saving anything you "
            "would not want typed by software.",
            self,
        )
        detail.setWordWrap(True)
        detail.setFont(QFont(self.font().family(), 11))
        detail.setStyleSheet(f"color: {TEXT_SECONDARY.name()};")

        field_style = (
            f"QLineEdit {{ background: #2a2a2a; color: {TEXT_PRIMARY.name()}; "
            f"border: 1px solid #3a3a3a; border-radius: 6px; padding: 8px; }}"
            f"QLineEdit:focus {{ border-color: {ACCENT.name()}; }}"
        )

        self.label_field = QLineEdit(self)
        self.label_field.setText(app_hint)
        self.label_field.setPlaceholderText("Label")
        self.label_field.setStyleSheet(field_style)

        title_hint_label = QLabel(
            "Only autotype when the window title contains (many apps, like a "
            "browser, share one window class across every site — this is what "
            "tells them apart; leave blank to match every window of this class):",
            self,
        )
        title_hint_label.setWordWrap(True)
        title_hint_label.setFont(QFont(self.font().family(), 10))
        title_hint_label.setStyleSheet(f"color: {TEXT_SECONDARY.name()};")

        self.title_hint = QLineEdit(self)
        self.title_hint.setText(window_title)
        self.title_hint.setPlaceholderText("Title contains (optional)")
        self.title_hint.setStyleSheet(field_style)

        self.secret = QLineEdit(self)
        self.secret.setEchoMode(QLineEdit.Password)
        self.secret.setPlaceholderText("Password")
        self.secret.setStyleSheet(field_style)

        self.confirm = QLineEdit(self)
        self.confirm.setEchoMode(QLineEdit.Password)
        self.confirm.setPlaceholderText("Confirm password")
        self.confirm.setStyleSheet(field_style)

        self.send_enter = QCheckBox("Press Enter after typing", self)
        self.send_enter.setStyleSheet(f"color: {TEXT_SECONDARY.name()};")

        self.problem = QLabel(error, self)
        self.problem.setWordWrap(True)
        self.problem.setStyleSheet(f"color: {DANGER.name()};")
        self.problem.setVisible(bool(error))

        cancel = QPushButton("Cancel", self)
        cancel.setStyleSheet(
            f"QPushButton {{ color: {TEXT_SECONDARY.name()}; background: transparent; "
            f"border: 1px solid #3a3a3a; border-radius: 6px; padding: 8px 16px; }}"
        )
        cancel.clicked.connect(self.reject)

        self.accept_button = QPushButton("Save && type", self)
        self.accept_button.setDefault(True)
        self.accept_button.setStyleSheet(
            f"QPushButton {{ color: {TEXT_PRIMARY.name()}; background: {ACCENT.name()}; "
            f"border: none; border-radius: 6px; padding: 8px 18px; }}"
        )
        self.accept_button.clicked.connect(self.try_accept)
        self.secret.returnPressed.connect(self.try_accept)
        self.confirm.returnPressed.connect(self.try_accept)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(self.accept_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(window_info)
        layout.addSpacing(6)
        layout.addWidget(detail)
        layout.addSpacing(6)
        layout.addWidget(self.label_field)
        layout.addWidget(self.secret)
        layout.addWidget(self.confirm)
        layout.addSpacing(6)
        layout.addWidget(title_hint_label)
        layout.addWidget(self.title_hint)
        layout.addWidget(self.send_enter)
        layout.addWidget(self.problem)
        layout.addSpacing(6)
        layout.addLayout(buttons)

        self.secret.setFocus()

    def try_accept(self) -> None:
        secret = self.secret.text()
        if not secret:
            self._complain("The password cannot be empty.")
            return
        if self.confirm.text() != secret:
            self._complain("The two passwords do not match.")
            self.confirm.clear()
            self.confirm.setFocus()
            return
        label = self.label_field.text().strip()
        title_hint = self.title_hint.text().strip()
        self.value = (secret, label, title_hint, self.send_enter.isChecked())
        self.accept()

    def _complain(self, message: str) -> None:
        self.problem.setText(message)
        self.problem.setVisible(True)


def ask(*, app_hint: str, window_title: str = "", error: str = "") -> Optional[tuple[str, str, str, bool]]:
    """Show the dialog; return `(secret, label, title_hint, send_enter)`, or
    None if the user cancelled."""
    global _APP
    from ._qt import app as _qapp

    _APP = _qapp()
    dialog = SecretDialog(app_hint=app_hint, window_title=window_title, error=error)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    dialog.exec()
    return dialog.value
