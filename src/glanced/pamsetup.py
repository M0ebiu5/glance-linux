"""`glancectl setup-pam` — wire pam_glance into the lock screen, and only there.

Omarchy has had two lock screens, and both talk PAM:

* **hyprlock** — `/etc/pam.d/hyprlock`. Auth runs when the user presses
  Enter. With `ignore_empty_input = false` in hyprlock.conf, an empty Enter
  is enough to trigger a face scan.
* **The Omarchy shell lock** (Quickshell) — `/etc/pam.d/omarchy-lock-password`
  for the typed password, and, only when a fingerprint is enrolled,
  `/etc/pam.d/omarchy-lock-fingerprint`, which the shell starts *by itself*
  the moment the screen locks and retries until it succeeds. The shell drops
  an empty password before it reaches PAM, so on the password stack a face
  scan needs any character plus Enter.

Two placements, then:

* **on demand** (default): `auth sufficient pam_glance.so` at the top of the
  password stack(s). The camera only runs when you ask. This is Howdy's model.
* **hands-free** (`--hands-free`): the same line ahead of `pam_fprintd.so` in
  the shell's fingerprint stack. The shell scans your face as soon as it
  locks and again after every fingerprint timeout, so the camera cycles for
  as long as the screen stays locked. Needs an enrolled fingerprint, because
  that is what makes the shell run the stack at all.

A third line, on the password stacks: `auth [default=ignore] pam_glance.so
capture` right after `pam_unix.so`. PAM only reaches it when the password was
wrong — a right one jumps past it — and it asks the daemon for a photo of
whoever is at the camera (see `intruder.py`). Inserting a line under a
`[success=N]` jump moves where that jump lands, so every jump that crosses it
is lengthened by one, and shortened again on removal; otherwise a correct
password would land on `pam_faillock authfail` and lock you out.
`--no-photos` leaves this line out.

Every edit is idempotent, keeps a `.glance-backup` beside the file, and goes
through `sudo` one file at a time so the terminal shows exactly what is being
touched. `--remove` strips the line from every stack again.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

PAM_DIR = Path("/etc/pam.d")
MODULE = Path("/usr/lib/security/pam_glance.so")
MODULE_LINE = "auth       sufficient                  pam_glance.so"
CAPTURE_LINE = "auth       [default=ignore]            pam_glance.so capture"

#: In the request the module sends for a photo. A module built before capture
#: existed ignores the argument and would run a whole face scan after every
#: wrong password instead, so the line is only added once this is present.
CAPTURE_MARKER = b'"verb": "capture"'

HYPRLOCK = PAM_DIR / "hyprlock"
SHELL_PASSWORD = PAM_DIR / "omarchy-lock-password"
SHELL_FINGERPRINT = PAM_DIR / "omarchy-lock-fingerprint"


def _lines(path: Path) -> list[str]:
    try:
        return path.read_text().splitlines() if path.exists() else []
    except OSError:
        return []


def _is_capture(line: str) -> bool:
    return "pam_glance.so" in line and "capture" in line.split("pam_glance.so", 1)[1].split()


def _mentioned(path: Path) -> bool:
    return any("pam_glance.so" in line for line in _lines(path))


def _wired(path: Path) -> bool:
    """Face unlock is in this stack (the capture line alone does not count)."""
    return any("pam_glance.so" in line and not _is_capture(line) for line in _lines(path))


def _capture_wired(path: Path) -> bool:
    return any(_is_capture(line) for line in _lines(path))


def module_captures() -> bool:
    try:
        return CAPTURE_MARKER in MODULE.read_bytes()
    except OSError:
        return False


def status() -> dict:
    """What the status socket reports, and what the plugin renders."""
    hyprlock, password, fingerprint = _wired(HYPRLOCK), _wired(SHELL_PASSWORD), _wired(SHELL_FINGERPRINT)
    return {
        "module": MODULE.exists(),
        "hyprlock": hyprlock,
        "shellPassword": password,
        "shellFingerprint": fingerprint,
        "wired": hyprlock or password or fingerprint,
        "photos": _capture_wired(HYPRLOCK) or _capture_wired(SHELL_PASSWORD),
    }


# --- editing ------------------------------------------------------------------


def _insert_on_demand(text: str) -> str:
    """Put the module line before the first `auth` line, after any header comments."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() and not line.lstrip().startswith("#"):
            lines.insert(index, MODULE_LINE)
            break
    else:
        lines.append(MODULE_LINE)
    return "\n".join(lines) + "\n"


def _insert_before_fprintd(text: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if "pam_fprintd.so" in line and not line.lstrip().startswith("#"):
            lines.insert(index, MODULE_LINE)
            break
    else:
        return _insert_on_demand(text)
    return "\n".join(lines) + "\n"


_AUTH = re.compile(r"^\s*-?auth\s")
_CONTROL = re.compile(r"\[([^\]]*)\]")
_JUMP = re.compile(r"(\w+)=(\d+)")


def _auth_rows(lines: list[str]) -> list[int]:
    """Indices of the auth lines: the only ones an auth jump counts."""
    return [index for index, line in enumerate(lines) if _AUTH.match(line)]


def _retarget(lines: list[str], position: int, delta: int) -> None:
    """Keep every `[value=N]` jump landing on the same line when an auth line
    is inserted at (delta=+1) or removed from (delta=-1) auth position
    `position`. A jump of N from auth line i lands on auth line i+N+1."""
    for ordinal, index in enumerate(_auth_rows(lines)[:position]):

        def adjust(match: re.Match) -> str:
            lands = ordinal + int(match.group(2)) + 1
            crosses = lands >= position if delta > 0 else lands > position
            return f"{match.group(1)}={int(match.group(2)) + delta if crosses else match.group(2)}"

        lines[index] = _CONTROL.sub(lambda c: "[" + _JUMP.sub(adjust, c.group(1)) + "]", lines[index], count=1)


def _insert_capture(text: str) -> Optional[str]:
    """Put the capture line right after `pam_unix.so`, where only a wrong
    password reaches it. None when the stack has no pam_unix line of its own
    (it `include`s another stack, whose own failure handling would end the
    conversation before a line here ran)."""
    lines = text.splitlines()
    rows = _auth_rows(lines)
    for position, index in enumerate(rows):
        if "pam_unix.so" in lines[index] and not lines[index].lstrip().startswith("#"):
            _retarget(lines, position + 1, +1)
            lines.insert(index + 1, CAPTURE_LINE)
            return "\n".join(lines) + "\n"
    return None


def _strip(text: str) -> str:
    lines = text.splitlines(keepends=True)
    while True:
        rows = _auth_rows(lines)
        found = next(
            ((position, index) for position, index in enumerate(rows) if "pam_glance.so" in lines[index]), None
        )
        if found is None:
            # Not an auth line (or not one at all): drop it, nothing jumps over it.
            remaining = [line for line in lines if "pam_glance.so" not in line]
            return "".join(remaining)
        position, index = found
        del lines[index]
        _retarget(lines, position, -1)


def _sudo(*command: str, stdin: Optional[str] = None) -> None:
    subprocess.run(["sudo", *command], input=stdin, text=True, check=True)


def _write(path: Path, content: str, log) -> None:
    backup = path.with_name(path.name + ".glance-backup")
    if not backup.exists():
        _sudo("cp", "-p", str(path), str(backup))
        log(f"  backup: {backup}")
    _sudo("tee", str(path), stdin=content)
    log(f"  wrote:  {path}")


def _ensure_module(repo_pam_dir: Optional[Path], log) -> bool:
    buildable = repo_pam_dir is not None and (repo_pam_dir / "pam_glance.c").exists()
    if MODULE.exists():
        if not module_captures() and buildable:
            # Installed before failed-password photos existed: rebuild, or the
            # capture line would run a full face scan after every wrong password.
            log("updating pam_glance.so (it predates failed-attempt photos) ...")
            subprocess.run(["make", "-C", str(repo_pam_dir)], check=True)
            _sudo("make", "-C", str(repo_pam_dir), "install")
        return True
    if not buildable:
        log(f"{MODULE} is missing and no source checkout to build it from (see pam/README.md)")
        return False
    log("building pam_glance.so ...")
    subprocess.run(["make", "-C", str(repo_pam_dir)], check=True)
    _sudo("make", "-C", str(repo_pam_dir), "install")
    return MODULE.exists()


def setup(
    *,
    hands_free: bool = False,
    remove: bool = False,
    photos: bool = True,
    repo_pam_dir: Optional[Path] = None,
    log=print,
) -> int:
    if remove:
        touched = 0
        for path in (HYPRLOCK, SHELL_PASSWORD, SHELL_FINGERPRINT):
            if _mentioned(path):
                _write(path, _strip(path.read_text()), log)
                touched += 1
        log(f"removed pam_glance from {touched} stack(s); the module file itself is left in place")
        return 0

    if not _ensure_module(repo_pam_dir, log):
        return 1
    if photos and not module_captures():
        log(f"{MODULE} cannot take failed-password photos (it predates them); skipping that line")
        photos = False

    # A fresh Omarchy that has never run its lock setup has no PAM file for the
    # shell lock at all — which also means the shell lock cannot lock. Its own
    # helper creates both files, and the fingerprint one only if a print is
    # enrolled, so defer to it rather than re-implement the policy.
    if shutil.which("omarchy-apply-lock") and not SHELL_PASSWORD.exists():
        log("shell lock has no PAM configuration yet; running omarchy-apply-lock ...")
        _sudo("omarchy-apply-lock")

    wired_any = False
    if hands_free:
        if not SHELL_FINGERPRINT.exists():
            log(
                "hands-free needs the Omarchy shell lock with an enrolled fingerprint "
                "(the shell only runs that stack automatically when one exists). "
                "Falling back to on-demand."
            )
        elif _wired(SHELL_FINGERPRINT):
            log(f"already wired: {SHELL_FINGERPRINT}")
            wired_any = True
        else:
            _write(SHELL_FINGERPRINT, _insert_before_fprintd(SHELL_FINGERPRINT.read_text()), log)
            log("hands-free: the shell scans your face as soon as it locks, then falls back to fingerprint, and repeats")
            wired_any = True

    for path, hint in (
        (SHELL_PASSWORD, "shell lock: type any character and press Enter to scan"),
        (HYPRLOCK, "hyprlock: press Enter to scan (set `ignore_empty_input = false` in hyprlock.conf so an empty Enter counts)"),
    ):
        if not path.exists():
            continue
        original = text = path.read_text()
        # Hands-free already covers the shell lock; leaving the password
        # stack's face line out keeps typing a password from waiting on the camera.
        wants_face = not (hands_free and path is SHELL_PASSWORD and _wired(SHELL_FINGERPRINT))
        if wants_face:
            if _wired(path):
                log(f"already wired: {path}")
            else:
                text = _insert_on_demand(text)
            log(f"  {hint}")
            wired_any = True
        if photos:
            if _capture_wired(path):
                log(f"  failed-password photos: already on in {path}")
            else:
                with_capture = _insert_capture(text)
                if with_capture is None:
                    log(f"  failed-password photos: {path} has no pam_unix.so line of its own; skipped")
                else:
                    text = with_capture
                    log(f"  failed-password photos: on in {path}")
        if text != original:
            _write(path, text, log)

    if not wired_any:
        log("no lock screen PAM stack found to wire (expected /etc/pam.d/hyprlock or omarchy-lock-password)")
        return 1
    log("\nface unlock is wired. Keep this terminal open and test the lock screen now; "
        "`glancectl setup-pam --remove` undoes it.")
    return 0
