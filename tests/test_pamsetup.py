"""The PAM-stack edits, as pure text transforms; sudo never runs here."""

from __future__ import annotations

from glanced import pamsetup

HYPRLOCK = """# PAM configuration file for hyprlock
# the 'login' configuration file (see /etc/pam.d/login)

auth        include     login
"""

FINGERPRINT = """#%PAM-1.0
auth       required                    pam_fprintd.so
account    include                     system-local-login
"""


def test_on_demand_goes_before_the_first_auth_line():
    out = pamsetup._insert_on_demand(HYPRLOCK)
    lines = out.splitlines()
    assert lines[:2] == HYPRLOCK.splitlines()[:2]
    assert lines.index(pamsetup.MODULE_LINE) < lines.index("auth        include     login")


def test_hands_free_goes_before_fprintd():
    out = pamsetup._insert_before_fprintd(FINGERPRINT).splitlines()
    assert out[0] == "#%PAM-1.0"
    assert out[1] == pamsetup.MODULE_LINE
    assert "pam_fprintd.so" in out[2]


def test_strip_is_the_inverse():
    assert pamsetup._strip(pamsetup._insert_on_demand(HYPRLOCK)) == HYPRLOCK
    assert pamsetup._strip(pamsetup._insert_before_fprintd(FINGERPRINT)) == FINGERPRINT


def test_status_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(pamsetup, "MODULE", tmp_path / "pam_glance.so")
    monkeypatch.setattr(pamsetup, "HYPRLOCK", tmp_path / "hyprlock")
    monkeypatch.setattr(pamsetup, "SHELL_PASSWORD", tmp_path / "omarchy-lock-password")
    monkeypatch.setattr(pamsetup, "SHELL_FINGERPRINT", tmp_path / "omarchy-lock-fingerprint")
    assert pamsetup.status() == {
        "module": False, "hyprlock": False, "shellPassword": False, "shellFingerprint": False, "wired": False,
        "photos": False,
    }
    (tmp_path / "hyprlock").write_text(pamsetup._insert_on_demand(HYPRLOCK))
    assert pamsetup.status()["hyprlock"] is True
    assert pamsetup.status()["wired"] is True


# --- failed-password photos ---------------------------------------------------

SHELL_PASSWORD = """#%PAM-1.0
auth       required                    pam_faillock.so preauth silent deny=10 unlock_time=120
-auth      [success=2 default=ignore]  pam_systemd_home.so
auth       [success=1 default=bad]     pam_unix.so try_first_pass nullok
auth       [default=die]               pam_faillock.so authfail deny=10 unlock_time=120
auth       optional                    pam_permit.so
auth       required                    pam_env.so
auth       required                    pam_faillock.so authsucc
account    include                     system-local-login
"""


def _auth(text):
    return [line for line in text.splitlines() if line.lstrip().lstrip("-").startswith("auth")]


def test_capture_goes_right_after_pam_unix_and_jumps_still_land():
    out = pamsetup._insert_capture(SHELL_PASSWORD)
    auth = _auth(out)
    unix = next(i for i, line in enumerate(auth) if "pam_unix.so" in line)
    assert auth[unix + 1] == pamsetup.CAPTURE_LINE
    # A right password still skips authfail and lands on pam_permit; so does
    # a systemd-homed login. Only a wrong one falls through onto the capture.
    before, after = _auth(SHELL_PASSWORD), auth
    assert "success=2" in after[unix] and "success=3" in after[unix - 1]
    for module in ("pam_unix.so", "pam_systemd_home.so"):
        assert _jump_target(before, module) == _jump_target(after, module) == "pam_permit.so"
    assert "pam_faillock.so authfail" in auth[unix + 2]


def _jump_target(lines, module):
    import re

    for ordinal, line in enumerate(lines):
        if module in line:
            n = int(re.search(r"success=(\d+)", line).group(1))
            return lines[ordinal + n + 1].split()[2]
    raise AssertionError(module)


def test_capture_and_face_strip_back_to_the_original():
    both = pamsetup._insert_on_demand(pamsetup._insert_capture(SHELL_PASSWORD))
    assert both.splitlines()[1] == pamsetup.MODULE_LINE
    assert pamsetup._strip(both) == SHELL_PASSWORD
    assert pamsetup._strip(pamsetup._insert_capture(SHELL_PASSWORD)) == SHELL_PASSWORD


def test_capture_needs_its_own_pam_unix_line():
    assert pamsetup._insert_capture(HYPRLOCK) is None


def test_status_tells_face_from_capture(tmp_path, monkeypatch):
    monkeypatch.setattr(pamsetup, "MODULE", tmp_path / "pam_glance.so")
    monkeypatch.setattr(pamsetup, "HYPRLOCK", tmp_path / "hyprlock")
    monkeypatch.setattr(pamsetup, "SHELL_PASSWORD", tmp_path / "omarchy-lock-password")
    monkeypatch.setattr(pamsetup, "SHELL_FINGERPRINT", tmp_path / "omarchy-lock-fingerprint")
    (tmp_path / "omarchy-lock-password").write_text(pamsetup._insert_capture(SHELL_PASSWORD))
    assert pamsetup.status()["photos"] is True
    assert pamsetup.status()["wired"] is False


def test_module_capture_detection(tmp_path, monkeypatch):
    module = tmp_path / "pam_glance.so"
    monkeypatch.setattr(pamsetup, "MODULE", module)
    assert not pamsetup.module_captures()
    module.write_bytes(b"\0old module\0")
    assert not pamsetup.module_captures()
    module.write_bytes(b"\0" + pamsetup.CAPTURE_MARKER + b"\0")
    assert pamsetup.module_captures()
