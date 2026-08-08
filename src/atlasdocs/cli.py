"""AtlasDocs command-line entrypoint."""

from __future__ import annotations

import argparse
import json
import os
import sys

from atlasdocs.config import get_settings
from atlasdocs.db.session import get_engine, get_session_factory
from atlasdocs.services.ingest import IngestionWorker
from atlasdocs.services.paperless import PaperlessClient
from atlasdocs.services.reconcile import ReconcileService


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="atlasdocs", description="AtlasDocs CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    reconcile = sub.add_parser(
        "reconcile",
        help="Reconcile Paperless documents with AtlasDocs external references",
    )
    reconcile.add_argument(
        "--dry-run",
        action="store_true",
        help="Report creates without writing AtlasDocs rows",
    )
    reconcile.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum Paperless documents to scan (also limits missing/inaccessible checks to those ids)",
    )
    reconcile.add_argument(
        "--page-size",
        type=int,
        default=100,
        help="Paperless list page size (default 100)",
    )
    reconcile.add_argument(
        "--token",
        default=None,
        help="Paperless API token (default: PAPERLESS_TOKEN env)",
    )
    reconcile.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON summary on stdout",
    )

    worker = sub.add_parser("worker", help="Background workers")
    worker_sub = worker.add_subparsers(dest="worker_command", required=True)
    ingest = worker_sub.add_parser("ingest", help="Process durable ingestion jobs")
    ingest.add_argument(
        "--once",
        action="store_true",
        help="Process at most one job and exit",
    )
    ingest.add_argument(
        "--idle-sleep",
        type=float,
        default=1.0,
        help="Seconds to sleep when the queue is empty (default 1)",
    )
    return parser


def _resolve_token(cli_token: str | None) -> str:
    token = (cli_token or os.environ.get("PAPERLESS_TOKEN") or "").strip()
    if not token:
        raise SystemExit(
            "Paperless token required via --token or PAPERLESS_TOKEN environment variable"
        )
    return token


def cmd_reconcile(args: argparse.Namespace) -> int:
    settings = get_settings()
    token = _resolve_token(args.token)
    get_engine()
    session = get_session_factory()()
    paperless = PaperlessClient(
        base_url=settings.paperless_base_url,
        timeout_seconds=settings.paperless_timeout_seconds,
    )
    try:
        service = ReconcileService(session, paperless)
        summary = service.reconcile(
            token,
            dry_run=args.dry_run,
            limit=args.limit,
            page_size=args.page_size,
        )
        if not args.dry_run:
            session.commit()
        else:
            session.rollback()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    if args.json:
        print(json.dumps(summary.to_dict(), indent=2, sort_keys=True))
    else:
        print(summary.human_summary())
        if summary.created:
            print("  created ids:", ", ".join(str(i) for i in summary.created[:20])
                  + ("…" if len(summary.created) > 20 else ""))
        if summary.missing_in_paperless:
            print(
                "  missing ids:",
                ", ".join(str(i) for i in summary.missing_in_paperless[:20])
                + ("…" if len(summary.missing_in_paperless) > 20 else ""),
            )
        if summary.inaccessible_in_paperless:
            print(
                "  inaccessible ids:",
                ", ".join(str(i) for i in summary.inaccessible_in_paperless[:20])
                + ("…" if len(summary.inaccessible_in_paperless) > 20 else ""),
            )
        if summary.errors:
            for err in summary.errors:
                print(f"  error: {err}", file=sys.stderr)
    return 1 if summary.errors else 0


def cmd_worker_ingest(args: argparse.Namespace) -> int:
    settings = get_settings()
    get_engine()
    paperless = PaperlessClient(
        base_url=settings.paperless_base_url,
        timeout_seconds=settings.paperless_timeout_seconds,
    )
    if args.once:
        session = get_session_factory()()
        try:
            worker = IngestionWorker(session, paperless)
            worker.run_once()
            return 0
        finally:
            session.close()

    while True:
        session = get_session_factory()()
        try:
            worker = IngestionWorker(session, paperless)
            worked = worker.run_once()
        except Exception:
            worked = False
        finally:
            session.close()
        if not worked:
            import time

            time.sleep(args.idle_sleep)
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "reconcile":
        raise SystemExit(cmd_reconcile(args))
    if args.command == "worker":
        if args.worker_command == "ingest":
            raise SystemExit(cmd_worker_ingest(args))
    parser.error(f"Unknown command {args.command}")


if __name__ == "__main__":
    main()
