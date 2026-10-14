"""The autotype vault: a small encrypted store of application passwords.

This is a deliberately different feature from `store.py`. The enrollment
store exists so this project never has to keep a password; the vault is the
opposite trade-off, made on purpose and only for logins the user has judged
low-value — see the "Autotype" section of the README and the matching entry
in SECURITY.md before wiring anything sensitive into it.

The file format mirrors `store.py`'s exactly (salt || nonce ||
AES-256-GCM(JSON), scrypt-derived key) and reuses its key derivation so the
two never drift apart on KDF cost parameters, but keeps its own save/load and
its own passphrase-protected file: a wrong guess against the vault can never
touch face data, and vice versa. In practice the user sets the same
passphrase for both, since `glanced` arms them together (see `daemon.py`).
"""

from __future__ import annotations

import json
import os
import secrets
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from .store import NONCE_BYTES, SALT_BYTES, derive_key

DEFAULT_VAULT_PATH = Path(
    os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
) / "glance" / "vault.bin"


@dataclass
class VaultEntry:
    id: str
    #: The window class `hyprctl activewindow` reports (e.g. "firefox"). The
    #: primary match key — see `VaultStore.find`.
    window_class: str
    #: A substring of the window title, used only to pick between several
    #: entries that share a window class.
    title_hint: str = ""
    label: str = ""
    secret: str = ""
    send_enter: bool = False
    created_at: float = 0.0


@dataclass
class VaultStore:
    entries: list[VaultEntry] = field(default_factory=list)

    def find(self, window_class: str, window_title: str) -> list[VaultEntry]:
        """Entries for `window_class`.

        An entry with a `title_hint` only matches a window whose title
        contains it — this is what makes several logins work under one
        window class (every browser tab shares a class, not a title). An
        entry with no hint matches any window of that class. When both kinds
        match, the title-hinted ones win, since they said more about what
        they're for; an unmatched window with only hinted entries to compare
        against finds nothing, rather than guessing.

        Never raises; an unmatched window just gets an empty list."""
        window_class = (window_class or "").lower()
        title = (window_title or "").lower()
        in_class = [e for e in self.entries if e.window_class.lower() == window_class]
        specific = [e for e in in_class if e.title_hint and e.title_hint.lower() in title]
        return specific or [e for e in in_class if not e.title_hint]

    def get(self, entry_id: str) -> Optional[VaultEntry]:
        return next((e for e in self.entries if e.id == entry_id), None)


def new_entry(
    *, window_class: str, title_hint: str = "", label: str = "", secret: str, send_enter: bool = False
) -> VaultEntry:
    return VaultEntry(
        id=uuid.uuid4().hex,
        window_class=window_class,
        title_hint=title_hint,
        label=label or window_class,
        secret=secret,
        send_enter=send_enter,
        created_at=time.time(),
    )


def save(vault: VaultStore, passphrase: str, path: Path = DEFAULT_VAULT_PATH) -> None:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    payload = json.dumps({"version": 1, "entries": [asdict(e) for e in vault.entries]}).encode("utf-8")

    salt = secrets.token_bytes(SALT_BYTES)
    nonce = secrets.token_bytes(NONCE_BYTES)
    ciphertext = AESGCM(derive_key(passphrase, salt)).encrypt(nonce, payload, None)

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(salt + nonce + ciphertext)
    os.chmod(temporary, 0o600)
    temporary.replace(path)  # atomic, so an interrupted save cannot truncate the vault


def load(passphrase: str, path: Path = DEFAULT_VAULT_PATH) -> VaultStore:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if not path.exists():
        return VaultStore()
    blob = path.read_bytes()
    salt, nonce, ciphertext = (
        blob[:SALT_BYTES],
        blob[SALT_BYTES : SALT_BYTES + NONCE_BYTES],
        blob[SALT_BYTES + NONCE_BYTES :],
    )
    payload = json.loads(
        AESGCM(derive_key(passphrase, salt)).decrypt(nonce, ciphertext, None).decode("utf-8")
    )
    return VaultStore(entries=[VaultEntry(**entry) for entry in payload["entries"]])
