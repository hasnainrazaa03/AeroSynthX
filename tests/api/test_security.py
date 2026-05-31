from __future__ import annotations

from aerosynthx.api.security import ApiKeyStore, Scope, _hash_key, _parse_scopes


def test_from_keys_ignores_blanks_and_hashes() -> None:
    store = ApiKeyStore.from_keys(["alpha", "  ", "", "beta"])
    assert store.enabled
    assert store.hashes == frozenset({_hash_key("alpha"), _hash_key("beta")})


def test_from_keys_grants_all_scopes_by_default() -> None:
    store = ApiKeyStore.from_keys(["alpha"])
    assert store.scopes_for("alpha") == frozenset({Scope.READ, Scope.RUN})


def test_from_keys_accepts_explicit_scopes() -> None:
    store = ApiKeyStore.from_keys(["reader"], scopes=[Scope.READ])
    assert store.scopes_for("reader") == frozenset({Scope.READ})


def test_empty_store_is_disabled() -> None:
    assert not ApiKeyStore.from_keys([]).enabled
    assert not ApiKeyStore().enabled


def test_from_env_reads_comma_separated() -> None:
    store = ApiKeyStore.from_env({"AEROSYNTHX_API_KEYS": "k1, k2 ,k3"})
    assert store.hashes == frozenset({_hash_key("k1"), _hash_key("k2"), _hash_key("k3")})
    # Bare keys (no scope suffix) get all scopes.
    assert store.scopes_for("k1") == frozenset({Scope.READ, Scope.RUN})


def test_from_env_parses_scoped_entries() -> None:
    store = ApiKeyStore.from_env(
        {"AEROSYNTHX_API_KEYS": "admin:read|run, reader:read , runner:run"}
    )
    assert store.scopes_for("admin") == frozenset({Scope.READ, Scope.RUN})
    assert store.scopes_for("reader") == frozenset({Scope.READ})
    assert store.scopes_for("runner") == frozenset({Scope.RUN})


def test_from_env_skips_entries_with_empty_key() -> None:
    store = ApiKeyStore.from_env({"AEROSYNTHX_API_KEYS": ":read, ,valid"})
    assert store.hashes == frozenset({_hash_key("valid")})


def test_from_env_empty_scope_suffix_grants_all() -> None:
    # A trailing colon with no scopes falls back to all scopes.
    store = ApiKeyStore.from_env({"AEROSYNTHX_API_KEYS": "k1:"})
    assert store.scopes_for("k1") == frozenset({Scope.READ, Scope.RUN})


def test_from_env_missing_var_is_disabled() -> None:
    assert not ApiKeyStore.from_env({}).enabled


def test_parse_scopes_ignores_unknown_tokens() -> None:
    assert _parse_scopes("read bogus run") == frozenset({Scope.READ, Scope.RUN})
    assert _parse_scopes("nonsense") == frozenset()


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


def test_scopes_for_unknown_key_is_empty() -> None:
    store = ApiKeyStore.from_keys(["good"])
    assert store.scopes_for("bad") == frozenset()
    assert store.scopes_for(None) == frozenset()
