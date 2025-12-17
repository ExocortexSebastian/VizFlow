# VizFlow

TB-scale data analysis and visualization library for exploratory data analysis.

## Installation

```bash
pip install vizflow
```

For development:
```bash
pip install vizflow[dev]
```

## Quick Start

```python
import vizflow as vf

# Check version
print(vf.__version__)
```

## Features

- **Config**: Global configuration with column mapping presets
- **Column Presets**: Auto-rename columns from different data sources
  - `ylin` - Yuanzhao's meords trade format (52 columns)
  - `jyao_v20251114` - jyao's alpha format
- **Market**: Trading session handling (CN, crypto, etc.)
- **I/O**: `scan_trade()`, `scan_alpha()` with automatic column mapping
- **Operations**: `parse_time`, `bin`, `aggregate`
- **Schema Evolution**: Type casting on load (e.g., Float64 → Int64)

## Column Naming Convention

| Type | Naming | Examples |
|------|--------|----------|
| Predictor (X) | `x_*` | `x_10s`, `x_60s`, `x_3m` |
| Target (Y) | `y_*` | `y_60s`, `y_3m` |
| Time suffix | ≤60s: `s`, >60s: `m` | `x_60s`, `x_3m` |

## Example

```python
import vizflow as vf
from pathlib import Path

# Configure with column preset
config = vf.Config(
    alpha_dir=Path("data/alpha"),
    alpha_pattern="alpha_{date}.feather",
    column_preset="jyao_v20251114",  # Auto-rename columns
    market="CN",
)
vf.set_config(config)

# Scan with automatic column mapping
df = vf.scan_alpha("20251114")
# Columns: x_10s, x_60s, x_3m, x_30m, bid_px0, ask_px0, ...
```

## Planned Features

- **Enrichment**: Trade tagging, FIFO matching
- **Execution**: Single-date, batch, and cluster processing
- **Visualization**: Plotly/Dash dashboards

## Requirements

- Python >= 3.10
- Polars >= 0.20.0

## License

MIT
