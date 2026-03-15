"""Wait command: block until tasks reach a target status."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import click

from lattice.cli.helpers import (
    load_project_config,
    output_error,
    require_root,
    resolve_task_id,
)
from lattice.cli.main import cli
from lattice.core.config import resolve_status_input
from lattice.storage.readers import read_task_events


def _check_tasks_status(
    lattice_dir: Path,
    task_ids: list[str],
    target_status: str,
) -> tuple[list[str], list[str]]:
    """Check which tasks have reached the target status.

    Returns (done_ids, pending_ids).
    """
    done: list[str] = []
    pending: list[str] = []

    for task_id in task_ids:
        snapshot_path = lattice_dir / "tasks" / f"{task_id}.json"
        if not snapshot_path.exists():
            pending.append(task_id)
            continue

        try:
            snapshot = json.loads(snapshot_path.read_text())
            if snapshot.get("status") == target_status:
                done.append(task_id)
            else:
                pending.append(task_id)
        except (json.JSONDecodeError, OSError):
            pending.append(task_id)

    return done, pending


def _get_latest_event(lattice_dir: Path, task_id: str) -> dict | None:
    """Read the most recent event for a task."""
    events = read_task_events(lattice_dir, task_id)
    return events[-1] if events else None


def _validate_event_line(line: str) -> dict | None:
    """Parse a JSONL line, returning None if malformed (guards against partial writes)."""
    line = line.strip()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


@cli.command("wait")
@click.argument("task_ids_str")
@click.option(
    "--status",
    "target_status",
    default="done",
    help="Target status to wait for (default: done).",
)
@click.option(
    "--timeout",
    default=600,
    type=int,
    help="Timeout in seconds (default: 600). 0 = no timeout.",
)
@click.option(
    "--poll-fallback",
    default=5,
    type=int,
    help="Poll interval in seconds if fswatch is unavailable (default: 5).",
)
@click.option("--json", "output_json", is_flag=True, help="Output structured JSON.")
@click.option("--quiet", is_flag=True, help="No progress output, just exit when done.")
def wait_cmd(
    task_ids_str: str,
    target_status: str,
    timeout: int,
    poll_fallback: int,
    output_json: bool,
    quiet: bool,
) -> None:
    """Wait for tasks to reach a target status.

    TASK_IDS is a comma-separated list of short IDs (e.g., SUB-55,SUB-56,SUB-57).

    Uses fswatch for instant filesystem-event detection when available,
    falls back to polling if fswatch is not installed.

    Examples:

        lattice wait SUB-55,SUB-56,SUB-57 --status done

        lattice wait SUB-55 --status review --timeout 300

        lattice wait SUB-55,SUB-56 --json
    """
    is_json = output_json
    lattice_dir = require_root(is_json)
    events_dir = lattice_dir / "events"

    # Resolve display names (e.g., "shipped" → "done") to canonical slugs
    config = load_project_config(lattice_dir)
    target_status = resolve_status_input(config, target_status) or target_status

    # Parse and resolve task IDs
    raw_ids = [t.strip() for t in task_ids_str.split(",") if t.strip()]
    if not raw_ids:
        output_error("No task IDs provided.", is_json)
        sys.exit(1)

    task_ids: list[str] = []
    short_id_map: dict[str, str] = {}  # full_id -> short_id
    for raw in raw_ids:
        full_id = resolve_task_id(lattice_dir, raw, is_json)
        task_ids.append(full_id)
        short_id_map[full_id] = raw

    total = len(task_ids)

    # Check if already satisfied
    done, pending = _check_tasks_status(lattice_dir, task_ids, target_status)
    if not pending:
        _emit_result(done, pending, target_status, short_id_map, is_json, quiet)
        return

    if not quiet and not is_json:
        click.echo(
            f"Waiting for {len(pending)}/{total} tasks to reach '{target_status}'..."
        )
        if done:
            done_names = ", ".join(short_id_map.get(t, t) for t in done)
            click.echo(f"  Already {target_status}: {done_names}")

    # Determine watch strategy
    has_fswatch = _check_fswatch()

    start_time = time.monotonic()

    if has_fswatch:
        _wait_with_fswatch(
            lattice_dir,
            events_dir,
            task_ids,
            target_status,
            timeout,
            short_id_map,
            is_json,
            quiet,
            start_time,
        )
    else:
        if not quiet and not is_json:
            click.echo("  (fswatch not found, using poll fallback)")
        _wait_with_poll(
            lattice_dir,
            task_ids,
            target_status,
            timeout,
            poll_fallback,
            short_id_map,
            is_json,
            quiet,
            start_time,
        )


def _check_fswatch() -> bool:
    """Check if fswatch is available."""
    try:
        subprocess.run(
            ["fswatch", "--version"],
            capture_output=True,
            timeout=5,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _wait_with_fswatch(
    lattice_dir: Path,
    events_dir: Path,
    task_ids: list[str],
    target_status: str,
    timeout: int,
    short_id_map: dict[str, str],
    is_json: bool,
    quiet: bool,
    start_time: float,
) -> None:
    """Watch for completions using fswatch (event-driven, near-instant)."""
    # Build set of event filenames we care about
    watched_files = {f"{tid}.jsonl" for tid in task_ids}

    cmd = ["fswatch", "-0", "--event", "Updated", "--event", "Created", str(events_dir)]
    if timeout > 0:
        # fswatch doesn't have a native timeout, so we use subprocess timeout
        pass

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)

    try:
        buffer = b""

        while True:
            # Check timeout
            elapsed = time.monotonic() - start_time
            if timeout > 0 and elapsed >= timeout:
                _handle_timeout(
                    lattice_dir, task_ids, target_status, short_id_map, is_json, quiet
                )
                return

            # Read from fswatch (with a short internal timeout to check overall timeout)
            read_timeout = min(5.0, (timeout - elapsed) if timeout > 0 else 5.0)
            try:
                import select

                ready, _, _ = select.select([proc.stdout], [], [], read_timeout)
                if not ready:
                    continue

                chunk = proc.stdout.read(4096)
                if not chunk:
                    break

                buffer += chunk

                # fswatch uses null-byte separators
                while b"\0" in buffer:
                    path_bytes, buffer = buffer.split(b"\0", 1)
                    changed_file = Path(path_bytes.decode().strip()).name

                    # Filter: only check if the changed file is one of our tasks
                    if changed_file not in watched_files:
                        continue

                    # Read the event file and check the latest event
                    task_id = changed_file.replace(".jsonl", "")
                    latest = _get_latest_event(lattice_dir, task_id)
                    if latest is None:
                        continue

                    # Validate the event is parseable (guards against partial writes)
                    event_type = latest.get("type", "")
                    new_status = latest.get("new_status", "")

                    # Only do the full check if this event looks like a status change
                    # to our target (optimization to avoid scanning all tasks on every event)
                    if event_type == "status_changed" and new_status == target_status:
                        done, pending = _check_tasks_status(
                            lattice_dir, task_ids, target_status
                        )
                        if not quiet and not is_json:
                            done_names = ", ".join(
                                short_id_map.get(t, t) for t in done
                            )
                            click.echo(
                                f"  Progress: {len(done)}/{len(task_ids)} "
                                f"({done_names})"
                            )
                        if not pending:
                            _emit_result(
                                done,
                                pending,
                                target_status,
                                short_id_map,
                                is_json,
                                quiet,
                            )
                            return

            except (OSError, ValueError):
                # select() can fail on some edge cases, fall through to retry
                continue

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def _wait_with_poll(
    lattice_dir: Path,
    task_ids: list[str],
    target_status: str,
    timeout: int,
    interval: int,
    short_id_map: dict[str, str],
    is_json: bool,
    quiet: bool,
    start_time: float,
) -> None:
    """Fallback: poll task snapshots at a regular interval."""
    while True:
        elapsed = time.monotonic() - start_time
        if timeout > 0 and elapsed >= timeout:
            _handle_timeout(
                lattice_dir, task_ids, target_status, short_id_map, is_json, quiet
            )
            return

        done, pending = _check_tasks_status(lattice_dir, task_ids, target_status)
        if not pending:
            _emit_result(done, pending, target_status, short_id_map, is_json, quiet)
            return

        if not quiet and not is_json:
            click.echo(
                f"  {len(done)}/{len(task_ids)} at '{target_status}', "
                f"checking again in {interval}s..."
            )

        time.sleep(interval)


def _emit_result(
    done: list[str],
    pending: list[str],
    target_status: str,
    short_id_map: dict[str, str],
    is_json: bool,
    quiet: bool,
) -> None:
    """Output the final result."""
    if is_json:
        click.echo(
            json.dumps(
                {
                    "ok": True,
                    "data": {
                        "status": target_status,
                        "completed": [short_id_map.get(t, t) for t in done],
                        "pending": [short_id_map.get(t, t) for t in pending],
                        "all_complete": len(pending) == 0,
                    },
                },
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )
    elif not quiet:
        done_names = ", ".join(short_id_map.get(t, t) for t in done)
        click.echo(f"All {len(done)} tasks reached '{target_status}': {done_names}")


def _handle_timeout(
    lattice_dir: Path,
    task_ids: list[str],
    target_status: str,
    short_id_map: dict[str, str],
    is_json: bool,
    quiet: bool,
) -> None:
    """Handle timeout — report what's done and what's still pending."""
    done, pending = _check_tasks_status(lattice_dir, task_ids, target_status)
    if is_json:
        click.echo(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": "timeout",
                        "message": f"Timed out waiting for tasks to reach '{target_status}'",
                    },
                    "data": {
                        "status": target_status,
                        "completed": [short_id_map.get(t, t) for t in done],
                        "pending": [short_id_map.get(t, t) for t in pending],
                        "all_complete": False,
                    },
                },
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )
    elif not quiet:
        pending_names = ", ".join(short_id_map.get(t, t) for t in pending)
        click.echo(f"Timeout. Still pending: {pending_names}")
    sys.exit(1)
