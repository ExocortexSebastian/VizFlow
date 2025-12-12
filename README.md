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

## Features (Planned)

- **Config**: Flexible column mapping and configuration
- **Market**: Trading session handling (CN, crypto, etc.)
- **I/O**: Load/save feather and parquet files
- **Operations**: parse_time, bin, aggregate, forward_return
- **Enrichment**: Trade tagging, FIFO matching
- **Execution**: Single-date, batch, and cluster processing
- **Visualization**: Plotly/Dash dashboards (future)

## Requirements

- Python >= 3.10
- Polars >= 0.20.0

## License

MIT
