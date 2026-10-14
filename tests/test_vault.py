"""The autotype vault: same file shape as the enrollment store, own key
material by construction (its own salt/nonce), and the class/title matching
rule `glancectl autotype` depends on."""

from __future__ import annotations

import pytest

from glanced import vault as vault_module


def test_round_trip(tmp_path):
    path = tmp_path / "vault.bin"
    store = vault_module.VaultStore()
    store.entries.append(
        vault_module.new_entry(window_class="firefox", title_hint="GitHub", label="GitHub", secret="hunter2")
    )
    vault_module.save(store, "hunter2", path)

    loaded = vault_module.load("hunter2", path)
    assert len(loaded.entries) == 1
    assert loaded.entries[0].secret == "hunter2"
    assert loaded.entries[0].window_class == "firefox"


def test_wrong_passphrase_raises(tmp_path):
    path = tmp_path / "vault.bin"
    vault_module.save(vault_module.VaultStore(), "right", path)
    with pytest.raises(Exception):
        vault_module.load("wrong", path)


def test_missing_file_is_an_empty_vault(tmp_path):
    store = vault_module.load("anything", tmp_path / "does-not-exist.bin")
    assert store.entries == []


def test_saved_file_is_0600(tmp_path):
    path = tmp_path / "vault.bin"
    vault_module.save(vault_module.VaultStore(), "hunter2", path)
    assert path.stat().st_mode & 0o777 == 0o600


def test_find_matches_by_class_alone_when_unambiguous():
    store = vault_module.VaultStore(
        entries=[vault_module.new_entry(window_class="firefox", secret="a")]
    )
    assert [e.secret for e in store.find("firefox", "anything")] == ["a"]
    assert store.find("chromium", "anything") == []


def test_find_narrows_by_title_hint_when_ambiguous():
    store = vault_module.VaultStore(
        entries=[
            vault_module.new_entry(window_class="firefox", title_hint="GitHub", secret="a"),
            vault_module.new_entry(window_class="firefox", title_hint="Gmail", secret="b"),
        ]
    )
    assert [e.secret for e in store.find("firefox", "Inbox - Gmail - Mozilla Firefox")] == ["b"]
    assert [e.secret for e in store.find("firefox", "GitHub - Mozilla Firefox")] == ["a"]


def test_find_returns_nothing_when_no_title_hint_matches():
    # Every saved entry for this class said what site it's for; a window
    # that matches none of them is a different, unsaved site — not a guess
    # between the two that happen to share a browser.
    store = vault_module.VaultStore(
        entries=[
            vault_module.new_entry(window_class="firefox", title_hint="GitHub", secret="a"),
            vault_module.new_entry(window_class="firefox", title_hint="Gmail", secret="b"),
        ]
    )
    assert store.find("firefox", "New Tab - Mozilla Firefox") == []


def test_find_ambiguous_when_two_entries_share_a_matching_hint():
    store = vault_module.VaultStore(
        entries=[
            vault_module.new_entry(window_class="firefox", title_hint="Google", label="work", secret="a"),
            vault_module.new_entry(window_class="firefox", title_hint="Google", label="personal", secret="b"),
        ]
    )
    matches = store.find("firefox", "Google - Mozilla Firefox")
    assert {e.secret for e in matches} == {"a", "b"}


def test_find_prefers_a_title_matched_entry_over_a_catch_all_one():
    catch_all = vault_module.new_entry(window_class="firefox", secret="a")
    specific = vault_module.new_entry(window_class="firefox", title_hint="GitHub", secret="b")
    store = vault_module.VaultStore(entries=[catch_all, specific])
    assert [e.secret for e in store.find("firefox", "GitHub - Mozilla Firefox")] == ["b"]


def test_find_falls_back_to_a_catch_all_entry_when_no_hint_matches():
    catch_all = vault_module.new_entry(window_class="firefox", secret="a")
    specific = vault_module.new_entry(window_class="firefox", title_hint="GitHub", secret="b")
    store = vault_module.VaultStore(entries=[catch_all, specific])
    assert [e.secret for e in store.find("firefox", "New Tab - Mozilla Firefox")] == ["a"]


def test_get_by_id():
    entry = vault_module.new_entry(window_class="firefox", secret="a")
    store = vault_module.VaultStore(entries=[entry])
    assert store.get(entry.id) is entry
    assert store.get("nope") is None
