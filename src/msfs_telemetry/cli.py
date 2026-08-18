"""Command-line interface for MSFS 2024 telemetry."""

from __future__ import annotations

import json
import sys
import time

import click
from rich.console import Console

from msfs_telemetry import __version__
from msfs_telemetry.catalog import catalog_stats, load_catalog
from msfs_telemetry.collector import CollectorConfig, TelemetryCollector, filter_values
from msfs_telemetry.display import render_snapshot, stream_table


console = Console(stderr=True)


@click.group()
@click.version_option(__version__, prog_name="msfs-telemetry")
def main() -> None:
    """Stream telemetry from Microsoft Flight Simulator 2024."""


@main.command("info")
@click.option(
    "--catalog",
    type=click.Path(exists=True, dir_okay=False, path_type=str),
    help="Path to scvars.json catalog file",
)
def info_cmd(catalog: str | None) -> None:
    """Show catalog statistics without connecting to the simulator."""
    data = load_catalog(catalog) if catalog else load_catalog()
    stats = catalog_stats(data)
    click.echo(json.dumps(stats, indent=2))


@main.command("list")
@click.option(
    "--catalog",
    type=click.Path(exists=True, dir_okay=False, path_type=str),
    help="Path to scvars.json catalog file",
)
@click.option("--search", "-s", help="Filter variables by substring")
@click.option("--limit", default=50, show_default=True, help="Maximum rows to print")
def list_cmd(catalog: str | None, search: str | None, limit: int) -> None:
    """List known SimVar names from the SDK catalog."""
    from msfs_telemetry.catalog import iter_simvar_specs

    specs = list(iter_simvar_specs(load_catalog(catalog) if catalog else None))
    if search:
        query = search.lower()
        specs = [spec for spec in specs if query in spec.name.lower()]

    for spec in specs[:limit]:
        click.echo(f"{spec.name}\t{spec.unit}")
    if len(specs) > limit:
        click.echo(f"... {len(specs) - limit} more", err=True)


@main.command("stream")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["table", "json", "jsonl", "csv"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format",
)
@click.option("--once", is_flag=True, help="Read one snapshot and exit")
@click.option("--active-only", is_flag=True, help="Hide zero/empty values")
@click.option("--search", "-s", help="Filter variables by substring")
@click.option("--batch-size", default=150, show_default=True, help="SimVars per SimConnect request")
@click.option("--max-index", default=4, show_default=True, help="Highest index for indexed SimVars")
@click.option("--period", default="second", show_default=True, help="Polling period between batch rotations")
@click.option("--refresh-rate", default=4.0, show_default=True, help="Terminal refresh rate for table mode")
@click.option("--output", "-o", type=click.File("w"), help="Write output to a file")
def stream_cmd(
    fmt: str,
    once: bool,
    active_only: bool,
    search: str | None,
    batch_size: int,
    max_index: int,
    period: str,
    refresh_rate: float,
    output,
) -> None:
    """Connect to MSFS 2024 and stream all available SimVar telemetry."""
    collector = TelemetryCollector(
        CollectorConfig(
            batch_size=batch_size,
            max_index=max_index,
            period=period,
        )
    )

    try:
        collector.ensure_simconnect()
    except RuntimeError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise SystemExit(1) from exc

    if once:
        try:
            collector.connect()
            snapshot = collector.poll_once()
            render_snapshot(
                snapshot,
                fmt=fmt,
                active_only=active_only,
                search=search,
                output=output,
            )
        except Exception as exc:
            console.print(f"[red]Failed to read telemetry:[/red] {exc}")
            raise SystemExit(1) from exc
        finally:
            collector.close()
        return

    if fmt == "table":
        latest = {"snapshot": collector.snapshot()}

        def on_update(snapshot):
            latest["snapshot"] = snapshot

        collector.start_stream(on_update)
        try:
            stream_table(
                lambda: latest["snapshot"],
                active_only=active_only,
                search=search,
                refresh_rate=refresh_rate,
            )
        finally:
            collector.close()
        return

    collector.start_stream(lambda snapshot: None)
    try:
        while True:
            snapshot = collector.snapshot()
            filtered = filter_values(
                snapshot.values,
                active_only=active_only,
                search=search,
            )
            snapshot.values = filtered
            render_snapshot(snapshot, fmt=fmt, output=output)
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        collector.close()


@main.command("ping")
def ping_cmd() -> None:
    """Verify SimConnect connectivity and print aircraft title."""
    collector = TelemetryCollector()
    try:
        collector.ensure_simconnect()
        collector.connect()
        snapshot = collector.snapshot()
        altitude = collector._simconnect.get("PLANE ALTITUDE", "feet", timeout=2.0)  # type: ignore[union-attr]
        click.echo(
            f"OK  connected to MSFS 2024\n"
            f"    aircraft: {snapshot.aircraft_title or 'unknown'}\n"
            f"    altitude: {altitude} ft\n"
            f"    catalog:  {len(collector.specs)} expanded SimVars in {collector.batch_count} batches"
        )
    except Exception as exc:
        console.print(f"[red]FAIL[/red] {exc}")
        raise SystemExit(1) from exc
    finally:
        collector.close()


if __name__ == "__main__":
    main()
