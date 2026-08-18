#!/usr/bin/env python3
"""Download the MSFS SimVar catalog from the pysimconnect project."""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

CATALOG_URL = (
    "https://raw.githubusercontent.com/patricksurry/pysimconnect/master/"
    "simconnect/scvars.json"
)
OUTPUT = Path(__file__).resolve().parents[1] / "src" / "msfs_telemetry" / "data" / "scvars.json"


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {CATALOG_URL} ...")
    with urllib.request.urlopen(CATALOG_URL, timeout=60) as response:
        payload = response.read()
    data = json.loads(payload)
    variable_count = len(data.get("VARIABLES", {}))
    OUTPUT.write_bytes(payload)
    print(f"Saved {variable_count} SimVar definitions to {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
