"""Deliver a vault secret into the focused window, via `wtype`.

`wtype` types over Wayland's virtual-keyboard protocol — no root daemon,
unlike `ydotool`'s `uinput` approach. The secret is always piped over `wtype
-`'s stdin, never passed as an argument: an argument would sit in `ps` output
and `/proc/<pid>/cmdline` for as long as the process runs.
"""

from __future__ import annotations

import subprocess

_RUN_TIMEOUT = 10.0


class TypingError(RuntimeError):
    pass


def type_text(secret: str, *, send_enter: bool = False) -> None:
    try:
        subprocess.run(
            ["wtype", "-"],
            input=secret,
            text=True,
            capture_output=True,
            timeout=_RUN_TIMEOUT,
            check=True,
        )
    except FileNotFoundError as error:
        raise TypingError("wtype is not installed (pacman -S wtype)") from error
    except subprocess.TimeoutExpired as error:
        raise TypingError("wtype timed out") from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or "").strip()
        raise TypingError(f"wtype failed: {detail or error}") from error

    if send_enter:
        try:
            subprocess.run(["wtype", "-k", "Return"], timeout=_RUN_TIMEOUT, check=True, capture_output=True)
        except (OSError, subprocess.SubprocessError) as error:
            raise TypingError(f"wtype failed to send Return: {error}") from error
