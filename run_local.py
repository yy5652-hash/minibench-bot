"""Run the forecasting bot on this computer instead of GitHub Actions.

Replaces the old every-20-minutes GitHub Actions schedule. Start it with

    poetry run python run_local.py              # loop: publish every 20 min
    poetry run python run_local.py --once       # a single publishing pass
    poetry run python run_local.py --dry-run    # loop without publishing

Keys are read from `.env` by main.py. Each pass is logged to `logs/`. A lock
file stops two copies from forecasting at the same time, which is what the
workflow's concurrency group used to guarantee.
"""

import argparse
import datetime
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"
LOCK_FILE = ROOT / ".run_local.lock"
# GitHub Actions killed a run after 50 minutes; keep the same ceiling.
RUN_TIMEOUT_SECONDS = 50 * 60


def acquire_lock():
    """Return an open, locked file handle, or None if another run holds it.

    The OS drops the lock when the process exits, so a crash leaves no stale lock.
    """
    handle = open(LOCK_FILE, "a+")
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def run_once(mode: str, publish: bool) -> int:
    LOG_DIR.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = LOG_DIR / f"{mode}-{stamp}.log"
    command = [sys.executable, str(ROOT / "main.py"), "--mode", mode]
    if publish:
        command.append("--publish")
    print(f"[{stamp}] {' '.join(command[1:])} -> {log_path.name}", flush=True)
    with open(log_path, "w", encoding="utf-8") as log:
        try:
            result = subprocess.run(
                command,
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=RUN_TIMEOUT_SECONDS,
            )
            code = result.returncode
        except subprocess.TimeoutExpired:
            log.write(f"\nTimed out after {RUN_TIMEOUT_SECONDS} seconds\n")
            code = 124
    print(f"    exit code {code}", flush=True)
    return code


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the bot locally on a loop")
    parser.add_argument(
        "--mode",
        choices=["minibench", "tournament", "metaculus_cup", "test_questions"],
        default="tournament",
        help="Passed to main.py (default: tournament = FutureEval + MiniBench)",
    )
    parser.add_argument(
        "--interval-minutes",
        type=float,
        default=20,
        help="Minutes between the start of each pass (default: 20)",
    )
    parser.add_argument("--once", action="store_true", help="Run one pass and exit")
    parser.add_argument(
        "--dry-run", action="store_true", help="Do not publish to Metaculus"
    )
    args = parser.parse_args()

    lock = acquire_lock()
    if lock is None:
        sys.exit("Another run_local.py is already running")
    try:
        while True:
            started = time.monotonic()
            code = run_once(args.mode, publish=not args.dry_run)
            if args.once:
                sys.exit(code)
            wait = args.interval_minutes * 60 - (time.monotonic() - started)
            time.sleep(max(wait, 0))
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        lock.close()


if __name__ == "__main__":
    main()
