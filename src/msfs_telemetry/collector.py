"""SimConnect telemetry collection for MSFS 2024."""

from __future__ import annotations

import platform
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from msfs_telemetry.catalog import SimVarSpec, build_field_map, iter_simvar_specs


@dataclass
class TelemetrySnapshot:
    timestamp: float
    values: dict[str, Any]
    batch_count: int
    connected: bool = True
    aircraft_title: str | None = None


@dataclass
class CollectorConfig:
    app_name: str = "MSFS Telemetry Terminal"
    batch_size: int = 150
    connect_timeout: float = 10.0
    max_index: int = 4
    include_indexed: bool = True
    period: str = "second"


class TelemetryCollector:
    """Collect SimVar telemetry from MSFS 2024 in rotating batches."""

    def __init__(self, config: CollectorConfig | None = None) -> None:
        self.config = config or CollectorConfig()
        self._lock = threading.Lock()
        self._values: dict[str, Any] = {}
        self._aircraft_title: str | None = None
        self._connected = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._simconnect = None
        self._specs = list(
            iter_simvar_specs(
                max_index=self.config.max_index,
                include_indexed=self.config.include_indexed,
            )
        )
        self._field_map = build_field_map(self._specs)
        self._batches = self._chunk_fields(self._field_map, self.config.batch_size)

    @property
    def specs(self) -> list[SimVarSpec]:
        return self._specs

    @property
    def batch_count(self) -> int:
        return len(self._batches)

    def ensure_simconnect(self) -> None:
        if platform.system() != "Windows":
            raise RuntimeError(
                "SimConnect is only available on Windows with MSFS 2024 running. "
                "Start the simulator, then run this application on the same machine."
            )
        try:
            from simconnect_native import SimConnect  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "simconnect-H is required to connect to MSFS. "
                "Install with: pip install msfs-telemetry[simconnect]"
            ) from exc
        self._SimConnect = SimConnect

    def connect(self) -> None:
        self.ensure_simconnect()
        self._simconnect = self._SimConnect.connect(
            self.config.app_name,
            timeout=self.config.connect_timeout,
            open_timeout=self.config.connect_timeout,
        )
        self._connected = True
        try:
            self._aircraft_title = self._simconnect.get_string("TITLE", timeout=2.0)
        except Exception:
            self._aircraft_title = None

    def close(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        if self._simconnect is not None:
            try:
                self._simconnect.close()
            except Exception:
                pass
        self._connected = False

    def snapshot(self) -> TelemetrySnapshot:
        with self._lock:
            return TelemetrySnapshot(
                timestamp=time.time(),
                values=dict(self._values),
                batch_count=len(self._batches),
                connected=self._connected,
                aircraft_title=self._aircraft_title,
            )

    def poll_once(self) -> TelemetrySnapshot:
        """Read all batches once and return a snapshot."""
        self.ensure_simconnect()
        if self._simconnect is None:
            self.connect()
        assert self._simconnect is not None

        merged: dict[str, Any] = {}
        for batch in self._batches:
            try:
                merged.update(self._simconnect.get_many(batch, timeout=2.0))
            except Exception:
                continue

        with self._lock:
            self._values.update(merged)
            return self.snapshot()

    def start_stream(self, on_update: Callable[[TelemetrySnapshot], None]) -> None:
        if self._thread and self._thread.is_alive():
            return

        def _worker() -> None:
            self.connect()
            assert self._simconnect is not None
            period = self._resolve_period()
            while not self._stop.is_set():
                for batch in self._batches:
                    if self._stop.is_set():
                        break
                    try:
                        values = self._simconnect.get_many(batch, timeout=2.0)
                        with self._lock:
                            self._values.update(values)
                    except Exception:
                        continue
                with self._lock:
                    snapshot = self.snapshot()
                on_update(snapshot)
                time.sleep(period)

        self._thread = threading.Thread(target=_worker, name="msfs-telemetry", daemon=True)
        self._thread.start()

    def wait(self) -> None:
        if self._thread:
            self._thread.join()

    def _resolve_period(self) -> float:
        mapping = {
            "frame": 1 / 30,
            "visual_frame": 1 / 60,
            "second": 1.0,
            "simframe": 1 / 30,
        }
        return mapping.get(self.config.period.lower(), 1.0)

    @staticmethod
    def _chunk_fields(
        fields: dict[str, tuple[str, str] | tuple[str, str, int]],
        batch_size: int,
    ) -> list[dict[str, tuple[str, str] | tuple[str, str, int]]]:
        items = list(fields.items())
        batches: list[dict[str, tuple[str, str] | tuple[str, str, int]]] = []
        for start in range(0, len(items), batch_size):
            chunk = items[start : start + batch_size]
            batches.append(dict(chunk))
        return batches


def filter_values(
    values: dict[str, Any],
    *,
    active_only: bool = False,
    search: str | None = None,
) -> dict[str, Any]:
    filtered: dict[str, Any] = {}
    query = search.lower() if search else None
    for key, value in values.items():
        if query and query not in key.lower():
            continue
        if active_only and _is_inactive(value):
            continue
        filtered[key] = value
    return filtered


def _is_inactive(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value == ""
    if isinstance(value, (int, float)):
        return value == 0
    return False
