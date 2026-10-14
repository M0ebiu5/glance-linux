"""Photos of failed unlock attempts.

When a lock screen refuses someone, the daemon keeps a picture of who was
there: the last frame with a face in it when a *face* scan fails, or a fresh
grab from the camera when a typed *password* fails (pam_glance's `capture`
line, which `glancectl setup-pam` puts right after `pam_unix.so`).

The photos are the full camera frame as a JPEG, unmirrored — evidence, not a
selfie view. They live in `~/.local/share/glance/intruders/`, a 0700
directory, each file 0600, and only the newest `KEEP` are kept so a looping
hands-free lock screen cannot fill the disk. `glancectl intruders` lists
them; `--no-intruder-photos` on the daemon turns the whole thing off.

This is the one place the daemon writes a camera frame to *disk* rather than
to tmpfs. That is the point of it, and the reason it can be switched off.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

import numpy as np

from . import paths

#: How many photos to keep. Older ones are deleted as new ones are written.
KEEP = 100

JPEG_QUALITY = 85


def save(
    native_rgb: np.ndarray,
    reason: str,
    *,
    directory: Optional[Path] = None,
    keep: int = KEEP,
    now: Optional[float] = None,
) -> Path:
    """Write one photo and prune old ones. Returns the new file's path."""
    import cv2

    directory = Path(directory or paths.INTRUDER_DIR)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)  # mkdir's mode is masked, and the dir may predate us

    ok, buffer = cv2.imencode(
        ".jpg", cv2.cvtColor(native_rgb, cv2.COLOR_RGB2BGR), [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
    )
    if not ok:
        raise RuntimeError("JPEG encode failed")

    now = time.time() if now is None else now
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now)) + f"-{int(now * 1000) % 1000:03d}"
    safe_reason = "".join(c if c.isalnum() or c == "_" else "-" for c in reason) or "failed"
    path = directory / f"{stamp}-{safe_reason}.jpg"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(buffer.tobytes())

    prune(directory, keep)
    return path


def photos(directory: Optional[Path] = None) -> list[Path]:
    """Every photo, oldest first. The names sort by time."""
    directory = Path(directory or paths.INTRUDER_DIR)
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir() if p.suffix == ".jpg" and p.is_file())


def prune(directory: Optional[Path] = None, keep: int = KEEP) -> None:
    existing = photos(directory)
    for path in existing[: max(0, len(existing) - keep)]:
        path.unlink(missing_ok=True)


def clear(directory: Optional[Path] = None) -> int:
    existing = photos(directory)
    for path in existing:
        path.unlink(missing_ok=True)
    return len(existing)
