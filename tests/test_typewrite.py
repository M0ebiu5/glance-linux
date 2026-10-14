"""`typewrite.type_text` — the one place a vault secret leaves the process.
What matters most: it goes over `wtype`'s stdin, never argv, so it never
sits in `ps` output or `/proc/<pid>/cmdline`."""

from __future__ import annotations

import subprocess

import pytest

from glanced import typewrite


class _Calls:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, args, **kwargs):
        self.calls.append({"args": args, **kwargs})
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")


def test_secret_goes_over_stdin_not_argv(monkeypatch):
    calls = _Calls()
    monkeypatch.setattr(typewrite.subprocess, "run", calls)
    typewrite.type_text("s3cr3t")
    assert len(calls.calls) == 1
    call = calls.calls[0]
    assert call["args"] == ["wtype", "-"]
    assert call["input"] == "s3cr3t"
    assert "s3cr3t" not in call["args"]


def test_send_enter_sends_a_second_key_event(monkeypatch):
    calls = _Calls()
    monkeypatch.setattr(typewrite.subprocess, "run", calls)
    typewrite.type_text("s3cr3t", send_enter=True)
    assert len(calls.calls) == 2
    assert calls.calls[1]["args"] == ["wtype", "-k", "Return"]


def test_no_send_enter_by_default(monkeypatch):
    calls = _Calls()
    monkeypatch.setattr(typewrite.subprocess, "run", calls)
    typewrite.type_text("s3cr3t")
    assert len(calls.calls) == 1


def test_missing_wtype_raises_typing_error(monkeypatch):
    def _raise(*a, **k):
        raise FileNotFoundError()

    monkeypatch.setattr(typewrite.subprocess, "run", _raise)
    with pytest.raises(typewrite.TypingError):
        typewrite.type_text("s3cr3t")


def test_wtype_failure_raises_typing_error(monkeypatch):
    def _raise(*a, **k):
        raise subprocess.CalledProcessError(1, ["wtype", "-"], stderr="no compositor")

    monkeypatch.setattr(typewrite.subprocess, "run", _raise)
    with pytest.raises(typewrite.TypingError):
        typewrite.type_text("s3cr3t")
