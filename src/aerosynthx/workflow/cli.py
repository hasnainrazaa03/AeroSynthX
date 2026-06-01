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
from aerosynthx.workflow.progress import ProgressEvent

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
    run_p.add_argument(
        "--execute",
        action="store_true",
        help="Run the generated case through OpenFOAM when the toolchain is available.",
    )
    run_p.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Wall-clock budget in seconds; the run fails fast once exceeded.",
    )
    run_p.add_argument(
        "--progress",
        action="store_true",
        help="Stream stage progress events to stderr as the run executes.",
    )

    show_p = sub.add_parser("show", help="Print a persisted run as JSON to stdout.")
    show_p.add_argument("run_id", help="Run id returned by `run`.")
    show_p.add_argument("--out", required=True, type=Path, help="Output directory used by `run`.")

    delete_p = sub.add_parser("delete", help="Delete a persisted run and its artifacts.")
    delete_p.add_argument("run_id", help="Run id returned by `run`.")
    delete_p.add_argument("--out", required=True, type=Path, help="Output directory used by `run`.")

    prune_p = sub.add_parser("prune", help="Prune old runs and reclaim store blobs.")
    prune_p.add_argument("--out", required=True, type=Path, help="Output directory used by runs.")
    prune_p.add_argument(
        "--max-age-days",
        type=float,
        default=None,
        help="Delete runs older than this many days.",
    )
    prune_p.add_argument(
        "--max-count",
        type=int,
        default=None,
        help="Keep only this many newest runs; delete the rest.",
    )
    prune_p.add_argument(
        "--gc",
        action="store_true",
        help="After pruning, garbage-collect store blobs no run references.",
    )

    relink_p = sub.add_parser(
        "relink", help="Hard-link run files into the store to reclaim disk space."
    )
    relink_p.add_argument("--out", required=True, type=Path, help="Output directory used by runs.")

    serve_p = sub.add_parser("serve", help="Start the FastAPI server.")
    serve_p.add_argument("--out", required=True, type=Path, help="Output directory used by runs.")
    serve_p.add_argument("--host", default="127.0.0.1", help="Bind host.")
    serve_p.add_argument("--port", default=8000, type=int, help="Bind port.")
    serve_p.add_argument(
        "--rate-limit",
        type=int,
        default=None,
        help="Max requests per window per principal (0 disables; default from env).",
    )
    serve_p.add_argument(
        "--rate-window-seconds",
        type=float,
        default=None,
        help="Rate-limit window in seconds (default from env or 60).",
    )
    serve_p.add_argument(
        "--max-body-bytes",
        type=int,
        default=None,
        help="Reject larger request bodies with 413 (0 disables; default from env or 1 MiB).",
    )

    return parser


def _print_result(result: RunResult) -> None:
    sys.stdout.write(json.dumps(result.to_json(), indent=2, sort_keys=True) + "\n")


def _progress_to_stderr(event: ProgressEvent) -> None:
    parts = [f"progress[{event.sequence}] {event.kind}"]
    if event.stage is not None:
        parts.append(event.stage)
    if event.status is not None:
        parts.append(event.status)
    if event.duration_ms is not None:
        parts.append(f"{event.duration_ms}ms")
    sys.stderr.write(" ".join(parts) + "\n")


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
        result = pipeline.run(
            args.intent,
            resume=not args.no_resume,
            execute=args.execute,
            timeout=args.timeout,
            on_event=_progress_to_stderr if args.progress else None,
        )
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


def _cmd_delete(args: argparse.Namespace) -> int:
    pipeline = Pipeline(out_root=args.out)
    if not pipeline.delete_run(args.run_id):
        raise RunNotFoundError(f"no run with id {args.run_id!r} in {pipeline.db_path}")
    sys.stdout.write(f"deleted run {args.run_id}\n")
    return 0


def _cmd_prune(args: argparse.Namespace) -> int:
    pipeline = Pipeline(out_root=args.out)
    result = pipeline.prune_runs(max_age_days=args.max_age_days, max_count=args.max_count)
    sys.stdout.write(f"pruned {result.count} run(s); {result.kept} kept\n")
    if args.gc:
        gc = pipeline.collect_garbage()
        sys.stdout.write(
            f"collected {gc.collected} blob(s); {gc.freed_bytes} bytes freed; {gc.kept} kept\n"
        )
    return 0


def _cmd_relink(args: argparse.Namespace) -> int:
    pipeline = Pipeline(out_root=args.out)
    result = pipeline.relink_runs()
    sys.stdout.write(
        f"linked {result.linked} file(s); "
        f"{result.bytes_reclaimed} bytes reclaimed; {result.skipped} skipped\n"
    )
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    # Imports deferred so `aerosynthx run`/`show` do not pay the FastAPI cost.
    import uvicorn

    from aerosynthx.api import create_app
    from aerosynthx.intent import build_client_from_env

    app = create_app(
        out_root=args.out,
        llm_client=build_client_from_env(),
        rate_limit=args.rate_limit,
        rate_window_seconds=args.rate_window_seconds,
        max_body_bytes=args.max_body_bytes,
    )
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
    if args.command == "delete":
        return _cmd_delete(args)
    if args.command == "prune":
        return _cmd_prune(args)
    if args.command == "relink":
        return _cmd_relink(args)
    if args.command == "serve":  # pragma: no branch - argparse enforces choice
        return _cmd_serve(args)
    parser.error(f"unknown command: {args.command}")  # pragma: no cover
    return 2  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
