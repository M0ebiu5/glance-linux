"""`window.active_window()` against a faked `hyprctl`. Failure of any kind
degrades to "no window" rather than an exception — `glancectl autotype`
treats that the same as nothing being focused."""

from __future__ import annotations

import subprocess

import pytest

from glanced import window as window_module


class _Result:
    def __init__(self, stdout: str, returncode: int = 0) -> None:
        self.stdout = stdout
        self.returncode = returncode


def test_parses_class_and_title(monkeypatch):
    monkeypatch.setattr(
        window_module.subprocess,
        "run",
        lambda *a, **k: _Result('{"class": "firefox", "title": "Example — Mozilla Firefox"}'),
    )
    active = window_module.active_window()
    assert active == window_module.ActiveWindow(window_class="firefox", title="Example — Mozilla Firefox")


def test_missing_hyprctl_returns_none(monkeypatch):
    def _raise(*a, **k):
        raise FileNotFoundError()

    monkeypatch.setattr(window_module.subprocess, "run", _raise)
    assert window_module.active_window() is None


def test_empty_workspace_returns_none(monkeypatch):
    # hyprctl prints an empty string, not JSON, when nothing is focused.
    monkeypatch.setattr(window_module.subprocess, "run", lambda *a, **k: _Result(""))
    assert window_module.active_window() is None


def test_malformed_json_returns_none(monkeypatch):
    monkeypatch.setattr(window_module.subprocess, "run", lambda *a, **k: _Result("{not json"))
    assert window_module.active_window() is None


def test_nonzero_exit_returns_none(monkeypatch):
    monkeypatch.setattr(window_module.subprocess, "run", lambda *a, **k: _Result("{}", returncode=1))
    assert window_module.active_window() is None


def test_timeout_returns_none(monkeypatch):
    def _raise(*a, **k):
        raise subprocess.TimeoutExpired(cmd="hyprctl", timeout=2.0)

    monkeypatch.setattr(window_module.subprocess, "run", _raise)
    assert window_module.active_window() is None


def test_missing_title_defaults_to_empty_string(monkeypatch):
    monkeypatch.setattr(window_module.subprocess, "run", lambda *a, **k: _Result('{"class": "foot"}'))
    active = window_module.active_window()
    assert active == window_module.ActiveWindow(window_class="foot", title="")
