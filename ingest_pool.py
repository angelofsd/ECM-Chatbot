"""Parallel ingestion runner for ECM RAG chatbot.

Launches multiple ingestion workers so we can overlap PDF parsing and
embedding calls. Each worker reuses the existing `ingest_document`
pipeline, meaning we preserve all memory guards (chunk limits, mini
batches, etc.) while drastically reducing wall-clock time.

Usage examples:
    python ingest_pool.py --workers 4                       # default resume
    python ingest_pool.py --workers 4 --max-pdfs 50         # cap run
    python ingest_pool.py --workers 3 --dry-run             # preview only

The script resumes automatically by skipping any `documents.source_path`
that already exists in the database.
"""

from __future__ import annotations

import argparse
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from tqdm import tqdm

# Force pipeline to use Postgres + OpenAI embeddings.
os.environ.setdefault("USE_SQLITE", "false")
os.environ.setdefault("USE_OPENAI_EMBEDDINGS", "true")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY must be set before running ingest_pool.py "
        "(required for parallel OpenAI embedding requests)."
    )

from api.config import OCR_OUTPUT_DIR  # noqa: E402  (import after env setup)
from api.ingest import db, ingest_document, guess_department_from_path  # noqa: E402
from api.db import Document  # noqa: E402


@dataclass
class IngestionTask:
    """Work item handed to a worker process."""

    path: str
    department: str
    source_type: str = "pdf"

    def as_tuple(self) -> Tuple[str, str, str]:
        """Return a tuple for easy pickling."""
        return self.path, self.department, self.source_type


def ensure_tables() -> None:
    """Make sure required tables exist before we spawn workers."""
    db.init_sync()
    db.create_all_tables()


def discover_remaining_pdfs(pdf_dir: Path, limit: Optional[int] = None) -> List[IngestionTask]:
    """Collect PDF paths that have not yet been ingested."""
    ensure_tables()

    if not pdf_dir.exists():
        raise FileNotFoundError(f"PDF directory does not exist: {pdf_dir}")

    all_pdfs = sorted(pdf_dir.glob("**/*.pdf"))

    session = db.get_session()
    try:
        processed_paths = {
            row.source_path for row in session.query(Document.source_path).all()
        }
    finally:
        session.close()

    tasks: List[IngestionTask] = []
    for file_path in all_pdfs:
        if str(file_path) in processed_paths:
            continue
        tasks.append(
            IngestionTask(
                path=str(file_path),
                department=guess_department_from_path(file_path),
            )
        )
        if limit and len(tasks) >= limit:
            break

    return tasks


def _worker_initializer() -> None:
    """Initializer executed in each worker process."""
    # Ensure env vars are visible in children and kill runaway Git watchers.
    os.environ.setdefault("USE_SQLITE", "false")
    os.environ.setdefault("USE_OPENAI_EMBEDDINGS", "true")

    # Import inside initializer so each process triggers ingest safeguards.
    from api.ingest import kill_git_processes

    try:
        kill_git_processes()
    except Exception:
        pass


def _process_task(task_tuple: Tuple[str, str, str]) -> Tuple[str, bool, str]:
    """Worker entrypoint to ingest a single document."""
    file_path_str, department, source_type = task_tuple
    file_path = Path(file_path_str)

    ok, message = ingest_document(file_path, source_type, department)
    return file_path_str, ok, message


def run_pool(tasks: Iterable[IngestionTask], workers: int, dry_run: bool) -> None:
    """Execute ingestion tasks in a process pool."""
    task_list = list(tasks)
    if not task_list:
        print("✓ Nothing to ingest — all PDFs are up to date.")
        return

    print(f"Dispatching {len(task_list)} PDFs across {workers} worker(s)...")

    if dry_run:
        for item in task_list:
            print(f"DRY-RUN: would ingest {item.path} (dept={item.department})")
        return

    with ProcessPoolExecutor(max_workers=workers, initializer=_worker_initializer) as executor:
        futures = {
            executor.submit(_process_task, task.as_tuple()): task.path for task in task_list
        }

        successes = 0
        failures = 0

        for future in tqdm(as_completed(futures), total=len(futures), desc="Pool"):
            path = futures[future]
            try:
                _, ok, message = future.result()
            except Exception as exc:
                failures += 1
                tqdm.write(f"FAIL {path}: {exc}")
                continue

            if ok:
                successes += 1
                tqdm.write(f"OK   {path}: {message}")
            else:
                failures += 1
                tqdm.write(f"FAIL {path}: {message}")

    print()
    print(f"Complete: {successes} success, {failures} failed")


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Parallel PDF ingestion runner")
    parser.add_argument(
        "--workers",
        type=int,
        default=int(os.getenv("INGEST_WORKERS", "4")),
        help="Number of worker processes (default 4)",
    )
    parser.add_argument(
        "--max-pdfs",
        type=int,
        help="Ingest at most N PDFs this run",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List PDFs that would be ingested without executing",
    )
    args = parser.parse_args()

    tasks = discover_remaining_pdfs(OCR_OUTPUT_DIR, limit=args.max_pdfs)
    run_pool(tasks, workers=max(1, args.workers), dry_run=args.dry_run)


if __name__ == "__main__":
    main()
