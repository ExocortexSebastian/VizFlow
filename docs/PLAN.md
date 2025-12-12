# VizFlow Implementation Plan

> Phased implementation with testable, PyPI-publishable milestones

---

## Version Roadmap

| Phase | Version | Status | Key Features |
|-------|---------|--------|--------------|
| 0 | 0.1.0 | [ ] | Project scaffolding, installable |
| 1 | 0.2.0 | [ ] | Config, Market (CN), I/O |
| 2 | 0.3.0 | [ ] | parse_time, bin, aggregate |
| 3 | 0.4.0 | [ ] | forward_return, calendar |
| 4 | 0.5.0 | [ ] | run, run_batch, run_local, run_cluster |
| 5 | 0.6.0 | [ ] | Enricher, TagCondition, TagRunning |
| 6 | 0.7.0 | [ ] | FIFOMatch (trade splitting) |
| 7 | 0.8.0 | [ ] | Visualization (future) |

---

## Phase 0: Project Scaffolding

**Goal**: Installable package skeleton on PyPI

### Steps

- [ ] **0.1** Create directory structure
  ```
  vizflow/
  ├── __init__.py
  ├── py.typed
  pyproject.toml
  README.md
  tests/
  └── __init__.py
  ```

- [ ] **0.2** Write `pyproject.toml`
  - Project metadata (name, version, description)
  - Dependencies: `polars>=0.20.0`
  - Dev dependencies: `pytest>=7.0`, `ruff`
  - Build system: setuptools or hatchling

- [ ] **0.3** Write `vizflow/__init__.py`
  ```python
  __version__ = "0.1.0"
  ```

- [ ] **0.4** Write `README.md`
  - Project description
  - Installation instructions
  - Basic usage example

- [ ] **0.5** Write `tests/test_import.py`
  ```python
  def test_import():
      import vizflow as vf
      assert vf.__version__ == "0.1.0"
  ```

- [ ] **0.6** Run tests locally: `pytest tests/`

- [ ] **0.7** Build package: `python -m build`

- [ ] **0.8** Upload to PyPI: `twine upload dist/*`

- [ ] **0.9** Verify: `pip install vizflow && python -c "import vizflow"`

### Exit Criteria
- `pip install vizflow` works
- `import vizflow as vf` works
- `vf.__version__` returns "0.1.0"

---

## Phase 1: Config + Market + I/O

**Goal**: Load data, compute elapsed_seconds, save results

### Steps

- [ ] **1.1** Create `vizflow/config.py`
  - `Config` dataclass with fields:
    - `input_dir: Path`
    - `output_dir: Path`
    - `input_pattern: str = "{date}.feather"`
    - `market: str = "CN"`
    - `columns: dict[str, str]` (semantic → actual mapping)
  - `col(semantic)` method for column name lookup
  - `get_file_path(date)` method

- [ ] **1.2** Create `vizflow/market.py`
  - `Session` dataclass: `start: str`, `end: str`
  - `Market` dataclass: `name: str`, `sessions: list[Session]`
  - `elapsed_seconds(time: datetime) -> int` method
  - `CN` preset: sessions 09:30-11:30, 13:00-15:00
  - `CRYPTO` preset: 24/7

- [ ] **1.3** Create `vizflow/io.py`
  - `load(path) -> pl.LazyFrame` - load feather/parquet
  - `save(df, path)` - save to parquet
  - `scan(pattern) -> pl.LazyFrame` - lazy scan glob pattern

- [ ] **1.4** Update `vizflow/__init__.py`
  ```python
  from .config import Config
  from .market import Market, Session, CN, CRYPTO
  from .io import load, save, scan
  ```

- [ ] **1.5** Create `tests/test_config.py`
  - Test column mapping
  - Test file path generation

- [ ] **1.6** Create `tests/test_market.py`
  - Test CN elapsed_seconds at key times (09:30, 11:30, 13:00, 15:00)
  - Test CRYPTO (24h)

- [ ] **1.7** Create `tests/test_io.py`
  - Test load/save roundtrip with tmp_path
  - Test scan glob pattern

- [ ] **1.8** Run all tests: `pytest tests/`

- [ ] **1.9** Update version to 0.2.0, publish to PyPI

### Exit Criteria
- `Config(columns={"price": "mid"}).col("price")` returns `"mid"`
- `CN.elapsed_seconds(datetime(2024,1,1,9,30,0))` returns `0`
- `CN.elapsed_seconds(datetime(2024,1,1,13,0,0))` returns `7200`
- Load/save roundtrip preserves data
- All tests pass

---

## Phase 2: Core Operations

**Goal**: Run simple aggregation pipeline

### Steps

- [ ] **2.1** Create `vizflow/ops.py` with `parse_time()`
  - Input: `df: LazyFrame`, `market: Market`, `timestamp_col: str`
  - Output: df with `elapsed_seconds` column added
  - Use `pl.Expr` to compute from timestamp

- [ ] **2.2** Add `bin()` to `vizflow/ops.py`
  - Input: `df: LazyFrame`, `widths: dict[str, float]`
  - Output: df with `{col}_bin` columns added
  - Formula: `round(value / width)` as integer

- [ ] **2.3** Add `aggregate()` to `vizflow/ops.py`
  - Input: `df: LazyFrame`, `group_by: list[str]`, `metrics: dict[str, pl.Expr]`
  - Output: aggregated LazyFrame
  - Apply `.group_by().agg()` with named expressions

- [ ] **2.4** Update `vizflow/__init__.py`
  ```python
  from .ops import parse_time, bin, aggregate
  ```

- [ ] **2.5** Create `tests/test_ops.py`
  - Test parse_time adds correct elapsed_seconds
  - Test bin creates correct bin values
  - Test aggregate computes correct metrics

- [ ] **2.6** Run all tests: `pytest tests/`

- [ ] **2.7** Update version to 0.3.0, publish to PyPI

### Exit Criteria
- `parse_time(df, CN, "ticktime")` adds `elapsed_seconds` column
- `bin(df, {"alpha": 1e-4})` adds `alpha_bin` column
- `aggregate(df, ["group"], {"count": pl.len()})` groups correctly
- All tests pass

---

## Phase 3: Forward Returns + Calendar

**Goal**: Compute forward returns, manage trading calendar

### Steps

- [ ] **3.1** Add `forward_return()` to `vizflow/ops.py`
  - Input: `df`, `horizons: list[int]`, `price_col`, `time_col`, `symbol_col`
  - Output: df with `return_{h}` columns for each horizon
  - Logic: For each row, find future price at `time + horizon`, compute `(future - current) / current`
  - Handle edge case: no future price → null

- [ ] **3.2** Create `vizflow/calendar.py`
  - `load(path) -> pl.DataFrame` - load calendar CSV/parquet
  - `generate(dates: list[str]) -> pl.DataFrame` - create calendar with prev/next
  - `range(calendar, start, end) -> list[str]` - get trading days in range

- [ ] **3.3** Update `vizflow/__init__.py`
  ```python
  from .ops import forward_return
  from . import calendar
  ```

- [ ] **3.4** Create `tests/test_forward_return.py`
  - Test forward return calculation
  - Test null when no future price
  - Test multiple horizons

- [ ] **3.5** Create `tests/test_calendar.py`
  - Test load/generate
  - Test range filtering

- [ ] **3.6** Run all tests: `pytest tests/`

- [ ] **3.7** Update version to 0.4.0, publish to PyPI

### Exit Criteria
- `forward_return(df, [60], "mid", "elapsed_seconds", "symbol")` computes returns
- `calendar.range(cal, "20240101", "20240105")` returns trading days
- All tests pass

---

## Phase 4: Execution

**Goal**: Production-ready pipeline execution

### Steps

- [ ] **4.1** Create `vizflow/context.py`
  - `Context` dataclass: `config`, `calendar`, `market`, `date`
  - `col(semantic)` shortcut method

- [ ] **4.2** Create `vizflow/run.py` with `run()`
  - Input: `pipeline_fn`, `config`, `date`, `save=True`
  - Logic:
    1. Load input file for date
    2. Create Context
    3. Call pipeline_fn(df, ctx)
    4. Save result if save=True
  - Return: collected DataFrame

- [ ] **4.3** Add `run_batch()` to `vizflow/run.py`
  - Input: `pipeline_fn`, `config`, `dates`, `parallel=True`, `skip_existing=True`
  - Logic:
    - If parallel: use multiprocessing Pool
    - If skip_existing: check output file exists
  - Return: None (saves to files)

- [ ] **4.4** Add `run_local()` to `vizflow/run.py`
  - Same as run_batch but always sequential
  - For debugging/testing without cluster

- [ ] **4.5** Add `run_cluster()` to `vizflow/run.py`
  - Input: `pipeline_fn`, `config`, `dates`
  - Output: list of ailab job commands
  - Format: `ailab create job --name=vf_{date} ...`

- [ ] **4.6** Update `vizflow/__init__.py`
  ```python
  from .context import Context
  from .run import run, run_batch, run_local, run_cluster
  ```

- [ ] **4.7** Create `tests/test_run.py`
  - Test run() single date with tmp_path
  - Test run_batch() multiple dates
  - Test skip_existing behavior
  - Test run_local()

- [ ] **4.8** Run all tests: `pytest tests/`

- [ ] **4.9** Update version to 0.5.0, publish to PyPI

### Exit Criteria
- `run(pipeline, config, "20241001")` processes single date
- `run_batch(pipeline, config, dates, parallel=True)` processes in parallel
- `run_local(pipeline, config, dates)` processes sequentially
- `skip_existing` works correctly
- All tests pass

---

## Phase 5: Enrichment Framework

**Goal**: Add tags to data in single pass (without FIFO)

### Steps

- [ ] **5.1** Create `vizflow/enrichment.py` with base classes
  - `State` class with `reset(symbol)` method
  - `TagRule` class with `output_columns` property and `process(row, state)` method

- [ ] **5.2** Add `TagCondition` rule
  - Input: `name: str`, `condition: Callable[[dict], bool]`
  - Output: single boolean column
  - process(): return `{name: condition(row)}`

- [ ] **5.3** Add `TagRunning` rule
  - Input: `name: str`, `update_fn: Callable`, `initial: Any`
  - Output: single column with running value
  - process(): update state, return `{name: new_value}`

- [ ] **5.4** Add `Enricher` class
  - Input: `rules`, `by`, `sort_by`, `state_class`
  - `run(df)` method:
    1. Collect df
    2. Group by `by` column
    3. Sort each group by `sort_by`
    4. For each group: reset state, process rows, collect outputs
    5. Return df with new columns

- [ ] **5.5** Update `vizflow/__init__.py`
  ```python
  from .enrichment import State, TagRule, Enricher, TagCondition, TagRunning
  ```

- [ ] **5.6** Create `tests/test_enrichment.py`
  - Test TagCondition adds boolean column
  - Test TagRunning accumulates values
  - Test state resets per symbol
  - Test multiple rules in one pass

- [ ] **5.7** Run all tests: `pytest tests/`

- [ ] **5.8** Update version to 0.6.0, publish to PyPI

### Exit Criteria
- `TagCondition("is_large", lambda r: r["qty"] > 10000)` works
- `TagRunning("seq", lambda p, r: p + 1, 0)` increments per row
- State resets when symbol changes
- All tests pass

---

## Phase 6: FIFO Matching

**Goal**: Trade matching with splitting

### Steps

- [ ] **6.1** Add `FIFOMatch` rule to `vizflow/enrichment.py`
  - Input: `side_col`, `qty_col`, `time_col`, `price_col`, `entry_side`, `exit_side`
  - Output columns: `matched_entry_idx`, `matched_qty`, `holding_period`, `is_closed`
  - Row-expanding: returns list of dicts when one exit matches multiple entries

- [ ] **6.2** Update `Enricher.run()` to handle row-expanding rules
  - Detect if rule returns list vs dict
  - If list: expand into multiple output rows
  - Preserve original row columns when expanding

- [ ] **6.3** Create `tests/test_fifo.py`
  - Test simple match (buy 100, sell 100)
  - Test partial match (buy 100, sell 60, sell 40)
  - Test trade splitting (buy 50, buy 50, sell 80 → 2 rows)
  - Test unclosed trades
  - Test columns preserved when splitting

- [ ] **6.4** Run all tests: `pytest tests/`

- [ ] **6.5** Update version to 0.7.0, publish to PyPI

### Exit Criteria
- Simple FIFO match works
- Trade splitting produces multiple rows
- Original columns preserved
- Unclosed trades tagged correctly
- All tests pass

---

## Phase 7: Visualization (Future)

**Goal**: Interactive Dash dashboards

### Steps

- [ ] **7.1** Create `vizflow/viz.py`
  - `heatmap(df, x, y, z)` → Plotly figure
  - `line(df, x, y, group)` → Plotly figure
  - `dashboard(panels)` → Dash app

- [ ] **7.2** Add optional dependency: `dash`, `plotly`

- [ ] **7.3** Create tests

- [ ] **7.4** Update version to 0.8.0, publish to PyPI

*Defer to later - focus on data processing first.*

---

## Quick Reference: File Structure

```
vizflow/
├── __init__.py      # Public API exports
├── py.typed         # PEP 561 marker
├── config.py        # Config dataclass
├── context.py       # Context dataclass
├── market.py        # Market, Session, CN, CRYPTO
├── calendar.py      # Calendar utilities
├── io.py            # load, save, scan
├── ops.py           # parse_time, bin, aggregate, forward_return
├── enrichment.py    # State, TagRule, Enricher, TagCondition, TagRunning, FIFOMatch
├── run.py           # run, run_batch, run_local, run_cluster
└── viz.py           # (future) visualization

tests/
├── __init__.py
├── test_import.py
├── test_config.py
├── test_market.py
├── test_io.py
├── test_ops.py
├── test_forward_return.py
├── test_calendar.py
├── test_run.py
├── test_enrichment.py
└── test_fifo.py
```
