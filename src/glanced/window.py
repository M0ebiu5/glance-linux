"""Which window has focus, for `glancectl autotype`.

Hyprland only, via `hyprctl -j activewindow` — this project runs on a
wlroots/Hyprland desktop (see the Omarchy plugin) and there is no portable
"focused window" query across compositors. A missing or failing `hyprctl`
degrades to "no window", not an exception: `glancectl autotype` treats that
the same as nothing being focused.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class ActiveWindow:
    window_class: str
    title: str


def active_window() -> Optional[ActiveWindow]:
    try:
        result = subprocess.run(
            ["hyprctl", "-j", "activewindow"],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        # An empty workspace prints an empty string, not JSON.
        return None
    window_class = data.get("class")
    if not window_class:
        return None
    return ActiveWindow(window_class=window_class, title=data.get("title") or "")
