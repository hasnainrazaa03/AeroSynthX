from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aerosynthx import __version__
from aerosynthx.api import create_app

_GOOD = "NACA 2412 at 50 m/s, alpha 3 deg, chord 1.0 m."


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


def test_list_runs_limit_clamped(client: TestClient) -> None:
    assert client.get("/api/v1/runs?limit=0").status_code == 200
    assert client.get("/api/v1/runs?limit=9999").status_code == 200


def test_get_run(client: TestClient) -> None:
    created = client.post("/api/v1/runs", json={"intent_text": _GOOD}).json()
    r = client.get(f"/api/v1/runs/{created['run_id']}")
    assert r.status_code == 200
    assert r.json()["run_id"] == created["run_id"]


def test_get_run_404(client: TestClient) -> None:
    r = client.get("/api/v1/runs/0000000000000000")
    assert r.status_code == 404


def test_list_files(client: TestClient) -> None:
    created = client.post("/api/v1/runs", json={"intent_text": _GOOD}).json()
    r = client.get(f"/api/v1/runs/{created['run_id']}/files")
    assert r.status_code == 200
    files = r.json()["files"]
    assert any(f.endswith("Allrun") for f in files)


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
