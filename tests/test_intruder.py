"""Failed-attempt photos on disk: private, pruned, named by time."""

from __future__ import annotations

import numpy as np

from glanced import intruder


def test_save_is_private_and_pruned(tmp_path):
    frame = np.zeros((24, 32, 3), dtype=np.uint8)
    for second in range(5):
        intruder.save(frame, "face", directory=tmp_path, keep=3, now=1_700_000_000 + second)
    kept = intruder.photos(tmp_path)
    assert len(kept) == 3
    assert kept[0].name < kept[-1].name  # oldest first; the two oldest went
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in kept)
    assert tmp_path.stat().st_mode & 0o777 == 0o700


def test_reason_cannot_escape_the_directory(tmp_path):
    path = intruder.save(np.zeros((8, 8, 3), dtype=np.uint8), "../../etc/x", directory=tmp_path)
    assert path.parent == tmp_path


def test_clear(tmp_path):
    intruder.save(np.zeros((8, 8, 3), dtype=np.uint8), "password", directory=tmp_path)
    assert intruder.clear(tmp_path) == 1
    assert intruder.photos(tmp_path) == []
    assert intruder.photos(tmp_path / "missing") == []
