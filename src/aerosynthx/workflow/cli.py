"""Command-line entry point for ``aerosynthx``."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from aerosynthx.workflow.errors import RunNotFoundError, StageError
from aerosynthx.workflow.pipeline import Pipeline, RunResult, load_run

_LOG = logging.getLogger("aerosynthx.cli")


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger().setLevel(level)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aerosynthx",
        description="AI-assisted aerodynamic design and CFD orchestration.",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging.")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Execute the pipeline for an intent.")
    run_p.add_argument("--intent", required=True, help="Natural-language design intent text.")
    run_p.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Output directory; created if absent.",
    )
    run_p.add_argument(
        "--no-resume",
        action="store_true",
        help="Re-execute even if a completed run already exists.",
    )
    run_p.add_argument(
        "--use-llm",
        action="store_true",
        help="Parse with the configured LLM provider (AEROSYNTHX_LLM_* env vars).",
    )

    show_p = sub.add_parser("show", help="Print a persisted run as JSON to stdout.")
    show_p.add_argument("run_id", help="Run id returned by `run`.")
    show_p.add_argument("--out", required=True, type=Path, help="Output directory used by `run`.")

    serve_p = sub.add_parser("serve", help="Start the FastAPI server.")
    serve_p.add_argument("--out", required=True, type=Path, help="Output directory used by runs.")
    serve_p.add_argument("--host", default="127.0.0.1", help="Bind host.")
    serve_p.add_argument("--port", default=8000, type=int, help="Bind port.")

    return parser


def _print_result(result: RunResult) -> None:
    sys.stdout.write(json.dumps(result.to_json(), indent=2, sort_keys=True) + "\n")


def _cmd_run(args: argparse.Namespace) -> int:
    llm_client = None
    if args.use_llm:
        from aerosynthx.intent import build_client_from_env

        llm_client = build_client_from_env()
        if llm_client is None:
            _LOG.warning(
                "--use-llm given but AEROSYNTHX_LLM_PROVIDER is unset; using offline parser"
            )
    pipeline = Pipeline(out_root=args.out, llm_client=llm_client)
    try:
        result = pipeline.run(args.intent, resume=not args.no_resume)
    except StageError as exc:
        _LOG.error("stage %s failed: %s", exc.stage, exc)
        return 2
    _print_result(result)
    return 0 if result.status == "completed" else 1


def _cmd_show(args: argparse.Namespace) -> int:
    db_path = args.out / "aerosynthx.db"
    result = load_run(db_path, args.run_id)
    if result is None:
        raise RunNotFoundError(f"no run with id {args.run_id!r} in {db_path}")
    _print_result(result)
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    # Imports deferred so `aerosynthx run`/`show` do not pay the FastAPI cost.
    import uvicorn

    from aerosynthx.api import create_app
    from aerosynthx.intent import build_client_from_env

    app = create_app(out_root=args.out, llm_client=build_client_from_env())
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI; return a POSIX exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "show":
        return _cmd_show(args)
    if args.command == "serve":  # pragma: no branch - argparse enforces choice
        return _cmd_serve(args)
    parser.error(f"unknown command: {args.command}")  # pragma: no cover
    return 2  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
