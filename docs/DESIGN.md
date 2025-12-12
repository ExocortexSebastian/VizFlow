# VizFlow Design Document

> TB-scale data analysis and visualization library
> `import vizflow as vf`

---

## Table of Contents

### Part 1: Foundation
1. [Overview & Architecture](#1-overview--architecture)
2. [Schema & Data Quality](#2-schema--data-quality)

### Part 2: Processing
3. [Pipeline Stages](#3-pipeline-stages)

### Part 3: Execution
4. [Running Pipelines](#4-running-pipelines)

### Part 4: Reference
5. [Operations Catalog](#5-operations-catalog)
6. [Package Structure](#6-package-structure)

### Appendices
- [A. Design Decisions](#appendix-a-design-decisions)
- [B. Discussion Log](#appendix-b-discussion-log)

---

# Part 1: Foundation

## 1. Overview & Architecture

### 1.1 Purpose

VizFlow is a general-purpose big data analysis and visualization framework for:
- **TB-scale time-series data processing**
- **Multi-dimensional aggregation** with interactive exploration
- **Composable, functional pipeline** design

**Primary use case:** Financial market data analysis (alpha evaluation, post-trade analysis)

### 1.2 Execution Model

**Map-Reduce-Visualize Pattern:**

```
┌─────────────────┬─────────────────────────┬──────────────────────────────┐
│ Stage           │ Environment             │ Purpose                      │
├─────────────────┼─────────────────────────┼──────────────────────────────┤
│ Map (per-date)  │ Cluster (100s of nodes) │ Raw data → partial results   │
│ Reduce/Explore  │ Single machine (2TB RAM)│ Aggregate partials, analysis │
│ Visualize       │ Single machine          │ Dash + Plotly dashboards     │
└─────────────────┴─────────────────────────┴──────────────────────────────┘
```

**Key characteristics:**
- **Date-partitioned**: One file per trading day (~5GB)
- **Lazy evaluation**: Polars LazyFrame throughout
- **Materialization points**: After Replay, After Aggregation
- **Functional composition**: `df.pipe(op1).pipe(op2).pipe(op3)`

### 1.3 Design Principles

1. **Polars-native**: No abstraction over Polars, extend it
2. **Lazy by default**: Defer computation until necessary
3. **Date-based partitioning**: No shuffle, perfect parallelism
4. **User-defined metrics**: Full Polars expression power
5. **Functional API**: Pure functions, easy to test and compose

### 1.4 Technology Stack

- **Data Engine**: Polars (lazy evaluation)
- **Visualization**: Dash + Plotly
- **Storage**: Feather (input), Parquet (output)
- **Cluster**: ailab (custom cloud platform)

---

## 2. Schema & Data Quality

### 2.1 The Problem

Real-world data has quality issues:

| Issue | Example | Impact |
|-------|---------|--------|
| **Float precision errors** | `qty = 1.00000002` should be `1` | Type mismatches in aggregation |
| **Column name drift** | `ticktime` → `tick_time` | Pipeline breaks on new data |
| **Type inconsistency** | Same column is `int` on some dates, `float` on others | Polars schema conflicts |
| **Missing columns** | New data adds fields | Old code ignores new columns |

### 2.2 Solution: Schema in Config

**Column mapping** (semantic → actual):

```python
config = vf.Config(
    columns={
        "timestamp": "ticktime",   # Semantic → Actual
        "price": "close",
        "volume": "vol",
        "symbol": "ukey"
    }
)

# Use semantic names in code
df = vf.parse_time(df, timestamp_col=config.col("timestamp"))
# Actual: timestamp_col="ticktime"
```

**Type casting** (future feature):

```python
config = vf.Config(
    # Schema with type casting
    schema={
        "qty": {"load_as": pl.Float64, "cast_to": pl.Int64},
        "price": {"load_as": pl.Float64, "cast_to": pl.Float64},
    }
)

# VizFlow will:
# 1. Load qty as Float64 (handles 1.00000002)
# 2. Cast to Int64 (becomes 1)
```

### 2.3 Schema Evolution Strategy

**Backward compatibility:**
- Old code works with new data (ignore unknown columns)
- New code works with old data (use defaults for missing columns)

**Version tracking:**
- Partial results include schema version metadata
- Alert if version changes unexpectedly

**Migration:**
- Reprocess historical dates when schema changes
- Use `run_batch(skip_existing=False)` to force reprocessing

### 2.4 Partitioning Strategy

**Primary Partition: By Date**

Files organized as one file per trading day (e.g., `20241201.parquet`).

**Why date-based partitioning?**

| Benefit | Description |
|---------|-------------|
| **Parallelizable** | 300 dates = 300 independent jobs |
| **No shuffle** | No cross-date data movement |
| **Clear failure boundary** | If date X fails, others succeed |
| **Incremental** | Add new dates without reprocessing old ones |
| **Natural unit** | Trading days are independent in finance |

**Partition sizing:**
- **Target:** ~5GB per date (one trading day)
- **Too small** (<100MB): Overhead dominates
- **Too large** (>50GB): Memory pressure, slow retries

**Hot partitions:**
- **Problem:** Market crash days may have 10x volume
- **Detection:** Log processing time, alert if >3x median
- **Mitigation:** Polars lazy evaluation handles automatically

---

# Part 2: Processing

## 3. Pipeline Stages

### 3.1 Overview

**Revised 5-Stage Pipeline** (with split enrichment):

```
┌──────────────────────────────────────────────────────────────┐
│ Stage 0: CONFIGURATION                                       │
│ ─────────────────────────────────────────────────────────    │
│ config = vf.Config(market="CN", columns={...})               │
│ ctx = vf.Context(config, calendar, market, date)             │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ Stage 1: MINIMAL ENRICHMENT (before Replay)                 │
│ ─────────────────────────────────────────────────────────    │
│ df = vf.parse_time(df, market=ctx.market)                   │
│                                                               │
│ Why: Replay needs elapsed_seconds for FIFO sorting          │
│ Execution: Lazy (no materialization)                         │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ Stage 2: REPLAY (Stateful Processing)                       │
│ ─────────────────────────────────────────────────────────    │
│ enricher = vf.Enricher(rules=[vf.FIFOMatch(...)])            │
│ df = enricher.run(df)  # FIFO matching                       │
│                                                               │
│ Execution: Eager (must materialize for stateful processing) │
│ ⚠️  MATERIALIZATION POINT 1                                   │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ Stage 3: FULL ENRICHMENT (after Replay)                     │
│ ─────────────────────────────────────────────────────────    │
│ df = vf.forward_return(df, horizons=[60, 300])              │
│ df = vf.overnight_return(df, calendar)                       │
│                                                               │
│ Why: Don't need these for FIFO matching                     │
│ Execution: Lazy (back to LazyFrame)                          │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ Stage 4: AGGREGATION                                         │
│ ─────────────────────────────────────────────────────────    │
│ df = vf.bin(df, widths={"alpha": 1e-4})                     │
│ partial = vf.aggregate(df, group_by=[...], metrics={...})   │
│                                                               │
│ Execution: Lazy → Eager (collects to DataFrame)             │
│ Output: Per-date partial results (saved to disk)            │
│ ⚠️  MATERIALIZATION POINT 2                                   │
└──────────────────────────────────────────────────────────────┘
```

**Critical ordering:**
1. **Minimal Enrich** → Replay → **Full Enrich** → Aggregate
2. Replay receives LazyFrame with `elapsed_seconds` (from parse_time)
3. forward_return happens AFTER Replay (doesn't affect FIFO)

### 3.2 Configuration (Stage 0)

**Config:** Central configuration for pipeline run

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
    columns: dict[str, str] = field(default_factory=dict)
    # Example: {"timestamp": "ticktime", "price": "mid"}

    # === Binning ===
    binwidths: dict[str, float] = field(default_factory=dict)

    # === Aggregation ===
    group_by: list[str] = field(default_factory=list)
    metrics: dict[str, pl.Expr] = field(default_factory=dict)

    # === Analysis ===
    horizons: list[int] = field(default_factory=list)
    time_cutoff: int | None = None

    # === Helpers ===
    def col(self, semantic: str) -> str:
        """Get actual column name from semantic name."""
        return self.columns.get(semantic, semantic)

    def get_file_path(self, date: str) -> Path:
        """Get input file path for a date."""
        return self.input_dir / self.input_pattern.format(date=date)
```

**Context:** Runtime state passed to pipeline functions

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

**Market:** Trading sessions and time handling

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

**elapsed_seconds calculation (CN market):**
```
Morning:   elapsed = (hour - 9) * 3600 + (minute - 30) * 60 + second
Afternoon: elapsed = 7200 + (hour - 13) * 3600 + minute * 60 + second

Example:
  09:30:00 → 0
  11:29:59 → 7199
  13:00:00 → 7200
  15:00:00 → 14400
```

### 3.3 Minimal Enrichment (Stage 1)

**Purpose:** Add ONLY what Replay needs

**Operations:**
- `parse_time()` - Convert timestamp to `elapsed_seconds`

**Why minimal?**
- Replay (FIFO) only needs time for sorting
- Other enrichments (`forward_return`) can happen AFTER replay
- Keeps replay input simple

**Example:**
```python
# BEFORE Replay: minimal enrichment
df = vf.parse_time(df, market=ctx.market, timestamp_col=ctx.col("timestamp"))
# Adds: elapsed_seconds column
```

### 3.4 Replay (Stage 2)

**Purpose:** Stateful processing (FIFO matching, trade splitting)

**Enrichment System:**

```python
class State:
    """Base class for user-defined state. Reset per symbol."""
    def reset(self, symbol: str) -> None:
        pass

class TagRule:
    """Base class for enrichment rules."""
    @property
    def output_columns(self) -> list[str]:
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

**Built-in rules:**

| Rule | Type | Purpose |
|------|------|---------|
| `FIFOMatch` | Row-expanding | FIFO trade matching with splitting |
| `TagCondition` | Column-adding | Add boolean columns based on conditions |
| `TagRunning` | Column-adding | Add cumulative statistics |

**FIFOMatch example:**

```python
enricher = vf.Enricher(
    rules=[
        vf.FIFOMatch(
            side_col="side",
            qty_col="quantity",
            time_col="elapsed_seconds",  # Uses output from parse_time!
            price_col="price",
            entry_side="B",
            exit_side="S"
        ),
    ],
    by="symbol",
    sort_by="elapsed_seconds",
)

# Run FIFO matching
df = enricher.run(df)
# Output columns: matched_entry_id, matched_qty, holding_period, is_closed
```

**Why eager (materialized)?**
- Stateful processing requires full dataset in memory
- Row-expanding (trade splitting) can't be done lazily
- This is MATERIALIZATION POINT 1

### 3.5 Full Enrichment (Stage 3)

**Purpose:** Add columns that DON'T affect Replay

**Operations:**
- `forward_return()` - Calculate future returns
- `overnight_return()` - Calculate cross-day returns
- Custom transformations

**Example:**
```python
# AFTER Replay: full enrichment
df = vf.forward_return(
    df,
    horizons=[60, 300, 600],  # 1min, 5min, 10min
    price_col=ctx.col("price"),
    time_col="elapsed_seconds",
    symbol_col=ctx.col("symbol")
)
# Adds: return_60, return_300, return_600 columns
```

**Why after Replay?**
- FIFO doesn't need forward returns
- Keeps replay input focused
- More flexible pipeline composition

### 3.6 Aggregation (Stage 4)

**Purpose:** Create per-date partial results for cross-date analysis

**Operations:**

1. **Binning** - Discretize continuous values

```python
df = vf.bin(df, widths={"alpha": 1e-4, "return": 1e-4})
# Adds: alpha_bin, return_bin columns

# Formula: bin_value = round(raw_value / binwidth)
```

2. **Aggregation** - Group by bins and compute metrics

```python
partial = vf.aggregate(
    df,
    group_by=["alpha_bin", "return_bin", "side"],
    metrics={
        "count": pl.len(),
        "total_qty": pl.col("quantity").sum(),
        "vwap": pl.col("notional").sum() / pl.col("quantity").sum(),
    }
)
# Output: per-date partial results (saved to partials/{date}.parquet)
```

**This is MATERIALIZATION POINT 2** - results saved to disk.

---

# Part 3: Execution

## 4. Running Pipelines

### 4.1 Local Execution

**Use cases:**
- Development and testing
- Small datasets (<10 dates)
- Quick iteration

**API:**

```python
# Single date
def run(
    pipeline_fn: Callable[[pl.LazyFrame, Context], pl.LazyFrame],
    config: Config,
    date: str,
    save: bool = True
) -> pl.DataFrame:
    """Run pipeline for a single date."""

# Multiple dates (parallel on local machine)
def run_batch(
    pipeline_fn: Callable[[pl.LazyFrame, Context], pl.LazyFrame],
    config: Config,
    dates: list[str],
    parallel: bool = True,
    skip_existing: bool = True
) -> None:
    """Run pipeline for multiple dates in parallel."""
```

**Example:**

```python
import vizflow as vf
import polars as pl

# === Configuration ===
config = vf.Config(
    input_dir=Path("/data/trades"),
    output_dir=Path("/data/partials"),
    market="CN",
    columns={"timestamp": "ticktime", "price": "mid"},
    binwidths={"alpha": 1e-4},
    horizons=[60, 300],
)

# === Pipeline Function ===
def process_day(df: pl.LazyFrame, ctx: vf.Context) -> pl.LazyFrame:
    # Stage 1: Minimal enrichment
    df = vf.parse_time(df, ctx.market, ctx.col("timestamp"))

    # Stage 2: Replay (FIFO)
    enricher = vf.Enricher(rules=[vf.FIFOMatch(...)])
    df = enricher.run(df)

    # Stage 3: Full enrichment
    df = vf.forward_return(df, horizons=ctx.config.horizons)

    # Stage 4: Aggregation
    df = vf.bin(df, ctx.config.binwidths)
    df = vf.aggregate(df, group_by=[...], metrics={...})

    return df

# === Run Locally ===
# Single date
result = vf.run(process_day, config, date="20241001")

# Batch (parallel)
vf.run_batch(
    process_day,
    config,
    dates=["20241001", "20241002", "20241003"],
    parallel=True,
    skip_existing=True
)
```

### 4.2 Cluster Execution

**Use cases:**
- Production pipelines
- Large datasets (100+ dates)
- TB-scale data

**API:**

```python
def run_cluster(
    pipeline_fn: Callable[[pl.LazyFrame, Context], pl.LazyFrame],
    config: Config,
    dates: list[str]
) -> list[str]:
    """Generate cluster job commands for ailab."""
```

**Example:**

```python
# Generate job commands
commands = vf.run_cluster(
    process_day,
    config,
    dates=vf.calendar.range("20240101", "20241231")  # 300 days
)

# Output: list of ailab commands
# ["ailab create job --name=vf_20240101 ...",
#  "ailab create job --name=vf_20240102 ...",
#  ...]

# Submit jobs to cluster
for cmd in commands:
    os.system(cmd)
```

**Cluster characteristics:**
- Each date = independent job
- Perfect parallelism (no dependencies)
- Linear speedup (100 dates on 100 nodes = 1x processing time)

### 4.3 Local vs Cluster Comparison

| Aspect | Local (`run_batch`) | Cluster (`run_cluster`) |
|--------|---------------------|-------------------------|
| **Environment** | Single machine | 100s of nodes |
| **Parallelism** | Limited by cores | Unlimited (add more nodes) |
| **Data size** | <50 dates | 300+ dates |
| **Speed** | Minutes | Seconds (with enough nodes) |
| **Use case** | Development, testing | Production |
| **Cost** | Free (local compute) | Pay for cluster |

---

# Part 4: Reference

## 5. Operations Catalog

### 5.1 Time Operations

**parse_time** - Convert timestamp to elapsed_seconds

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

### 5.2 Return Calculations

**forward_return** - Calculate forward returns at specified horizons

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

### 5.3 Transformations

**bin** - Discretize continuous values into bins

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

**aggregate** - Group and aggregate data

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

### 5.4 Stateful Enrichment

**Enricher** - Single-pass enrichment with pluggable rules

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

**FIFOMatch** - FIFO trade matching with splitting

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
```

**TagCondition** - Tag rows matching a condition

```python
class TagCondition(TagRule):
    """Tag rows matching a condition."""

    def __init__(self, name: str, condition: Callable[[dict], bool]):
        self.name = name
        self.condition = condition
```

**TagRunning** - Tag with running (cumulative) statistics

```python
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
```

---

## 6. Package Structure

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

# Appendices

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

### A.6 Split Enrichment (Before/After Replay)

**Decision**: Minimal enrichment before Replay, full enrichment after

**Rationale**:
- Replay only needs `elapsed_seconds` for sorting
- forward_return doesn't affect FIFO matching
- More flexible pipeline composition
- Faster replay (less data to materialize)

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

### Session 3 (2024-12-12)

**Design Refinements**:
- Split enrichment into before/after replay stages
- Elevate schema & data quality to Section 2
- Clarify local vs cluster execution patterns
- Reorganize document into Parts for better navigation

### Open Questions

| # | Question | Status |
|---|----------|--------|
| Q7 | What needs configuration beyond column names? | Resolved - See Section 2.2 |
| Q10 | Should VizFlow generate job scripts? | Yes - `run_cluster()` generates commands |

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
