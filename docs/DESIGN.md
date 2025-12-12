# VizFlow Design Document

> TB-scale data analysis and visualization library
> `import vizflow as vf`

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Core Abstractions](#3-core-abstractions)
4. [Enrichment System](#4-enrichment-system)
5. [Operations](#5-operations)
6. [Execution](#6-execution)
7. [Package Structure](#7-package-structure)
8. [Implementation Plan](#8-implementation-plan)
9. [Appendix: Design Decisions](#appendix-a-design-decisions)
10. [Appendix: Discussion Log](#appendix-b-discussion-log)

---

## 1. Overview

### 1.1 Purpose

VizFlow is a general-purpose big data analysis and visualization framework for:
- TB-scale time-series data processing
- Multi-dimensional aggregation with interactive exploration
- Composable, functional pipeline design

**Primary use case**: Financial market data analysis (alpha evaluation, post-trade analysis)

### 1.2 Execution Model

```
┌─────────────────┬─────────────────────────┬──────────────────────────────┐
│ Stage           │ Environment             │ Purpose                      │
├─────────────────┼─────────────────────────┼──────────────────────────────┤
│ Map (per-date)  │ Cluster (100s of nodes) │ Raw data → partial results   │
│ Reduce/Explore  │ Single machine (2TB RAM)│ Aggregate partials, analysis │
│ Visualize       │ Single machine          │ Dash + Plotly dashboards     │
└─────────────────┴─────────────────────────┴──────────────────────────────┘
```

### 1.3 Data Characteristics

| Property     | Value                                          |
|--------------|------------------------------------------------|
| Input format | `{prefix}_{YYYYMMDD}.feather` (one file/day)   |
| Scale        | ~300 days, ~5GB/day, thousands of symbols/file |
| Partitioning | Pre-partitioned by date (no shuffle needed)    |

### 1.4 Technology Stack

- **Data Engine**: Polars (lazy evaluation)
- **Visualization**: Dash + Plotly
- **Storage**: Feather (input), Parquet (output)

---

## 2. Architecture

### 2.1 Data Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              SETUP (once)                                │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Calendar File ──► vf.calendar.load() ──► calendar_df                   │
│                                                                          │
│   ┌────────────┬───────────────────┬───────────────────┐                │
│   │ date       │ prev_trading_day  │ next_trading_day  │                │
│   ├────────────┼───────────────────┼───────────────────┤                │
│   │ 20240102   │ 20231229          │ 20240103          │                │
│   └────────────┴───────────────────┴───────────────────┘                │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                     PER-DATE PROCESSING (cluster)                        │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌────────────┐    ┌─────────────────────────────────────────────────┐ │
│   │ Raw Data   │───►│ User Pipeline Function                          │ │
│   │ + Calendar │    │                                                 │ │
│   └────────────┘    │  df = vf.parse_time(df, ctx.market)             │ │
│                     │  df = enricher.run(df)                          │ │
│                     │  df = vf.forward_return(df, horizons=[...])     │ │
│                     │  df = vf.bin(df, widths={...})                  │ │
│                     │  df = vf.aggregate(df, group_by=[...])          │ │
│                     │                                                 │ │
│                     └───────────────────────┬─────────────────────────┘ │
│                                             ▼                            │
│                                 ┌────────────────────┐                  │
│                                 │ partials/{date}.pq │                  │
│                                 └────────────────────┘                  │
└──────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                   EXPLORATION (single machine, 2TB RAM)                  │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   df = pl.scan_parquet("partials/*.parquet")                            │
│   result = df.filter(...).group_by(...).agg(...).collect()              │
│                                                                          │
│   vf.viz.heatmap(df, x="time_bin", y="alpha_bin", z="weighted_return")  │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Processing Pipeline

```
Raw Data ──► Enrichment ──► Binning ──► Aggregation ──► Partial Result
             (FIFO, tags)   (discretize)  (group_by)     (per-date)
```

---

## 3. Core Abstractions

### 3.1 Config

Central configuration for a pipeline run.

```python
@dataclass
class Config:
    # === Paths ===
    input_dir: Path
    output_dir: Path
    input_pattern: str = "{date}.feather"
    calendar_path: Path | None = None

    # === Market ===
    market: str = "CN"  # CN, KR, crypto, hkex_northbound

    # === Column Mapping ===
    # Maps semantic names to actual column names
    columns: dict[str, str] = field(default_factory=dict)
    # Example: {"timestamp": "ticktime", "price": "mid", "symbol": "ukey"}

    # === Binning ===
    binwidths: dict[str, float] = field(default_factory=dict)
    # Example: {"alpha": 1e-4, "return": 1e-4}

    # === Aggregation ===
    group_by: list[str] = field(default_factory=list)
    metrics: dict[str, pl.Expr] = field(default_factory=dict)

    # === Analysis ===
    horizons: list[int] = field(default_factory=list)  # Forward return horizons (seconds)
    time_cutoff: int | None = None  # e.g., 143000000 for 14:30:00

    # === Helpers ===
    def col(self, semantic: str) -> str:
        """Get actual column name from semantic name."""
        return self.columns.get(semantic, semantic)

    def get_file_path(self, date: str) -> Path:
        """Get input file path for a date."""
        return self.input_dir / self.input_pattern.format(date=date)
```

### 3.2 Context

Runtime context passed to pipeline functions.

```python
@dataclass
class Context:
    config: Config
    calendar: pl.DataFrame
    market: Market
    date: str

    def col(self, semantic: str) -> str:
        """Shortcut to config.col()."""
        return self.config.col(semantic)
```

### 3.3 Market

Market-specific trading sessions and time handling.

```python
@dataclass
class Session:
    start: str  # "HH:MM"
    end: str    # "HH:MM"

@dataclass
class Market:
    name: str
    sessions: list[Session]

    def elapsed_seconds(self, time: datetime) -> int:
        """Convert wall-clock time to continuous trading seconds."""
        ...

# === Presets ===
CN = Market(
    name="CN",
    sessions=[
        Session(start="09:30", end="11:30"),  # Morning (2 hours)
        Session(start="13:00", end="15:00"),  # Afternoon (2 hours)
    ]
)
# Total: 4 hours = 14,400 seconds

CRYPTO = Market(name="crypto", sessions=[Session(start="00:00", end="24:00")])
```

**elapsed_seconds calculation (CN market)**:
```
Morning:   elapsed = (hour - 9) * 3600 + (minute - 30) * 60 + second
Afternoon: elapsed = 7200 + (hour - 13) * 3600 + minute * 60 + second

Example:
  09:30:00 → 0
  11:29:59 → 7199
  13:00:00 → 7200
  15:00:00 → 14400
```

---

## 4. Enrichment System

The enrichment system adds computed columns/rows to raw data in a single pass.

### 4.1 Design Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Enricher                                │
├─────────────────────────────────────────────────────────────────┤
│  Components:                                                    │
│  ┌─────────────────┐    ┌─────────────────────────────────────┐ │
│  │  State Class    │    │  Tag Rules                          │ │
│  │  (user-defined) │    │  - FIFOMatch (row-expanding)        │ │
│  │                 │    │  - TagCondition (column-adding)     │ │
│  │  - entry_queue  │    │  - TagRunning (stateful column)     │ │
│  │  - running_pnl  │    │  - Custom rules...                  │ │
│  └─────────────────┘    └─────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  Processing:                                                    │
│  For each symbol (grouped):                                     │
│    state.reset(symbol)                                          │
│    For each row (sorted by time):                               │
│      For each rule:                                             │
│        outputs = rule.process(row, state)                       │
│      Collect outputs → new columns/rows                         │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Enrichment Types

| Type              | Example       | Rows   | Description                    |
|-------------------|---------------|--------|--------------------------------|
| **Row-Expanding** | FIFOMatch     | N → M  | Splits trades, adds rows       |
| **Column-Adding** | TagCondition  | N → N  | Adds computed columns          |

**Important**: Row-expanding rules must track original row index to preserve ALL columns when splitting.

### 4.3 Base Classes

```python
class State:
    """Base class for user-defined state. Reset per symbol."""

    def reset(self, symbol: str) -> None:
        """Called when starting a new symbol."""
        pass


class TagRule:
    """Base class for enrichment rules."""

    @property
    def output_columns(self) -> list[str]:
        """Columns this rule will add."""
        raise NotImplementedError

    def process(self, row: dict, state: State) -> dict | list[dict]:
        """
        Process a single row.

        Returns:
            dict: Single output row (column-adding)
            list[dict]: Multiple output rows (row-expanding)
        """
        raise NotImplementedError
```

### 4.4 Built-in Rules

```python
class FIFOMatch(TagRule):
    """
    FIFO entry/exit matching with trade splitting.

    Row-expanding: One exit trade may split into multiple matched trades
    if it closes multiple entries.
    """
    output_columns = ["matched_entry_id", "matched_qty", "holding_period", "is_closed"]

    def __init__(
        self,
        side_col: str,
        qty_col: str,
        time_col: str,
        price_col: str,
        entry_side: str = "B",
        exit_side: str = "S"
    ):
        ...

    def process(self, row: dict, state: State) -> list[dict]:
        # Returns list because one exit may match multiple entries
        ...


class TagCondition(TagRule):
    """Tag rows matching a condition."""

    def __init__(self, name: str, condition: Callable[[dict], bool]):
        self.name = name
        self.condition = condition

    @property
    def output_columns(self) -> list[str]:
        return [self.name]

    def process(self, row: dict, state: State) -> dict:
        return {self.name: self.condition(row)}


class TagRunning(TagRule):
    """Tag with running (cumulative) statistics."""

    def __init__(
        self,
        name: str,
        update_fn: Callable[[Any, dict], Any],
        initial: Any = 0
    ):
        self.name = name
        self.update_fn = update_fn
        self.initial = initial

    @property
    def output_columns(self) -> list[str]:
        return [self.name]

    def process(self, row: dict, state: State) -> dict:
        val = state.running.get(self.name, self.initial)
        new_val = self.update_fn(val, row)
        state.running[self.name] = new_val
        return {self.name: new_val}
```

### 4.5 Enricher

```python
class Enricher:
    """Single-pass enrichment with pluggable rules."""

    def __init__(
        self,
        rules: list[TagRule],
        by: str = "symbol",           # Group by column
        sort_by: str = "timestamp",   # Sort within group
        state_class: type[State] | None = None
    ):
        self.rules = rules
        self.by = by
        self.sort_by = sort_by
        self.state_class = state_class or State

    def run(self, df: pl.LazyFrame) -> pl.LazyFrame:
        """Apply all rules in one pass, return df with new columns."""
        ...
```

### 4.6 Usage Example

```python
# Define custom state
class MyState(vf.State):
    def reset(self, symbol):
        self.entry_queue = []      # For FIFO matching
        self.running_pnl = 0       # Custom tracking

# Create enricher
enricher = vf.Enricher(
    rules=[
        vf.FIFOMatch(
            side_col="side",
            qty_col="quantity",
            time_col="elapsed_seconds",
            price_col="price"
        ),
        vf.TagCondition("is_large", lambda r: r["quantity"] > 10000),
        vf.TagCondition("is_late", lambda r: r["elapsed_seconds"] > 12600),  # After 14:30
        vf.TagRunning("trade_count", lambda prev, row: prev + 1, initial=0),
    ],
    by="symbol",
    sort_by="elapsed_seconds",
    state_class=MyState
)

# Use in pipeline
df = enricher.run(df)
```

---

## 5. Operations

All operations are **pure functions** that take a LazyFrame and return a LazyFrame.

### 5.1 parse_time

Convert timestamp to continuous trading seconds.

```python
def parse_time(
    df: pl.LazyFrame,
    market: Market,
    timestamp_col: str = "timestamp"
) -> pl.LazyFrame:
    """
    Add elapsed_seconds column based on market sessions.

    Args:
        df: Input DataFrame
        market: Market definition with sessions
        timestamp_col: Name of timestamp column

    Returns:
        DataFrame with elapsed_seconds column added
    """
```

### 5.2 forward_return

Calculate forward returns at specified horizons.

```python
def forward_return(
    df: pl.LazyFrame,
    horizons: list[int],
    price_col: str = "price",
    time_col: str = "elapsed_seconds",
    symbol_col: str = "symbol"
) -> pl.LazyFrame:
    """
    Add forward return columns for each horizon.

    Args:
        df: Input DataFrame
        horizons: List of horizon seconds [60, 300, 600]
        price_col: Price column for return calculation
        time_col: Time column for horizon lookup
        symbol_col: Symbol column for grouping

    Returns:
        DataFrame with return_{h} columns added

    Example:
        horizons=[60, 300] adds columns: return_60, return_300
    """
```

### 5.3 bin

Discretize continuous values into bins.

```python
def bin(
    df: pl.LazyFrame,
    widths: dict[str, float]
) -> pl.LazyFrame:
    """
    Add bin columns for specified columns.

    Args:
        df: Input DataFrame
        widths: Column name to bin width mapping

    Returns:
        DataFrame with {col}_bin columns added

    Formula:
        bin_value = round(raw_value / binwidth)
        actual_value = bin_value * binwidth  # To recover

    Example:
        widths={"alpha": 1e-4} adds alpha_bin column
    """
```

### 5.4 aggregate

Group and aggregate data.

```python
def aggregate(
    df: pl.LazyFrame,
    group_by: list[str],
    metrics: dict[str, pl.Expr]
) -> pl.LazyFrame:
    """
    Aggregate data with custom metrics.

    Args:
        df: Input DataFrame
        group_by: Columns to group by
        metrics: Name to Polars expression mapping

    Returns:
        Aggregated DataFrame

    Example:
        metrics = {
            "count": pl.len(),
            "total_qty": pl.col("quantity").sum(),
            "vwap": pl.col("notional").sum() / pl.col("quantity").sum(),
        }
    """
```

---

## 6. Execution

### 6.1 API

```python
def run(
    pipeline_fn: Callable[[pl.LazyFrame, Context], pl.LazyFrame],
    config: Config,
    date: str,
    save: bool = True
) -> pl.DataFrame:
    """Run pipeline for a single date."""

def run_batch(
    pipeline_fn: Callable[[pl.LazyFrame, Context], pl.LazyFrame],
    config: Config,
    dates: list[str],
    parallel: bool = True,
    skip_existing: bool = True
) -> None:
    """Run pipeline for multiple dates."""

def run_cluster(
    pipeline_fn: Callable[[pl.LazyFrame, Context], pl.LazyFrame],
    config: Config,
    dates: list[str]
) -> list[str]:
    """Generate cluster job commands for ailab."""
```

### 6.2 Complete Pipeline Example

```python
import vizflow as vf
import polars as pl

# === Configuration ===
config = vf.Config(
    input_dir=Path("/data/trades"),
    output_dir=Path("/data/partials"),
    input_pattern="trades_{date}.feather",
    market="CN",
    columns={
        "timestamp": "ticktime",
        "price": "mid",
        "symbol": "ukey",
        "quantity": "qty",
    },
    binwidths={"alpha": 1e-4, "return": 1e-4},
    horizons=[60, 300, 600],
    group_by=["alpha_bin", "return_bin", "side"],
    metrics={
        "count": pl.len(),
        "total_qty": pl.col("quantity").sum(),
        "total_notional": pl.col("notional").sum(),
    },
)

# === Enricher ===
enricher = vf.Enricher(
    rules=[
        vf.FIFOMatch(
            side_col="side",
            qty_col="quantity",
            time_col="elapsed_seconds",
            price_col="price"
        ),
    ],
    by="symbol",
    sort_by="elapsed_seconds",
)

# === Pipeline Function ===
def process_day(df: pl.LazyFrame, ctx: vf.Context) -> pl.LazyFrame:
    # Parse time
    df = vf.parse_time(df, ctx.market, ctx.col("timestamp"))

    # Enrich (FIFO matching)
    df = enricher.run(df)

    # Forward returns
    df = vf.forward_return(
        df,
        horizons=ctx.config.horizons,
        price_col=ctx.col("price"),
        symbol_col=ctx.col("symbol")
    )

    # Bin
    df = vf.bin(df, ctx.config.binwidths)

    # Aggregate
    df = vf.aggregate(df, ctx.config.group_by, ctx.config.metrics)

    return df

# === Run ===
# Single date
result = vf.run(process_day, config, date="20241001")

# Batch (parallel)
vf.run_batch(process_day, config, dates=["20241001", "20241002", "20241003"])

# Cluster
commands = vf.run_cluster(process_day, config, dates=vf.calendar.range("20240101", "20241231"))
```

---

## 7. Package Structure

```
vizflow/
├── __init__.py      # Public API exports
├── config.py        # Config, Context dataclasses
├── calendar.py      # Trading calendar utilities
├── market.py        # Market, Session, presets (CN, CRYPTO)
├── enrichment.py    # State, TagRule, Enricher, FIFOMatch, etc.
├── ops.py           # parse_time, forward_return, bin, aggregate
├── run.py           # run, run_batch, run_cluster
├── io.py            # load, save, scan
└── viz.py           # heatmap, line, dashboard
```

**Public API** (`__init__.py`):
```python
# Config
from .config import Config, Context

# Market
from .market import Market, Session, CN, CRYPTO

# Calendar
from . import calendar

# Enrichment
from .enrichment import State, TagRule, Enricher, FIFOMatch, TagCondition, TagRunning

# Operations
from .ops import parse_time, forward_return, bin, aggregate

# Execution
from .run import run, run_batch, run_cluster

# I/O
from .io import load, save, scan

# Visualization
from . import viz
```

---

## 8. Implementation Plan

### Phase 1: Foundation
| # | File | Components |
|---|------|------------|
| 1 | `config.py` | Config, Context dataclasses |
| 2 | `calendar.py` | load(), generate(), range() |
| 3 | `market.py` | Market, Session, CN preset, elapsed_seconds |
| 4 | `io.py` | load(), save(), scan() |

### Phase 2: Enrichment
| # | File | Components |
|---|------|------------|
| 5 | `enrichment.py` | State, TagRule base classes |
| 6 | `enrichment.py` | Enricher (row-by-row processing) |
| 7 | `enrichment.py` | FIFOMatch rule |
| 8 | `enrichment.py` | TagCondition, TagRunning rules |

### Phase 3: Core Operations
| # | File | Components |
|---|------|------------|
| 9 | `ops.py` | parse_time() |
| 10 | `ops.py` | forward_return() |
| 11 | `ops.py` | bin() |
| 12 | `ops.py` | aggregate() |

### Phase 4: Execution
| # | File | Components |
|---|------|------------|
| 13 | `run.py` | run() |
| 14 | `run.py` | run_batch() |
| 15 | `run.py` | run_cluster() |

### Phase 5: Visualization
| # | File | Components |
|---|------|------------|
| 16 | `viz.py` | heatmap(), line() |
| 17 | `viz.py` | dashboard() |

---

## Appendix A: Design Decisions

### A.1 API Style: Functional + Sugar

**Decision**: Style C (Functional) with convenience wrappers

```python
# Core: Pure functions
def process_day(df: pl.LazyFrame, ctx: Context) -> pl.LazyFrame:
    df = vf.parse_time(df, ctx.market)
    df = vf.forward_return(df, ctx.config.horizons)
    ...
    return df

# Sugar: Convenience wrappers
vf.run(process_day, config, dates=[...], parallel=True)
```

**Rationale**:
- Maximum flexibility for custom logic
- Easy conditional branching
- Plain Python, easy to debug
- No framework lock-in

### A.2 Enrichment: Pluggable Rules

**Decision**: Enricher class with pluggable TagRule instances

**Rationale**:
- Single pass through data (efficient)
- User controls what state to maintain
- Composable: add/remove rules freely
- Separation: FIFO logic vs condition tagging vs running stats

### A.3 Metrics: User-Defined Polars Expressions

**Decision**: Pass raw `pl.Expr` instead of pre-built Metric classes

```python
metrics = {
    "vwap": pl.col("notional").sum() / pl.col("quantity").sum(),
}
```

**Rationale**:
- Full Polars expressiveness
- No need to wrap every aggregation function
- Easy to add custom metrics

### A.4 Market Abstraction

**Decision**: Configurable Market class, not hardcoded

**Supported markets**:
- `CN` - China A-shares (09:30-11:30, 13:00-15:00)
- `KR` - Korea KRX
- `crypto` - 24/7
- `hkex_northbound` - HK-China connect

### A.5 Calendar as DataFrame

**Decision**: Generate calendar as Polars DataFrame with prev/next trading day

**Rationale**:
- Can be joined with data using Polars
- Enables overnight return calculation
- No external dependency (Bizday)

---

## Appendix B: Discussion Log

### Session 1 (2024-12-11)

**Clarifications received**:
1. Raw data already partitioned by date (all symbols in one file)
2. Need replay/tagging system (FIFO matching, trade splitting, holding periods)
3. Partial results are N-dimensional with multiple stats per cell
4. Cluster for map → Single machine (2TB/100+ cores) for reduce/explore
5. Dash + Plotly for visualization
6. Both batch and interactive important, batch first
7. Want clean-slate design (existing code won't bias)

### Session 2 (2024-12-11)

**Trade Matching**:
- FIFO matching: within a single day, by symbol
- Unclosed trades: tagged as "unclosed"
- Start with vectorized operations, leave room for stateful strategies

**Granularity**:
- Date = partition key (not a dimension in aggregation)
- Typically 2D, max 4D
- 2-6 stats per cell

**Cluster**:
- Platform: `ailab create job` (custom cloud)
- VizFlow provides functions callable from job scripts

### Open Questions

| # | Question | Status |
|---|----------|--------|
| Q7 | What needs configuration beyond column names? | Pending |
| Q10 | Should VizFlow generate job scripts? | Pending |

### Data Schema Reference

**Input** (`alpha_{date}.feather`):
```
Columns: GlobalExTime, ticktime, ukey, alpha1, alpha2, AskPrice1, BidPrice1
Derived: mid = (AskPrice1 + BidPrice1) / 2
```

**Enriched** (after FIFO):
```
Columns: ukey, alphaTs, fillPrice, matched_qty, holding_period, close_markout, orderSide
Derived: fillNotional = matched_qty * fillPrice
```

### Time Handling Reference

```
CN Market:
  Morning:   09:30 - 11:30 (2 hours)
  Lunch:     11:30 - 13:00 (break)
  Afternoon: 13:00 - 15:00 (2 hours)

elapsed_seconds formula:
  Morning:   (hour - 9) * 3600 + (minute - 30) * 60 + second
  Afternoon: 7200 + (hour - 13) * 3600 + minute * 60 + second
```

### Binning Reference

```python
bin_value = round(raw_value / binwidth)  # Integer bin index
actual_value = bin_value * binwidth       # To recover

# Typical widths:
ALPHA_BINWIDTH = 1e-4    # 1 bps
MARKOUT_BINWIDTH = 1e-4  # 1 bps
```
