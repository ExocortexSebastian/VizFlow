# VizFlow Implementation Plan

> Implementation details, API specifications, and release process

---

## Table of Contents

### Part 1: Status & Roadmap
- [Current Status](#current-status)
- [Version Roadmap](#version-roadmap)

### Part 2: API Specification
- [Config & Context](#config--context)
- [Market & Session](#market--session)
- [Operations](#operations)
- [Enrichment System](#enrichment-system)
- [Execution](#execution)

### Part 3: Implementation Phases
- [Phase 0: Scaffolding](#phase-0-scaffolding-v010)
- [Phase 1: Config + Market](#phase-1-config--market-v020)
- [Phase 2: Core Operations](#phase-2-core-operations-v030-v040)
- [Phase 3: Enrichment + FIFO](#phase-3-enrichment--fifo-v050)
- [Phase 4: Forward Returns](#phase-4-forward-returns-v060)
- [Phase 5: Execution](#phase-5-execution-v070)
- [Phase 6: Visualization](#phase-6-visualization-v080)

### Part 4: Release Process
- [Versioning](#versioning)
- [Release Checklist](#release-checklist)

---

# Part 1: Status & Roadmap

## Current Status

**Current Version:** v0.4.0 (published to PyPI)
**Next Version:** v0.5.0 (Enrichment + FIFO)

| Component | Status | Version |
|-----------|--------|---------|
| Config, set_config, get_config | DONE | v0.4.0 |
| Market, Session, CN | DONE | v0.2.0 |
| parse_time | DONE | v0.3.0 |
| bin | DONE | v0.3.0 |
| aggregate | DONE | v0.3.0 |
| **Enrichment + FIFO** | **NEXT** | v0.5.0 |
| forward_return | TODO | v0.6.0 |
| run, run_batch, run_cluster | TODO | v0.7.0 |

## Version Roadmap

| Version | Features | Pipeline Stage |
|---------|----------|----------------|
| 0.1.0 | Scaffolding | - |
| 0.2.0 | Config, Market | Stage 0 |
| 0.3.0 | parse_time, bin, aggregate | Stage 1, 4 |
| 0.4.0 | Global config refactor | Stage 0 |
| **0.5.0** | **Enrichment + FIFO** | **Stage 2 (Replay)** |
| 0.6.0 | forward_return, calendar | Stage 3 |
| 0.7.0 | run, run_batch, run_cluster | Execution |
| 0.8.0 | Visualization (Dash) | Optional |
| 0.9.0 | API freeze, polish | Stabilization |
| 1.0.0 | Production release | Milestone |

---

# Part 2: API Specification

## Config & Context

### ColumnSchema

Schema for type casting on load.

```python
@dataclass
class ColumnSchema:
    cast_to: Any  # pl.DataType (e.g., pl.Int64, pl.Float64)
```

### Config

Central configuration for a pipeline run.

```python
@dataclass
class Config:
    # === Input Paths ===
    alpha_dir: Path | None = None
    alpha_pattern: str = "alpha_{date}.feather"
    trade_dir: Path | None = None
    trade_pattern: str = "trade_{date}.feather"
    calendar_path: Path | None = None

    # === Output Paths (2 materialization points) ===
    replay_dir: Path | None = None      # FIFO output (materialization 1)
    aggregate_dir: Path | None = None   # Aggregation output (materialization 2)

    # === Market ===
    market: str = "CN"

    # === Column Mapping (per datasource) ===
    alpha_columns: dict[str, str] = field(default_factory=dict)
    trade_columns: dict[str, str] = field(default_factory=dict)

    # === Schema Evolution ===
    alpha_schema: dict[str, ColumnSchema] = field(default_factory=dict)
    trade_schema: dict[str, ColumnSchema] = field(default_factory=dict)

    # === Aggregation ===
    binwidths: dict[str, float] = field(default_factory=dict)
    group_by: list[str] = field(default_factory=list)

    # === Analysis ===
    horizons: list[int] = field(default_factory=list)
    time_cutoff: int | None = None

    # === Helpers ===
    def col(self, semantic: str, source: str = "trade") -> str:
        """Get actual column name from semantic name."""
        if source == "alpha":
            return self.alpha_columns.get(semantic, semantic)
        return self.trade_columns.get(semantic, semantic)

    def get_alpha_path(self, date: str) -> Path:
        """Get alpha file path for a date."""

    def get_trade_path(self, date: str) -> Path:
        """Get trade file path for a date."""

    def get_replay_path(self, date: str, suffix: str = ".parquet") -> Path:
        """Get FIFO replay output path for a date."""

    def get_aggregate_path(self, date: str, suffix: str = ".parquet") -> Path:
        """Get aggregation output path for a date."""
```

### Context

Runtime state passed to pipeline functions.

```python
@dataclass
class Context:
    config: Config
    calendar: pl.DataFrame
    market: Market
    date: str

    def col(self, semantic: str, source: str = "trade") -> str:
        """Shortcut to config.col()."""
        return self.config.col(semantic, source)
```

### Global Config

```python
def set_config(config: Config) -> None:
    """Set the global config."""

def get_config() -> Config:
    """Get the global config. Raises RuntimeError if not set."""
```

### I/O Functions

Load data with automatic schema evolution.

```python
def load_alpha(date: str, config: Config | None = None) -> pl.LazyFrame:
    """Load alpha data with schema evolution applied."""

def load_trade(date: str, config: Config | None = None) -> pl.LazyFrame:
    """Load trade data with schema evolution applied."""

def load_calendar(config: Config | None = None) -> pl.DataFrame:
    """Load trading calendar."""
```

---

## Market & Session

### Session

```python
@dataclass
class Session:
    start: str  # "HH:MM"
    end: str    # "HH:MM"
```

### Market

```python
@dataclass
class Market:
    name: str
    sessions: list[Session]

    def elapsed_seconds(self, time: datetime) -> int:
        """Convert wall-clock time to continuous trading seconds."""
```

### Presets

```python
CN = Market(
    name="CN",
    sessions=[
        Session(start="09:30", end="11:30"),  # Morning (2 hours)
        Session(start="13:00", end="15:00"),  # Afternoon (2 hours)
    ]
)
# Total: 4 hours = 14,400 seconds
```

### elapsed_seconds Calculation

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

## Operations

### parse_time

Convert timestamp to elapsed_seconds.

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

### bin

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
    """
```

### aggregate

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

### forward_return

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
    """
```

---

## Enrichment System

### State

Base class for user-defined state.

```python
class State:
    """Per-symbol state that resets when symbol changes."""

    def reset(self, symbol: str) -> None:
        """Called when processing a new symbol."""
        pass
```

### TagRule

Base class for enrichment rules.

```python
class TagRule:
    """Base class for enrichment rules."""

    @property
    def output_columns(self) -> list[str]:
        """Column names this rule adds."""
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

### Enricher

Orchestrator that applies rules.

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
        """
        Apply all rules in one pass.

        Returns:
            DataFrame with new columns added
        """
```

### TagCondition

Tag rows matching a condition.

```python
class TagCondition(TagRule):
    """Add boolean column based on condition."""

    def __init__(self, name: str, condition: Callable[[dict], bool]):
        self.name = name
        self.condition = condition

    @property
    def output_columns(self) -> list[str]:
        return [self.name]

    def process(self, row: dict, state: State) -> dict:
        return {self.name: self.condition(row)}
```

### TagRunning

Tag with running (cumulative) statistics.

```python
class TagRunning(TagRule):
    """Add cumulative statistics column."""

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
```

### FIFOMatch

FIFO trade matching with splitting.

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
        self.side_col = side_col
        self.qty_col = qty_col
        self.time_col = time_col
        self.price_col = price_col
        self.entry_side = entry_side
        self.exit_side = exit_side

    def process(self, row: dict, state: FIFOState) -> list[dict]:
        """
        Process entry or exit trade.

        Entry: Add to queue
        Exit: Match against queue (FIFO), may return multiple rows
        """
```

---

## Execution

### run

Single date processing.

```python
def run(
    pipeline_fn: Callable[[pl.LazyFrame, Context], pl.LazyFrame],
    config: Config,
    date: str,
    save: bool = True
) -> pl.DataFrame:
    """Run pipeline for a single date."""
```

### run_batch

Multiple dates, parallel processing.

```python
def run_batch(
    pipeline_fn: Callable[[pl.LazyFrame, Context], pl.LazyFrame],
    config: Config,
    dates: list[str],
    parallel: bool = True,
    skip_existing: bool = True
) -> None:
    """Run pipeline for multiple dates in parallel."""
```

### run_cluster

Generate cluster job commands.

```python
def run_cluster(
    pipeline_fn: Callable[[pl.LazyFrame, Context], pl.LazyFrame],
    config: Config,
    dates: list[str]
) -> list[str]:
    """Generate cluster job commands for ailab."""
```

### Example Usage

```python
import vizflow as vf
import polars as pl
from pathlib import Path

# === Configuration ===
config = vf.Config(
    # Input Paths
    alpha_dir=Path("/data/alpha"),
    trade_dir=Path("/data/trade"),
    calendar_path=Path("/data/calendar.parquet"),
    # Output Paths (2 materialization points)
    replay_dir=Path("/data/replay"),         # FIFO output (materialization 1)
    aggregate_dir=Path("/data/partials"),    # Aggregation output (materialization 2)
    # Market
    market="CN",
    # Column Mapping
    alpha_columns={"timestamp": "ticktime", "price": "mid", "symbol": "ukey"},
    trade_columns={"timestamp": "fillTs", "price": "fillPrice", "symbol": "ukey"},
    # Schema Evolution
    trade_schema={"qty": vf.ColumnSchema(cast_to=pl.Int64)},  # 1.00000002 → 1
    # Aggregation
    binwidths={"alpha": 1e-4},
    # Analysis
    horizons=[60, 300],
)
vf.set_config(config)

# === Load Data (with schema evolution) ===
alpha = vf.load_alpha("20241001")  # LazyFrame
trade = vf.load_trade("20241001")  # LazyFrame, qty cast to Int64
calendar = vf.load_calendar()      # DataFrame

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

# === Run ===
vf.run(process_day, config, date="20241001")
vf.run_batch(process_day, config, dates=["20241001", "20241002", "20241003"])
```

---

# Part 3: Implementation Phases

## Phase 0: Scaffolding (v0.1.0)

**Status:** COMPLETE

- [x] Create directory structure
- [x] Write `pyproject.toml`
- [x] Write `vizflow/__init__.py`
- [x] Write `README.md`
- [x] Write `tests/test_import.py`
- [x] Build and publish to PyPI

---

## Phase 1: Config + Market (v0.2.0)

**Status:** COMPLETE

- [x] Create `vizflow/config.py`
  - Config dataclass with fields
  - `col(semantic)` method

- [x] Create `vizflow/market.py`
  - Session dataclass
  - Market dataclass
  - CN preset

- [x] Update `vizflow/__init__.py` exports
- [x] Create tests
- [x] Publish v0.2.0

---

## Phase 2: Core Operations (v0.3.0, v0.4.0)

**Status:** COMPLETE

### v0.3.0

- [x] Add `parse_time()` to ops.py
- [x] Add `bin()` to ops.py
- [x] Add `aggregate()` to ops.py
- [x] Create `tests/test_ops.py`
- [x] Publish v0.3.0

### v0.4.0

- [x] Add `set_config()` and `get_config()` to config.py
- [x] Refactor `parse_time()` to use global config
- [x] Update tests for global config pattern
- [x] Publish v0.4.0

---

## Phase 3: Enrichment + FIFO (v0.5.0)

**Status:** NEXT

> **Detailed plan:** See below for architecture, data flow, and implementation steps.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER INTERFACE                                 │
│  result = calc_fifo(df)  # No column params - uses Config               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATION LAYER                              │
│                           calc_fifo()                                    │
│  • Validates input columns via cfg.col()                                │
│  • Collects LazyFrame (MATERIALIZATION 1)                               │
│  • Coordinates pipeline stages                                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────┐         ┌───────────────┐         ┌───────────────┐
│  PREP STAGE   │         │ GROUPING STAGE│         │ MATCHING STAGE│
│ _prep_trades()│   ───►  │ _assign_      │   ───►  │ _match_fifo() │
│               │         │ position_     │         │               │
│ • signed_qty  │         │ groups()      │         │ • FIFO queue  │
│ • cumQty      │         │               │         │ • Trade split │
│ • jump split  │         │ • cumQty=0    │         │ • Entry/Exit  │
└───────────────┘         │   detection   │         │   tagging     │
                          └───────────────┘         └───────────────┘
```

### Key Concepts

**Position Lifecycle:**
```
cumQty = cumsum(signed_qty)  # per symbol
Each cumQty=0 → end of position group, start new group
```

**Jump Row Handling (Position Reversal):**
```
cumQty=100, then Sell 150
→ Split into: Sell 100 (closes group 1) + Sell 50 (opens group 2)
Detection: abs(sign(cumQty).diff()) == 2
```

**Entry/Exit Tagging:**
```
entry_side = first trade's side in group
trade_type = "Entry" if same side, "Exit" if opposite
```

### Output Schema

| Column | Type | Description |
|--------|------|-------------|
| entry_idx | Int64 | Original index of Entry trade |
| exit_idx | Int64 | Original index of Exit trade (None if unclosed) |
| entry_time | Float64 | Time of Entry |
| exit_time | Float64 | Time of Exit (None if unclosed) |
| matched_qty | Int64 | Quantity matched |
| holding_period | Float64 | exit_time - entry_time (inf if unclosed) |
| close_markout | Float64 | Return from Entry to Exit |
| is_closed | Boolean | Whether entry has been exited |
| entry_side | String | "B" or "S" |
| trade_type | String | "Entry" or "Exit" |

### Implementation Steps

**Step 0: Create docs/SCHEMA.md**
- [x] Document standard log columns from production
- [x] Document semantic → standard column mapping

**Step 1: Scaffold vizflow/fifo.py**
- [ ] Create file with section comments
- [ ] Define `calc_fifo()` signature

**Step 2: Prep Stage - _prep_trades()**
- [ ] `_compute_signed_qty()`: qty * sign(side)
- [ ] `_compute_cum_qty()`: cumsum per symbol
- [ ] `_split_jump_rows()`: split position reversals

**Step 3: Grouping Stage - _assign_position_groups()**
- [ ] Detect `cumQty=0` boundaries
- [ ] Assign unique group IDs per symbol

**Step 4: Matching Stage - _match_fifo()**
- [ ] `_fifo_match_group()`: Core FIFO algorithm
  - Entry queue with FIFO order
  - Exit matching with trade splitting
  - Preserve both entry_idx and exit_idx
- [ ] Handle unclosed: holding_period=inf

**Step 5: Orchestration - calc_fifo()**
- [ ] Use `get_config()` for column resolution
- [ ] Pipeline: prep → group → match
- [ ] Return as LazyFrame

**Step 6: Exports and Tests**
- [ ] Update `vizflow/__init__.py`
- [ ] Create `tests/test_fifo.py`

**Step 7: Publish v0.5.0**

### Test Cases

1. **cumQty:** Buy 100, Sell 100 → cumQty=[100, 0]
2. **Jump split:** Buy 100, Sell 150 → splits into (Sell 100, Sell 50)
3. **Position groups:** Multiple round-trips get different group IDs
4. **Simple match:** Buy 100 @ t=0, Sell 100 @ t=10 → holding_period=10
5. **Trade splitting:** Buy 50, Buy 50, Sell 80 → 2 output rows
6. **Unclosed:** Buy 100, no exit → holding_period=inf, is_closed=False
7. **exit_idx preserved:** Fixes pandas bug - both split rows have same exit_idx
8. **Entry/Exit tagging:** entry_side="B" means Buy=Entry, Sell=Exit
9. **Short selling:** First trade is Sell → entry_side="S"
10. **Multi-symbol:** Symbols processed independently

### Exit Criteria

- [ ] `_compute_cum_qty()` correctly computes cumulative position
- [ ] `_split_jump_rows()` splits position reversals correctly
- [ ] `_assign_position_groups()` groups round-trips correctly
- [ ] `_fifo_match_group()` matches FIFO and splits trades
- [ ] **exit_idx preserved** for all matched rows
- [ ] **entry_side** and **trade_type** columns correctly tag Entry vs Exit
- [ ] Unclosed positions have `holding_period=inf`, `exit_idx=None`
- [ ] Multi-symbol data handled correctly
- [ ] All tests pass

---

## Phase 4: Forward Returns (v0.6.0)

**Status:** TODO

- [ ] Add `forward_return()` to `vizflow/ops.py`
  - Input: `df`, `horizons`, `price_col`, `time_col`, `symbol_col`
  - Output: df with `return_{h}` columns
  - Handle edge case: no future price → null

- [ ] Create `vizflow/calendar.py`
  - `load(path) -> pl.DataFrame`
  - `generate(dates) -> pl.DataFrame` with prev/next columns

- [ ] Update `__init__.py` exports
- [ ] Create `tests/test_forward_return.py`
- [ ] Create `tests/test_calendar.py`
- [ ] Publish v0.6.0

---

## Phase 5: Execution (v0.7.0)

**Status:** TODO

- [ ] Create `vizflow/context.py`
  - Context dataclass: config, calendar, market, date
  - `col(semantic)` shortcut method

- [ ] Add `run()` to `vizflow/run.py`
  - Single date processing
  - Load → Pipeline → Save

- [ ] Add `run_batch()` to `vizflow/run.py`
  - Multiple dates, parallel processing
  - `skip_existing` option

- [ ] Add `run_cluster()` to `vizflow/run.py`
  - Generate ailab job commands

- [ ] Update `__init__.py` exports
- [ ] Create `tests/test_run.py`
- [ ] Publish v0.7.0

---

## Phase 6: Visualization (v0.8.0)

**Status:** FUTURE (optional)

- [ ] Create `vizflow/viz.py`
  - `heatmap(df, x, y, z)` → Plotly figure
  - `line(df, x, y, group)` → Plotly figure
  - `dashboard(panels)` → Dash app

- [ ] Add optional dependencies: `dash`, `plotly`
- [ ] Create tests
- [ ] Publish v0.8.0

---

# Part 4: Release Process

## Versioning

### Pre-1.0 (Current)

**Format:** `0.MINOR.PATCH`

- **0.MINOR.0** - New features (new modules, new public APIs)
- **0.MINOR.PATCH** - Bug fixes, refactors, internal improvements

**Breaking changes:** Allowed in any 0.MINOR release (document in changelog)

### Post-1.0 (Future)

**Format:** `MAJOR.MINOR.PATCH`

- **MAJOR** - Breaking changes
- **MINOR** - New features (backward compatible)
- **PATCH** - Bug fixes

## Release Checklist

### Feature Release (0.MINOR.0)

- [ ] All tests pass (`pytest tests/`)
- [ ] Update `__version__` in `__init__.py`
- [ ] Update `version` in `pyproject.toml`
- [ ] Update CHANGELOG.md
- [ ] Build: `python -m build`
- [ ] Test locally: `pip install dist/*.whl`
- [ ] **ASK USER**: "Ready to publish v0.X.0 to PyPI?"
- [ ] Upload: `twine upload dist/*.whl` (wheel ONLY, NOT .tar.gz!)
- [ ] Git tag: `git tag v0.X.0 && git push origin v0.X.0`
- [ ] Update demo.ipynb if needed

### Patch Release (0.MINOR.PATCH)

Same as above, but:
- [ ] Verify no new features
- [ ] Verify no breaking changes

---

## Package Structure

```
vizflow/
├── __init__.py      # Public API exports
├── py.typed         # PEP 561 marker
├── config.py        # Config, set_config, get_config
├── market.py        # Market, Session, CN
├── ops.py           # parse_time, bin, aggregate, forward_return
├── enrichment.py    # State, TagRule, Enricher, FIFOMatch
├── calendar.py      # Calendar utilities
├── context.py       # Context for pipeline runs
├── run.py           # run, run_batch, run_cluster
└── viz.py           # Visualization (future)

tests/
├── test_import.py
├── test_config.py
├── test_market.py
├── test_ops.py
├── test_enrichment.py
├── test_fifo.py
├── test_forward_return.py
├── test_calendar.py
└── test_run.py
```

---

## Version 1.0.0 Criteria

### Functional Requirements

- [ ] Config, Market, parse_time, bin, aggregate
- [ ] Enrichment + FIFO
- [ ] forward_return + calendar
- [ ] Execution (run, run_batch, run_cluster)
- [ ] Visualization (optional, can be 1.1.0)

### Quality Requirements

- [ ] Test coverage >90% on core modules
- [ ] API reference complete
- [ ] User guide with examples
- [ ] TB-scale validated on ailab

### API Stability

- [ ] No breaking changes planned for 6 months
- [ ] Deprecation policy defined
