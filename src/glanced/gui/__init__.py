"""The enrollment window, and the passphrase prompt that precedes it.

Kept behind its own import so nothing in the daemon, the PAM path, or the
headless CLI ever pulls Qt in. `glancectl enroll --gui` is the only caller,
and a missing extra surfaces as an install hint rather than a traceback.
"""

from __future__ import annotations

from typing import Optional

_MISSING = (
    "the enrollment window needs PySide6: pip install 'glanced[gui]' "
    "(or run `glancectl enroll` without --gui)"
)


def ask_passphrase(*, confirm: bool, error: str = "") -> Optional[str]:
    """Prompt for the passphrase in a window; None if the user cancelled.

    For an enrollment started from a button rather than a prompt: there is no
    terminal for getpass, and argv is not a place for a secret.
    """
    try:
        from .passphrase import ask
    except ImportError as exc:  # pragma: no cover - depends on the extra
        raise ImportError(_MISSING) from exc
    return ask(confirm=confirm, error=error)


def ask_secret(
    *, app_hint: str, window_title: str = "", error: str = ""
) -> Optional[tuple[str, str, str, bool]]:
    """Prompt for a new vault password in a window; `(secret, label,
    title_hint, send_enter)`, or None if the user cancelled.

    For `glancectl autotype` run from a hotkey against an unknown window:
    there is no terminal, and no expectation of retyping the master
    passphrase just to save one more site password. The window's title is
    shown and editable — several apps (a browser, above all) share one
    window class across every site, so the title is what tells them apart.
    """
    try:
        from .secret import ask
    except ImportError as exc:  # pragma: no cover - depends on the extra
        raise ImportError(_MISSING) from exc
    return ask(app_hint=app_hint, window_title=window_title, error=error)


def ask_choice(*, prompt: str, options: list[tuple[str, str]]) -> Optional[str]:
    """Pick one of several saved vault entries in a window.

    `options` is a list of `(id, label)`; returns the chosen id, or None if
    the user cancelled. Used when `glancectl autotype` finds more than one
    saved password for a window class and there is no terminal to number a
    list in.
    """
    try:
        from PySide6.QtWidgets import QInputDialog

        from ._qt import app as _qapp
    except ImportError as exc:  # pragma: no cover - depends on the extra
        raise ImportError(_MISSING) from exc
    _qapp()
    labels = [label for _, label in options]
    choice, ok = QInputDialog.getItem(None, "Glance", prompt, labels, 0, False)
    if not ok or not choice:
        return None
    return options[labels.index(choice)][0]


def run_enrollment(**kwargs) -> tuple[list, list]:
    """Open the guided enrollment window; return `(embeddings, pose_names)`.

    See :mod:`glanced.gui.enroll_window` for the arguments.
    """
    try:
        from .enroll_window import run
    except ImportError as error:  # pragma: no cover - depends on the extra
        raise ImportError(_MISSING) from error
    return run(**kwargs)
