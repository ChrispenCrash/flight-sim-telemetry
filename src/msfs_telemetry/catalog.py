"""Load and expand MSFS SimVar definitions from the SDK catalog."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

PACKAGE_DATA = Path(__file__).resolve().parent / "data" / "scvars.json"

SKIP_UNIT_MARKERS = (
    "struct:",
    "simconnect data",
    "pid struct",
    "xyz",
    "latlonalt",
    "initposition",
    "waypoint",
    "facilities",
)

STRING_UNITS = {"string", "stringv", "string256", "string128", "string64", "string32"}
BOOL_UNITS = {"bool", "boolean"}
INT_UNITS = {"enum", "mask", "flags", "bco16", "number"}


@dataclass(frozen=True, slots=True)
class SimVarSpec:
    name: str
    unit: str
    is_string: bool
    description: str = ""
    category: str = ""


def _normalize_unit(unit: str) -> str:
    return re.sub(r"\s+", " ", unit.strip().lower())


def _is_supported_unit(unit: str) -> bool:
    normalized = _normalize_unit(unit)
    if not normalized:
        return False
    return not any(marker in normalized for marker in SKIP_UNIT_MARKERS)


def _is_string_unit(unit: str) -> bool:
    return _normalize_unit(unit) in STRING_UNITS


def _catalog_path(path: Path | None = None) -> Path:
    return path or PACKAGE_DATA


def load_catalog(path: Path | None = None) -> dict:
    catalog_path = _catalog_path(path)
    if not catalog_path.exists():
        raise FileNotFoundError(
            f"SimVar catalog not found at {catalog_path}. "
            "Run: python scripts/fetch_simvars_catalog.py"
        )
    with catalog_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def iter_simvar_specs(
    catalog: dict | None = None,
    *,
    max_index: int = 4,
    include_indexed: bool = True,
) -> Iterable[SimVarSpec]:
    """Yield concrete SimVar names with units from the SDK catalog."""
    data = catalog or load_catalog()
    variables = data.get("VARIABLES", {})

    for _key, entry in sorted(variables.items(), key=lambda item: item[1]["name_std"]):
        name = entry["name_std"]
        unit = entry.get("units_std") or entry.get("units") or ""
        if not _is_supported_unit(unit):
            continue

        description = entry.get("description", "")
        category = entry.get("page", "")
        is_string = _is_string_unit(unit)
        indexed = bool(entry.get("indexed"))

        if indexed and include_indexed:
            for index in range(1, max_index + 1):
                yield SimVarSpec(
                    name=f"{name}:{index}",
                    unit="NULL" if is_string else unit,
                    is_string=is_string,
                    description=description,
                    category=category,
                )
        elif not indexed:
            yield SimVarSpec(
                name=name,
                unit="NULL" if is_string else unit,
                is_string=is_string,
                description=description,
                category=category,
            )


def build_field_map(
    specs: Iterable[SimVarSpec],
) -> dict[str, tuple[str, str] | tuple[str, str, int]]:
    """Build a unique-key map for simconnect-H field definitions."""
    fields: dict[str, tuple[str, str] | tuple[str, str, int]] = {}
    for spec in specs:
        key = _field_key(spec.name)
        if key in fields:
            continue
        if spec.is_string:
            fields[key] = (spec.name, "NULL", 11)  # SIMCONNECT_DATATYPE_STRINGV
        else:
            fields[key] = (spec.name, spec.unit)
    return fields


def _field_key(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()


def catalog_stats(catalog: dict | None = None) -> dict[str, int]:
    data = catalog or load_catalog()
    specs = list(iter_simvar_specs(data))
    return {
        "base_variables": len(data.get("VARIABLES", {})),
        "expanded_variables": len(specs),
        "string_variables": sum(1 for spec in specs if spec.is_string),
        "numeric_variables": sum(1 for spec in specs if not spec.is_string),
    }
