"""Tests for the CLI entry point."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from aerosynthx.workflow.cli import main


def test_run_happy_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    argv = [
        "run",
        "--intent",
        "NACA 0012 at 50 m/s, 4 deg alpha",
        "--out",
        str(tmp_path),
    ]
    assert main(argv) == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["status"] == "completed"


@patch("aerosynthx.workflow.pipeline.run_xfoil")
def test_run_xfoil_mode(mock_run_xfoil, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from aerosynthx.xfoil import XfoilResult
    mock_run_xfoil.return_value = [XfoilResult(alpha_deg=4.0, cl=0.45, cd=0.006, cm=0.0)]

    argv = [
        "run",
        "--intent",
        "NACA 0012 at 50 m/s, 4 deg alpha",
        "--out",
        str(tmp_path),
        "--mode",
        "xfoil",
    ]
    assert main(argv) == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["status"] == "completed"
    assert result["xfoil"] is not None
    assert len(result["xfoil"]) == 1
    assert result["xfoil"][0]["cl"] == 0.45


def test_run_failure_exits_nonzero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    argv = [
        "run",
        "--intent",
        "unparseable gibberish",
        "--out",
        str(tmp_path),
    ]
    assert main(argv) == 1
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["status"] == "failed"


def test_run_stage_error_exits_2(tmp_path: Path) -> None:
    argv = ["run", "--intent", "  ", "--out", str(tmp_path)]
    assert main(argv) == 2


def test_show_happy_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_argv = [
        "run",
        "--intent",
        "NACA 0012 at 50 m/s, 4 deg alpha",
        "--out",
        str(tmp_path),
    ]
    assert main(run_argv) == 0
    run_id = json.loads(capsys.readouterr().out)["run_id"]

    show_argv = ["show", run_id, "--out", str(tmp_path)]
    assert main(show_argv) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["run_id"] == run_id


def test_delete_happy_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_argv = [
        "run",
        "--intent",
        "NACA 0012 at 50 m/s, 4 deg alpha",
        "--out",
        str(tmp_path),
    ]
    assert main(run_argv) == 0
    run_id = json.loads(capsys.readouterr().out)["run_id"]

    delete_argv = ["delete", run_id, "--out", str(tmp_path)]
    assert main(delete_argv) == 0
    assert f"deleted run {run_id}" in capsys.readouterr().out


def test_report_happy_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_argv = [
        "run",
        "--intent",
        "NACA 0012 at 50 m/s, 4 deg alpha",
        "--out",
        str(tmp_path),
    ]
    assert main(run_argv) == 0
    run_id = json.loads(capsys.readouterr().out)["run_id"]

    report_argv = ["report", run_id, "--out", str(tmp_path)]
    assert main(report_argv) == 0
    html = capsys.readouterr().out
    assert html.startswith("<!DOCTYPE html>")
    assert run_id in html


def test_prune_and_gc(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["run", "--intent", "run 1", "--out", str(tmp_path)])
    main(["run", "--intent", "run 2", "--out", str(tmp_path)])
    prune_argv = ["prune", "--out", str(tmp_path), "--max-count", "1", "--gc"]
    assert main(prune_argv) == 0
    out = capsys.readouterr().out
    assert "pruned 1 run(s)" in out
    assert "collected" in out


def test_relink(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["run", "--intent", "run 1", "--out", str(tmp_path)])
    relink_argv = ["relink", "--out", str(tmp_path)]
    assert main(relink_argv) == 0
    assert "linked" in capsys.readouterr().out


def test_serve_is_registered(tmp_path: Path) -> None:
    # Not testing the server itself, just that the command is wired.
    with patch("uvicorn.run") as mock_run:
        main(["serve", "--out", str(tmp_path)])
        mock_run.assert_called_once()
