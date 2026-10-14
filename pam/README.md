# pam_glance

The PAM half of the unlock path. It connects to your running `glanced` over
the auth socket in `$XDG_RUNTIME_DIR/glance/` and turns the daemon's verdict
into a PAM result. All of the vision, liveness and recognition is in the
daemon; this module is about 150 lines and does none of it.

## The short version

```bash
glancectl setup-pam            # builds + installs the module if needed, edits the lock stacks (sudo)
glancectl setup-pam --remove   # undo
```

**Keep a root shell open in another terminal while you test.** A broken PAM
stack can lock you out. Every file `setup-pam` touches gets a
`.glance-backup` beside it.

## Where it goes, and why only there

The module refuses to run for any account other than the one the calling
process runs as, and refuses entirely in a setuid context. So it cannot be
made to authorize `sudo`, `su`, or a login manager; it exists for the lock
screen, where the process is already you and the only question is whether to
let you back in.

Omarchy has two lock screens, and `setup-pam` handles both:

| Lock screen | PAM file | How a scan is triggered |
|---|---|---|
| Omarchy shell lock (Quickshell, `omarchy system lock`) | `/etc/pam.d/omarchy-lock-password` | type any character, press Enter (the shell drops an empty password before PAM sees it) |
| Omarchy shell lock, `--hands-free` | `/etc/pam.d/omarchy-lock-fingerprint` | automatically, the moment the screen locks, and again after every fingerprint timeout |
| hyprlock | `/etc/pam.d/hyprlock` | press Enter; set `ignore_empty_input = false` in `~/.config/hypr/hyprlock.conf` so an empty Enter counts |

`sufficient` means a face success ends the stack; any failure drops through to
the password (or fingerprint) exactly as before.

On the password stacks `setup-pam` also adds a second line right after
`pam_unix.so`:

```
auth       [success=2 default=bad]     pam_unix.so try_first_pass nullok   # was success=1
auth       [default=ignore]            pam_glance.so capture
auth       [default=die]               pam_faillock.so authfail ...
```

Only a wrong password reaches it. It asks the daemon to photograph whoever is
at the camera and returns `PAM_IGNORE` within two seconds whatever happens.
Every `success=N` jump that crosses the new line is lengthened by one so a
right password still lands where it did; `--remove` shortens them again.
`--no-photos` skips this line. An installed module older than this feature
is rebuilt first, because an old module ignores `capture` and would run a
face scan instead.

### On demand vs hands-free

The default is on demand: the camera only runs when you press Enter. That is
Howdy's model and the one that is kind to your camera LED and battery.

`--hands-free` puts the module ahead of `pam_fprintd.so` in the shell's
fingerprint stack, because that is the stack the shell starts *by itself* when
it locks and retries until it succeeds. You get a face scan with no keypress —
and the camera cycling for as long as the screen stays locked, alternating
with the 30-second fingerprint wait. It needs an enrolled fingerprint, since
that is what makes the shell run the stack at all.

The right long-term answer is a dedicated face PAM context in Omarchy's lock,
the way it has one for fingerprint. That is an upstream change to
`shell/plugins/lock/Service.qml`, not something a plugin can do.

### A fresh Omarchy

If `/etc/pam.d/omarchy-lock-password` does not exist yet, the shell lock
cannot lock at all (`omarchy-shell lock status` shows `"passwordPam":false`).
`setup-pam` runs Omarchy's own `omarchy-apply-lock` first, which creates it.

## Timing

A typed password waits for the face scan ahead of it. The daemon caps that:
no face in view for 3 seconds ends the scan (`--no-face-timeout`), and a scan
never runs longer than 8 seconds (`--scan-timeout`). In practice a recognised
face unlocks in about two seconds, before you would have finished typing.

## Options

| arg | meaning |
|---|---|
| `debug` | log why the module declined, to the auth log |
| `timeout=N` | seconds to wait for the daemon (default 20) |
| `capture` | ask for a failed-attempt photo instead of a scan; always `PAM_IGNORE` |

## Build by hand

```bash
sudo pacman -S --needed pam base-devel
make -C pam && sudo make -C pam install   # -> /usr/lib/security/pam_glance.so
```

## Check it without locking

```bash
glancectl authenticate            # the exact request the module sends
glancectl status                  # includes a "lock screen:" line
journalctl --user -u glanced -f   # what the daemon saw
journalctl -t omarchy-shell -f    # or hyprlock: what PAM said
```
