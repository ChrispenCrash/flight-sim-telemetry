"""Terminal output formatters for telemetry snapshots."""

from __future__ import annotations

import csv
import io
import json
import sys
from typing import Any, TextIO

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from msfs_telemetry.collector import TelemetrySnapshot, filter_values


def render_snapshot(
    snapshot: TelemetrySnapshot,
    *,
    fmt: str,
    active_only: bool = False,
    search: str | None = None,
    output: TextIO | None = None,
    console: Console | None = None,
) -> str | None:
    values = filter_values(snapshot.values, active_only=active_only, search=search)
    if fmt == "json":
        payload = _snapshot_payload(snapshot, values)
        text = json.dumps(payload, indent=2, default=str)
        _write(text, output)
        return text
    if fmt == "jsonl":
        payload = _snapshot_payload(snapshot, values)
        text = json.dumps(payload, default=str)
        _write(text, output)
        return text
    if fmt == "csv":
        text = _format_csv(values)
        _write(text, output)
        return text
    if fmt == "table":
        panel = _build_table_panel(snapshot, active_only=active_only, search=search)
        target = console or Console(file=output or sys.stdout)
        target.print(panel)
        return None
    return None


def stream_table(
    get_snapshot,
    *,
    active_only: bool = False,
    search: str | None = None,
    refresh_rate: float = 4.0,
) -> None:
    console = Console()
    with Live(console=console, refresh_per_second=refresh_rate, screen=False) as live:
        while True:
            snapshot = get_snapshot()
            live.update(_build_table_panel(snapshot, active_only=active_only, search=search))
            try:
                import time

                time.sleep(1.0 / refresh_rate)
            except KeyboardInterrupt:
                break


def _snapshot_payload(snapshot: TelemetrySnapshot, values: dict[str, Any]) -> dict[str, Any]:
    return {
        "timestamp": snapshot.timestamp,
        "connected": snapshot.connected,
        "aircraft_title": snapshot.aircraft_title,
        "batch_count": snapshot.batch_count,
        "variable_count": len(values),
        "telemetry": values,
    }


def _format_csv(values: dict[str, Any]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["variable", "value"])
    for key in sorted(values):
        writer.writerow([key, values[key]])
    return buffer.getvalue()


def _build_table_panel(
    snapshot: TelemetrySnapshot,
    *,
    active_only: bool,
    search: str | None,
) -> Panel:
    values = filter_values(snapshot.values, active_only=active_only, search=search)
    header = Table.grid(expand=True)
    header.add_column()
    header.add_row(
        Text(
            f"Aircraft: {snapshot.aircraft_title or 'unknown'}  |  "
            f"Variables: {len(values)}  |  "
            f"Batches: {snapshot.batch_count}",
            style="bold cyan",
        )
    )

    table = Table(show_header=True, header_style="bold magenta", expand=True)
    table.add_column("Variable", style="green", no_wrap=True)
    table.add_column("Value", style="white")

    for key in sorted(values):
        table.add_row(key, _format_value(values[key]))

    return Panel(Group(header, table), title="MSFS 2024 Telemetry", border_style="blue")


def _format_value(value: Any) -> str:
    if isinstance(value, float):
        if abs(value) >= 1000 or (abs(value) > 0 and abs(value) < 0.01):
            return f"{value:.6g}"
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def _write(text: str, output: TextIO | None) -> None:
    stream = output or sys.stdout
    stream.write(text)
    if not text.endswith("\n"):
        stream.write("\n")
    stream.flush()
