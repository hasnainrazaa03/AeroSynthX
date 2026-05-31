from __future__ import annotations

from aerosynthx.api.security import ApiKeyStore, _hash_key


def test_from_keys_ignores_blanks_and_hashes() -> None:
    store = ApiKeyStore.from_keys(["alpha", "  ", "", "beta"])
    assert store.enabled
    assert store.hashes == frozenset({_hash_key("alpha"), _hash_key("beta")})


def test_empty_store_is_disabled() -> None:
    assert not ApiKeyStore.from_keys([]).enabled
    assert not ApiKeyStore().enabled


def test_from_env_reads_comma_separated() -> None:
    store = ApiKeyStore.from_env({"AEROSYNTHX_API_KEYS": "k1, k2 ,k3"})
    assert store.hashes == frozenset({_hash_key("k1"), _hash_key("k2"), _hash_key("k3")})


def test_from_env_missing_var_is_disabled() -> None:
    assert not ApiKeyStore.from_env({}).enabled


def test_verify_accepts_known_key() -> None:
    store = ApiKeyStore.from_keys(["good"])
    assert store.verify("good")


def test_verify_rejects_unknown_key() -> None:
    store = ApiKeyStore.from_keys(["good"])
    assert not store.verify("bad")


def test_verify_rejects_empty_and_none() -> None:
    store = ApiKeyStore.from_keys(["good"])
    assert not store.verify("")
    assert not store.verify(None)
