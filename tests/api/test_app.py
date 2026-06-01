from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aerosynthx import __version__
from aerosynthx.api import create_app

_GOOD = "NACA 2412 at 50 m/s, alpha 3 deg, chord 1.0 m."
_OTHER = "NACA 2412 at 65 m/s, alpha 3 deg, chord 1.0 m."


@pytest.fixture()
def client(tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(out_root=tmp_path)
    with TestClient(app) as c:
        yield c


def test_healthz(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_version(client: TestClient) -> None:
    r = client.get("/api/v1/version")
    assert r.status_code == 200
    assert r.json() == {"name": "aerosynthx", "version": __version__}


def test_create_run_happy(client: TestClient) -> None:
    r = client.post("/api/v1/runs", json={"intent_text": _GOOD})
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "completed"
    assert body["run_id"]
    assert len(body["stages"]) == 5


def test_create_run_failed_status_is_201_with_failed_body(client: TestClient) -> None:
    """Stage failures (e.g. unparseable intent) yield 201 + status=failed."""
    r = client.post(
        "/api/v1/runs",
        json={"intent_text": "totally unparseable gibberish without numbers"},
    )
    assert r.status_code == 201
    assert r.json()["status"] == "failed"


def test_create_run_empty_intent_returns_422(client: TestClient) -> None:
    r = client.post("/api/v1/runs", json={"intent_text": ""})
    assert r.status_code == 422


def test_create_run_accepts_timeout_seconds(client: TestClient) -> None:
    r = client.post("/api/v1/runs", json={"intent_text": _GOOD, "timeout_seconds": 60})
    assert r.status_code == 201
    assert r.json()["status"] == "completed"


def test_create_run_rejects_non_positive_timeout(client: TestClient) -> None:
    r = client.post("/api/v1/runs", json={"intent_text": _GOOD, "timeout_seconds": 0})
    assert r.status_code == 422


def test_create_run_whitespace_intent_returns_400(client: TestClient) -> None:
    r = client.post("/api/v1/runs", json={"intent_text": "   "})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["stage"] == "parse"


def test_list_runs(client: TestClient) -> None:
    assert client.post("/api/v1/runs", json={"intent_text": _GOOD}).status_code == 201
    r = client.get("/api/v1/runs")
    assert r.status_code == 200
    runs = r.json()
    assert len(runs) == 1
    assert runs[0]["status"] == "completed"


def test_delete_run_returns_204(client: TestClient) -> None:
    created = client.post("/api/v1/runs", json={"intent_text": _GOOD}).json()
    run_id = created["run_id"]
    r = client.delete(f"/api/v1/runs/{run_id}")
    assert r.status_code == 204
    assert client.get(f"/api/v1/runs/{run_id}").status_code == 404


def test_delete_run_missing_returns_404(client: TestClient) -> None:
    r = client.delete("/api/v1/runs/ffffffffffffffff")
    assert r.status_code == 404


def test_list_runs_limit_clamped(client: TestClient) -> None:
    assert client.get("/api/v1/runs?limit=0").status_code == 200
    assert client.get("/api/v1/runs?limit=9999").status_code == 200


def test_list_runs_pagination_headers_and_offset(client: TestClient) -> None:
    for velocity in (50, 55, 60):
        intent = f"NACA 2412 at {velocity} m/s, alpha 3 deg, chord 1.0 m."
        assert client.post("/api/v1/runs", json={"intent_text": intent}).status_code == 201
    first = client.get("/api/v1/runs?limit=2&offset=0")
    assert first.status_code == 200
    assert first.headers["X-Total-Count"] == "3"
    assert first.headers["X-Limit"] == "2"
    assert first.headers["X-Offset"] == "0"
    assert len(first.json()) == 2
    second = client.get("/api/v1/runs?limit=2&offset=2")
    assert second.headers["X-Total-Count"] == "3"
    assert len(second.json()) == 1


def test_list_runs_search_filters_by_intent(client: TestClient) -> None:
    assert client.post("/api/v1/runs", json={"intent_text": _GOOD}).status_code == 201
    assert client.post("/api/v1/runs", json={"intent_text": _OTHER}).status_code == 201
    r = client.get("/api/v1/runs?q=65 m/s")
    assert r.status_code == 200
    runs = r.json()
    assert len(runs) == 1
    assert "65 m/s" in runs[0]["intent_text"]
    assert r.headers["X-Total-Count"] == "1"


def test_list_runs_status_filter(client: TestClient) -> None:
    assert client.post("/api/v1/runs", json={"intent_text": _GOOD}).status_code == 201
    assert (
        client.post(
            "/api/v1/runs",
            json={"intent_text": "totally unparseable gibberish without numbers"},
        ).status_code
        == 201
    )
    completed = client.get("/api/v1/runs?status=completed").json()
    assert len(completed) == 1
    assert completed[0]["status"] == "completed"
    failed = client.get("/api/v1/runs?status=failed").json()
    assert len(failed) == 1
    assert failed[0]["status"] == "failed"


def test_get_run(client: TestClient) -> None:
    created = client.post("/api/v1/runs", json={"intent_text": _GOOD}).json()
    r = client.get(f"/api/v1/runs/{created['run_id']}")
    assert r.status_code == 200
    assert r.json()["run_id"] == created["run_id"]


def test_get_run_404(client: TestClient) -> None:
    r = client.get("/api/v1/runs/0000000000000000")
    assert r.status_code == 404


def test_stream_run_events(client: TestClient) -> None:
    created = client.post("/api/v1/runs", json={"intent_text": _GOOD}).json()
    r = client.get(f"/api/v1/runs/{created['run_id']}/events")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.headers["cache-control"] == "no-cache"
    assert r.headers["x-accel-buffering"] == "no"
    body = r.text
    assert "event: stage" in body
    assert body.rstrip().endswith("}")
    assert "event: complete" in body
    assert created["run_id"] in body


def test_stream_run_events_404(client: TestClient) -> None:
    r = client.get("/api/v1/runs/0000000000000000/events")
    assert r.status_code == 404


def test_list_files(client: TestClient) -> None:
    created = client.post("/api/v1/runs", json={"intent_text": _GOOD}).json()
    r = client.get(f"/api/v1/runs/{created['run_id']}/files")
    assert r.status_code == 200
    files = r.json()["files"]
    assert any(f.endswith("Allrun") for f in files)


def test_store_stats(client: TestClient) -> None:
    empty = client.get("/api/v1/store/stats")
    assert empty.status_code == 200
    assert empty.json() == {"blobs": 0, "bytes": 0}

    client.post("/api/v1/runs", json={"intent_text": _GOOD})
    after = client.get("/api/v1/store/stats").json()
    assert after["blobs"] > 0
    assert after["bytes"] > 0


def test_prune_endpoint_trims_and_gcs(client: TestClient) -> None:
    client.post("/api/v1/runs", json={"intent_text": _GOOD})
    client.post("/api/v1/runs", json={"intent_text": _OTHER})
    assert len(client.get("/api/v1/runs").json()) == 2
    before = client.get("/api/v1/store/stats").json()["blobs"]

    resp = client.post("/api/v1/maintenance/prune", json={"max_count": 1, "gc": True})

    assert resp.status_code == 200
    body = resp.json()
    assert body["pruned"] == 1
    assert body["kept"] == 1
    assert body["collected"] >= 1
    assert body["freed_bytes"] > 0
    assert len(client.get("/api/v1/runs").json()) == 1
    assert client.get("/api/v1/store/stats").json()["blobs"] == before - body["collected"]


def test_prune_endpoint_without_gc_leaves_blobs(client: TestClient) -> None:
    client.post("/api/v1/runs", json={"intent_text": _GOOD})
    before = client.get("/api/v1/store/stats").json()["blobs"]

    body = client.post("/api/v1/maintenance/prune", json={"max_count": 0}).json()

    assert body["pruned"] == 1
    assert body["collected"] == 0
    assert body["freed_bytes"] == 0
    assert client.get("/api/v1/store/stats").json()["blobs"] == before


def test_relink_endpoint_links_run_files(client: TestClient) -> None:
    client.post("/api/v1/runs", json={"intent_text": _GOOD})

    resp = client.post("/api/v1/maintenance/relink")

    assert resp.status_code == 200
    body = resp.json()
    assert body["linked"] > 0
    assert body["bytes_reclaimed"] > 0
    assert body["skipped"] == 0

    # A second relink finds everything already linked.
    again = client.post("/api/v1/maintenance/relink").json()
    assert again["linked"] == 0
    assert again["bytes_reclaimed"] == 0
    assert again["skipped"] > 0


def test_list_files_404_unknown_run(client: TestClient) -> None:
    r = client.get("/api/v1/runs/deadbeefdeadbeef/files")
    assert r.status_code == 404


def test_list_files_409_when_case_missing(client: TestClient, tmp_path: Path) -> None:
    created = client.post("/api/v1/runs", json={"intent_text": _GOOD}).json()
    # Remove the case dir to simulate corruption.
    import shutil

    shutil.rmtree(tmp_path / "runs" / created["run_id"] / "case")
    r = client.get(f"/api/v1/runs/{created['run_id']}/files")
    assert r.status_code == 409


def test_download_file(client: TestClient) -> None:
    created = client.post("/api/v1/runs", json={"intent_text": _GOOD}).json()
    r = client.get(f"/api/v1/runs/{created['run_id']}/files/Allrun")
    assert r.status_code == 200
    assert b"#!/" in r.content or len(r.content) > 0


def test_download_file_404_missing_file(client: TestClient) -> None:
    created = client.post("/api/v1/runs", json={"intent_text": _GOOD}).json()
    r = client.get(f"/api/v1/runs/{created['run_id']}/files/no/such/file.txt")
    assert r.status_code == 404


def test_download_file_rejects_traversal(client: TestClient) -> None:
    created = client.post("/api/v1/runs", json={"intent_text": _GOOD}).json()
    # FastAPI's path converter strips ../ outside the route; we test our
    # own guard by hitting the safe-resolve helper through a crafted
    # path that the router still forwards intact.
    r = client.get(f"/api/v1/runs/{created['run_id']}/files/..%2F..%2Fetc%2Fpasswd")
    assert r.status_code in {400, 404}


def test_index_html_served(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "AeroSynthX" in r.text


def test_static_assets_served(client: TestClient) -> None:
    r = client.get("/static/app.js")
    assert r.status_code == 200
    assert "fetch" in r.text


def test_app_without_static_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover the branch where static assets are absent."""
    from aerosynthx.api import app as app_mod

    monkeypatch.setattr(app_mod, "_STATIC_DIR", tmp_path / "missing")
    app = app_mod.create_app(out_root=tmp_path)
    with TestClient(app) as c:
        # Index route is not registered when static dir is missing.
        assert c.get("/").status_code == 404
        # API routes still work.
        assert c.get("/healthz").status_code == 200


def test_safe_resolve_direct_traversal_guard(tmp_path: Path) -> None:
    from fastapi import HTTPException

    from aerosynthx.api.app import _safe_resolve

    case = tmp_path / "case"
    case.mkdir()
    with pytest.raises(HTTPException) as exc:
        _safe_resolve(case, "../etc/passwd")
    assert exc.value.status_code == 400


def test_metrics_endpoint_exposes_prometheus_text(client: TestClient) -> None:
    # Drive at least one request through the API so counters populate.
    assert client.get("/healthz").status_code == 200
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    assert "aerosynthx_http_requests_total" in r.text
    assert "aerosynthx_http_request_duration_seconds" in r.text


def test_response_includes_correlation_id_header(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.headers.get("X-Correlation-Id")


def test_correlation_id_round_trips(client: TestClient) -> None:
    r = client.get("/healthz", headers={"X-Correlation-Id": "my-trace-1"})
    assert r.headers["X-Correlation-Id"] == "my-trace-1"


def test_use_llm_without_client_falls_back(client: TestClient) -> None:
    # Default app has no llm_client; use_llm must still succeed (offline).
    r = client.post("/api/v1/runs", json={"intent_text": _GOOD, "use_llm": True})
    assert r.status_code == 201
    assert r.json()["status"] == "completed"


def test_use_llm_with_client_invokes_llm(tmp_path: Path) -> None:
    from aerosynthx.intent import StaticLLMClient, parse_offline

    payload = parse_offline(_GOOD).intent.model_dump(mode="json")
    llm = StaticLLMClient([payload])
    app = create_app(out_root=tmp_path, llm_client=llm)
    with TestClient(app) as c:
        r = c.post("/api/v1/runs", json={"intent_text": _GOOD, "use_llm": True})
    assert r.status_code == 201
    assert r.json()["status"] == "completed"
    assert llm.calls, "LLM client should have been used"


@pytest.fixture()
def auth_client(tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(out_root=tmp_path, api_keys=["s3cret"])
    with TestClient(app) as c:
        yield c


def test_auth_rejects_missing_key(auth_client: TestClient) -> None:
    r = auth_client.post("/api/v1/runs", json={"intent_text": _GOOD})
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"


def test_auth_rejects_invalid_key(auth_client: TestClient) -> None:
    r = auth_client.get("/api/v1/runs", headers={"X-API-Key": "nope"})
    assert r.status_code == 401


def test_auth_accepts_x_api_key_header(auth_client: TestClient) -> None:
    r = auth_client.post(
        "/api/v1/runs", json={"intent_text": _GOOD}, headers={"X-API-Key": "s3cret"}
    )
    assert r.status_code == 201


def test_auth_accepts_bearer_token(auth_client: TestClient) -> None:
    r = auth_client.get("/api/v1/runs", headers={"Authorization": "Bearer s3cret"})
    assert r.status_code == 200


def test_auth_rejects_non_bearer_authorization(auth_client: TestClient) -> None:
    r = auth_client.get("/api/v1/runs", headers={"Authorization": "Basic s3cret"})
    assert r.status_code == 401


def test_auth_leaves_meta_endpoints_open(auth_client: TestClient) -> None:
    assert auth_client.get("/healthz").status_code == 200
    assert auth_client.get("/metrics").status_code == 200
    assert auth_client.get("/api/v1/version").status_code == 200


def test_open_mode_allows_unauthenticated(client: TestClient) -> None:
    # Default fixture configures no keys -> store disabled -> open access.
    assert client.get("/api/v1/runs").status_code == 200


def test_scoped_keys_enforce_rbac(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEROSYNTHX_API_KEYS", "reader:read, runner:run")
    app = create_app(out_root=tmp_path)
    with TestClient(app) as c:
        # Reader can list but cannot create.
        assert c.get("/api/v1/runs", headers={"X-API-Key": "reader"}).status_code == 200
        forbidden = c.post(
            "/api/v1/runs", json={"intent_text": _GOOD}, headers={"X-API-Key": "reader"}
        )
        assert forbidden.status_code == 403
        # Runner can create but cannot list.
        created = c.post(
            "/api/v1/runs", json={"intent_text": _GOOD}, headers={"X-API-Key": "runner"}
        )
        assert created.status_code == 201
        assert c.get("/api/v1/runs", headers={"X-API-Key": "runner"}).status_code == 403
        # The events stream requires the read scope.
        rid = created.json()["run_id"]
        assert (
            c.get(f"/api/v1/runs/{rid}/events", headers={"X-API-Key": "reader"}).status_code == 200
        )
        assert (
            c.get(f"/api/v1/runs/{rid}/events", headers={"X-API-Key": "runner"}).status_code == 403
        )
        # Store stats also requires the read scope.
        assert c.get("/api/v1/store/stats", headers={"X-API-Key": "reader"}).status_code == 200
        assert c.get("/api/v1/store/stats", headers={"X-API-Key": "runner"}).status_code == 403
        # Pruning requires the run scope.
        assert (
            c.post(
                "/api/v1/maintenance/prune", json={}, headers={"X-API-Key": "reader"}
            ).status_code
            == 403
        )
        assert (
            c.post(
                "/api/v1/maintenance/prune", json={}, headers={"X-API-Key": "runner"}
            ).status_code
            == 200
        )
        # Relinking also requires the run scope.
        assert (
            c.post("/api/v1/maintenance/relink", headers={"X-API-Key": "reader"}).status_code == 403
        )
        assert (
            c.post("/api/v1/maintenance/relink", headers={"X-API-Key": "runner"}).status_code == 200
        )


def test_rate_limit_returns_429(tmp_path: Path) -> None:
    app = create_app(out_root=tmp_path, rate_limit=1, rate_window_seconds=60.0)
    with TestClient(app) as c:
        assert c.get("/api/v1/runs").status_code == 200
        throttled = c.get("/api/v1/runs")
        assert throttled.status_code == 429
        assert throttled.json()["detail"] == "rate limit exceeded"
        assert int(throttled.headers["Retry-After"]) >= 1
        # Meta endpoints are never throttled.
        assert c.get("/healthz").status_code == 200


def test_body_size_limit_returns_413(tmp_path: Path) -> None:
    app = create_app(out_root=tmp_path, max_body_bytes=10)
    with TestClient(app) as c:
        r = c.post("/api/v1/runs", json={"intent_text": _GOOD})
        assert r.status_code == 413
        assert r.json()["detail"] == "request body too large"
        # Response still carries the correlation id from the outer middleware.
        assert r.headers.get("X-Correlation-Id")


def test_body_size_limit_disabled_allows_large(tmp_path: Path) -> None:
    app = create_app(out_root=tmp_path, max_body_bytes=0)
    with TestClient(app) as c:
        r = c.post("/api/v1/runs", json={"intent_text": _GOOD})
        assert r.status_code == 201
