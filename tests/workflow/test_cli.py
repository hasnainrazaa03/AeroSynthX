from __future__ import annotations

import json
from pathlib import Path

import pytest

from aerosynthx.workflow.cli import main
from aerosynthx.workflow.errors import RunNotFoundError

_GOOD = "NACA 2412 at 50 m/s, alpha 3 deg, chord 1.0 m."


def _capture(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    out = capsys.readouterr().out.strip()
    return json.loads(out)  # type: ignore[no-any-return]


def test_run_subcommand_succeeds(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["run", "--intent", _GOOD, "--out", str(tmp_path)])
    assert rc == 0
    payload = _capture(capsys)
    assert payload["status"] == "completed"
    assert payload["run_id"]


def test_run_then_show(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "--intent", _GOOD, "--out", str(tmp_path)]) == 0
    payload = _capture(capsys)
    run_id = str(payload["run_id"])

    assert main(["show", run_id, "--out", str(tmp_path)]) == 0
    shown = _capture(capsys)
    assert shown["run_id"] == run_id


def test_show_missing_run_raises(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # First create the db so it exists but has no matching row.
    assert main(["run", "--intent", _GOOD, "--out", str(tmp_path)]) == 0
    capsys.readouterr()
    with pytest.raises(RunNotFoundError):
        main(["show", "ffffffffffffffff", "--out", str(tmp_path)])


def test_run_failing_intent_returns_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["run", "--intent", "totally unparseable gibberish", "--out", str(tmp_path)])
    assert rc == 1
    payload = _capture(capsys)
    assert payload["status"] == "failed"


def test_run_empty_intent_returns_stage_error_exit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["run", "--intent", "   ", "--out", str(tmp_path)])
    assert rc == 2


def test_no_resume_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "--intent", _GOOD, "--out", str(tmp_path)]) == 0
    capsys.readouterr()
    assert main(["run", "--intent", _GOOD, "--out", str(tmp_path), "--no-resume"]) == 0
    payload = _capture(capsys)
    assert payload["status"] == "completed"


def test_run_timeout_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["run", "--intent", _GOOD, "--out", str(tmp_path), "--timeout", "60"])
    assert rc == 0
    payload = _capture(capsys)
    assert payload["status"] == "completed"


def test_verbose_flag_sets_debug_logging(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import logging

    assert main(["-v", "run", "--intent", _GOOD, "--out", str(tmp_path)]) == 0
    assert logging.getLogger().level == logging.DEBUG
    # Reset for other tests.
    logging.getLogger().setLevel(logging.WARNING)


def test_missing_subcommand_errors(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main([])


def test_serve_subcommand_invokes_uvicorn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def fake_run(app: object, **kwargs: object) -> None:
        calls["app"] = app
        calls["kwargs"] = kwargs

    import uvicorn

    monkeypatch.setattr(uvicorn, "run", fake_run)
    rc = main(
        [
            "serve",
            "--out",
            str(tmp_path),
            "--host",
            "127.0.0.1",
            "--port",
            "9999",
        ]
    )
    assert rc == 0
    assert calls["app"] is not None
    assert calls["kwargs"] == {"host": "127.0.0.1", "port": 9999, "log_level": "info"}


def test_run_use_llm_without_provider_warns_and_uses_offline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # No AEROSYNTHX_LLM_PROVIDER -> build_client_from_env returns None.
    monkeypatch.delenv("AEROSYNTHX_LLM_PROVIDER", raising=False)
    rc = main(["run", "--intent", _GOOD, "--out", str(tmp_path), "--use-llm"])
    assert rc == 0
    payload = _capture(capsys)
    assert payload["status"] == "completed"


def test_run_use_llm_with_provider_builds_client(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import aerosynthx.intent as intent_pkg
    from aerosynthx.intent import StaticLLMClient, parse_offline

    payload = parse_offline(_GOOD).intent.model_dump(mode="json")

    def fake_build(env: object = None) -> StaticLLMClient:
        return StaticLLMClient([payload])

    monkeypatch.setattr(intent_pkg, "build_client_from_env", fake_build)
    rc = main(["run", "--intent", _GOOD, "--out", str(tmp_path), "--use-llm"])
    assert rc == 0
    assert _capture(capsys)["status"] == "completed"
