# VizFlow Design Document

> TB-scale data analysis and visualization library
> `import vizflow as vf`

---

## Table of Contents

1. [Purpose](#1-purpose)
2. [Pipeline Architecture](#2-pipeline-architecture)
3. [Data Sources](#3-data-sources)
4. [Key Concepts](#4-key-concepts)
5. [Design Decisions](#5-design-decisions)

---

## 1. Purpose

VizFlow is a **Polars extension** (not replacement) for:
- **TB-scale time-series data processing**
- **Multi-dimensional aggregation** with interactive exploration
- **Composable, functional pipeline** design

**Primary use case:** Financial market data analysis (alpha evaluation, post-trade analysis)

**What VizFlow does:**
- Hard problems (FIFO matching with trade splitting)
- Complicated logic (elapsed_seconds with market sessions)
- Heavy coding tasks (batch processing, skip_existing)

**What VizFlow does NOT do:**
- Wrap simple Polars operations (user can do `pl.scan_parquet()`)
- Add unnecessary abstraction layers
- Hide Polars from the user

---

## 2. Pipeline Architecture

### 2.1 Dataflow Diagram

Enrichment can branch to visualization at any point:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PIPELINE (per-date processing)                                             │
│                                                                             │
│   ┌─────────────────────────────────┐                                       │
│   │           CONFIG                │  vf.Config(market, columns, ...)      │
│   └─────────────────────────────────┘                                       │
│                   ↓                                                         │
│           ┌─────────────┐                      ┌─────────────────────┐      │
│           │  enrichment │ ──────────────────→  │     VISUALIZE       │      │
│           │ parse_time  │     [Lazy]           │  (alpha signals)    │      │
│           └─────────────┘                      └─────────────────────┘      │
│                   ↓                                                         │
│   ┌─────────────────────────────────┐                                       │
│   │       REPLAY (FIFO)             │  Stateful matching, trade splitting   │
│   │                                 │  MATERIALIZATION 1 [Eager]            │
│   └─────────────────────────────────┘                                       │
│                   ↓                                                         │
│           ┌─────────────┐                      ┌─────────────────────┐      │
│           │  enrichment │ ──────────────────→  │     VISUALIZE       │      │
│           │ fwd_return  │     [Lazy]           │  (trade-level)      │      │
│           └─────────────┘                      └─────────────────────┘      │
│                   ↓                                                         │
│   ┌─────────────────────────────────┐                                       │
│   │         AGGREGATE               │  bin() + aggregate()                  │
│   │                                 │  MATERIALIZATION 2 [Eager]            │
│   └─────────────────────────────────┘  → partials/{date}.parquet            │
│                   ↓                                                         │
│           ┌─────────────┐                      ┌─────────────────────┐      │
│           │  enrichment │ ──────────────────→  │     VISUALIZE       │      │
│           │   reduce    │                      │  (aggregated)       │      │
│           └─────────────┘                      └─────────────────────┘      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Stage Details

| Stage | Name | Purpose | Execution |
|-------|------|---------|-----------|
| 0 | CONFIG | Set up market, columns, paths | - |
| 1 | Minimal Enrich | Add elapsed_seconds for FIFO | Lazy |
| 2 | REPLAY | FIFO matching, trade splitting | **Eager** (Materialization 1) |
| 3 | Full Enrich | Add forward_return, overnight | Lazy |
| 4 | AGGREGATE | bin() + aggregate() | **Eager** (Materialization 2) |

**Critical ordering:** Minimal Enrich → REPLAY → Full Enrich → AGGREGATE

**Execution model:** Map (cluster, per-date) → Reduce (single machine) → Visualize (Dash)

### 2.3 Key Characteristics

- **Date-partitioned**: One file per trading day (~5GB), perfect parallelism
- **Lazy by default**: Only 2 materialization points (FIFO + Aggregation)
- **Functional composition**: `df.pipe(op1).pipe(op2).pipe(op3)`

---

## 3. Data Sources

### 3.1 Input (3 types)

| Datasource | File Pattern | Key Columns |
|------------|--------------|-------------|
| Alpha | `alpha_{date}.feather` | ticktime, ukey, alpha1, alpha2, AskPrice1, BidPrice1 |
| Trade | `trade_{date}.feather` | fillTs, ukey, fillPrice, orderSide, qty |
| Calendar | `calendar.parquet` | date, prev_date, next_date |

### 3.2 Output

| Stage | Output | Key Columns |
|-------|--------|-------------|
| After FIFO | (in memory) | matched_entry_id, matched_qty, holding_period, is_closed |
| After Aggregation | `partials/{date}.parquet` | group_by columns + metrics |

### 3.3 Partitioning Strategy

**Primary Partition: By Date** - One file per trading day

| Benefit | Description |
|---------|-------------|
| **Parallelizable** | 300 dates = 300 independent jobs |
| **No shuffle** | No cross-date data movement |
| **Clear failure boundary** | If date X fails, others succeed |
| **Incremental** | Add new dates without reprocessing old ones |

**Partition sizing:** ~5GB per date (one trading day)

---

## 4. Key Concepts

### 4.1 Lazy vs Eager

| Type | Description | When |
|------|-------------|------|
| **Lazy** | Build query plan, no execution | Enrichment (parse_time, forward_return) |
| **Eager** | Execute immediately, materialize | FIFO (stateful), Aggregation (save to disk) |

Only 2 materialization points in the entire pipeline.

### 4.2 Enrichment System

**Purpose:** Add columns to DataFrame in a single pass

| Concept | Description |
|---------|-------------|
| **State** | Per-symbol state that resets when symbol changes |
| **TagRule** | Base class for enrichment rules |
| **Enricher** | Orchestrator that applies rules in order |

**Rule types:**
- **Column-adding**: Add new columns (e.g., TagCondition, TagRunning)
- **Row-expanding**: One input row → multiple output rows (e.g., FIFOMatch)

### 4.3 FIFO Matching

**Problem:** Match exit trades to entry trades using FIFO ordering

**Trade splitting:** One exit may close multiple entries → one exit row becomes multiple rows

**Example:**
```
Buy 100 at t=0 (entry #1)
Buy 50 at t=1 (entry #2)
Sell 120 at t=2 → splits into:
  - 100 matched to entry #1 (fully closed)
  - 20 matched to entry #2 (partially closed)
```

### 4.4 Column Mapping

**Problem:** Column names vary across data sources and time

**Solution:** Semantic names in code, per-datasource mappings in config

```
Alpha: "timestamp" → "ticktime", "price" → "mid"
Trade: "timestamp" → "fillTs", "price" → "fillPrice"
```

### 4.5 Schema Evolution

**Problem:** Data quality issues like float precision errors (1.00000002 should be 1)

**Solution:** ColumnSchema with type casting applied on load

```
trade_schema={"qty": ColumnSchema(cast_to=pl.Int64)}
# When loading: qty 1.00000002 → 1
```

### 4.6 Column Naming Conventions

**Predictor vs Target:**
- `x_*` = alpha / predictions
- `y_*` = forward returns / targets

**Time suffix rule:**
- ≤60s → use seconds: `x_10s`, `x_60s`
- >60s → use minutes: `x_3m`, `x_30m`

**Standard column names:**

| Category | Standard Name | Description |
|----------|---------------|-------------|
| Symbol | `ukey` | Unique key for instrument |
| Quote | `bid_px0`, `ask_px0` | Best bid/ask price |
| Quote | `bid_size0`, `ask_size0` | Best bid/ask size |
| Time | `timestamp`, `ticktime` | Event timestamp |
| Predictor | `x_10s`, `x_60s` | Alpha predictions (≤60s) |
| Predictor | `x_3m`, `x_30m` | Alpha predictions (>60s) |
| Target | `y_60s`, `y_3m` | Forward returns |

### 4.7 Market Sessions

**Problem:** Wall-clock time ≠ trading time (lunch breaks, overnight gaps)

**Solution:** Convert to elapsed_seconds (continuous trading time)

```
CN Market:
  09:30:00 → 0 seconds
  11:29:59 → 7199 seconds
  (lunch break)
  13:00:00 → 7200 seconds
  15:00:00 → 14400 seconds
```

---

## 5. Design Decisions

### 5.1 API Style: Functional

Pure functions, easy to test and compose. No framework lock-in.

### 5.2 Metrics: User-Defined Polars Expressions

Pass raw `pl.Expr` instead of pre-built Metric classes. Full Polars expressiveness.

### 5.3 Enrichment: Pluggable Rules

Single pass through data (efficient). User controls what state to maintain.

### 5.4 Split Enrichment (Before/After Replay)

- **Before Replay:** Only `elapsed_seconds` (FIFO needs this for sorting)
- **After Replay:** `forward_return`, `overnight_return` (don't affect FIFO)

Rationale: Keeps replay input minimal, more flexible composition.

### 5.5 Calendar as DataFrame

Can be joined with data using Polars. Enables overnight return calculation.

---

**See [PLAN.md](PLAN.md) for implementation details and API specifications.**
