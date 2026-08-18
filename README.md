# MSFS 2024 Telemetry Terminal

A terminal application that connects to **Microsoft Flight Simulator 2024** over [SimConnect](https://docs.flightsimulator.com/msfs2024/html/6_Programming_APIs/SimConnect/SimConnect_SDK.htm) and outputs all available simulation variable (SimVar) telemetry.

## Requirements

- **Windows** (SimConnect is a Windows API)
- **Microsoft Flight Simulator 2024** running and in an active flight (not paused on the main menu)
- **Python 3.10+**
- **SimConnect.dll** (ships with MSFS; the `simconnect-H` package locates it automatically)

## Installation

```powershell
git clone https://github.com/flight-sim-telemetry/flight-sim-telemetry.git
cd flight-sim-telemetry
pip install -e ".[simconnect]"
```

The SimVar catalog (`scvars.json`) is bundled with the package. To refresh it from the latest SDK scrape:

```powershell
python scripts/fetch_simvars_catalog.py
```

## Quick start

Verify connectivity:

```powershell
msfs-telemetry ping
```

Stream all telemetry in a live terminal table:

```powershell
msfs-telemetry stream
```

Take a one-shot JSON snapshot:

```powershell
msfs-telemetry stream --once --format json
```

Show only non-zero values:

```powershell
msfs-telemetry stream --active-only
```

Filter by variable name:

```powershell
msfs-telemetry stream --search "AIRSPEED"
```

Export to a file:

```powershell
msfs-telemetry stream --once --format csv -o telemetry.csv
```

## Commands

| Command | Description |
|---------|-------------|
| `msfs-telemetry ping` | Test SimConnect connection and show aircraft title |
| `msfs-telemetry info` | Show catalog statistics (no sim required) |
| `msfs-telemetry list` | List known SimVar names from the SDK catalog |
| `msfs-telemetry stream` | Stream live telemetry from the simulator |

### `stream` options

| Option | Default | Description |
|--------|---------|-------------|
| `--format` | `table` | Output format: `table`, `json`, `jsonl`, or `csv` |
| `--once` | off | Read one snapshot and exit |
| `--active-only` | off | Hide zero/empty values |
| `--search` | — | Filter variables by substring |
| `--batch-size` | `150` | SimVars per SimConnect request |
| `--max-index` | `4` | Highest index for indexed SimVars (engines, tanks, etc.) |
| `--period` | `second` | Delay between batch rotations |
| `--refresh-rate` | `4` | Terminal refresh rate (table mode) |

## How it works

MSFS exposes thousands of **SimVars** (simulation variables) documented in the [MSFS 2024 SDK](https://docs.flightsimulator.com/msfs2024/html/6_Programming_APIs/SimVars/Simulation_Variables.htm). This tool:

1. Loads the full SDK SimVar catalog (~1,250 base variables, ~1,900 expanded with engine/tank indexes)
2. Connects to the running simulator via SimConnect (`simconnect-H`)
3. Reads variables in batches (SimConnect limits how many can be requested at once)
4. Rotates through all batches and prints the merged telemetry to your terminal

Indexed variables (e.g. `GENERAL ENG RPM:1` through `:4`) are expanded automatically for multi-engine aircraft.

## Output formats

- **table** — Live-updating Rich table in the terminal (default)
- **json** — Pretty-printed JSON snapshot with metadata
- **jsonl** — One JSON object per line (for logging pipelines)
- **csv** — Variable/value pairs for spreadsheets

## Troubleshooting

**"SimConnect is only available on Windows"** — Run this tool on the same Windows PC where MSFS 2024 is installed.

**"simconnect-H is required"** — Install the optional dependency: `pip install msfs-telemetry[simconnect]`

**Connection timeout** — Make sure MSFS is running, you are in an active flight (not the main menu), and the sim is not paused.

**Missing variables** — Some SimVars only apply to specific aircraft types or require named indexes (`'COMPONENT'_n` syntax). The catalog covers all documented SDK variables; aircraft-specific L-vars require separate tooling.

## License

MIT
