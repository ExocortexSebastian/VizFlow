# VizFlow Feedback Log

Feature requests and pain points discovered during research projects.

---

## Template

### [YYYY-MM-DD] Feature Title

**Context**: Which project/notebook triggered this
**Problem**: What VizFlow cannot do
**Expected API**:
```python
# Desired usage
result = vf.new_function(df, param=value)
```
**Generality**: High / Medium / Low
**Status**: Open | In Progress | Implemented | Verified

---

## Open Items

### [2025-12-17] Quantile-based binning for analysis

**Context**: toxicity_model/notebooks/03_toxicity_analysis.ipynb
**Problem**: `vf.bin()` bins by fixed width, but for research analysis we often need quantile-based binning (quintiles, deciles) to ensure equal sample sizes per bin.
**Expected API**:
```python
# Bin by quantiles (equal count per bin)
df = vf.qbin(df, {"spread_norm": 5})  # 5 quantile bins

# Or extend existing bin() with mode parameter
df = vf.bin(df, {"spread_norm": 5}, mode="quantile")
```
**Generality**: High - common pattern in any feature analysis
**Status**: Open

---

### [2025-12-17] Analysis groupby utilities

**Context**: toxicity_model/notebooks/03_toxicity_analysis.ipynb
**Problem**: Repeatedly writing the same groupby-aggregate pattern to analyze metrics by features
**Expected API**:
```python
# Analyze ex post metric by ex ante feature
result = vf.analyze(df, by="spread_norm_bin", metrics=["y_60s", "y_3m"])
# Returns: DataFrame with n, mean, std per group
```
**Generality**: Medium - useful but may be too opinionated
**Status**: Open

---

---

## Implemented (Pending Review)

(Move here after implementation, delete after code-reviewer verification)

### [2024-12-24] Univ data source

**Context**: markout_analysis project needs close prices
**Implemented**: `vf.scan_univ(date)`, `vf.scan_univs()`, config fields `univ_dir`, `univ_pattern`, `univ_schema`
**Files**: `vizflow/config.py`, `vizflow/io.py`, `vizflow/__init__.py`
**Status**: Implemented

---

### [2024-12-24] Date column in multi-file loading (data_date)

**Context**: markout_analysis needs to group by date for time-series analysis
**Implemented**: `scan_trades()` now adds `data_date` column extracted from filename
**Files**: `vizflow/io.py`
**Status**: Implemented

---

### [2024-12-24] Mark-to-close return

**Context**: markout_analysis needs return from mid to official close price
**Implemented**: `vf.mark_to_close(df_trade, df_univ)` - joins and calculates `y_close`
**Files**: `vizflow/ops.py`, `vizflow/__init__.py`
**Status**: Implemented

---

### [2024-12-24] Sign return by order side

**Context**: markout_analysis needs positive = favorable for order side
**Implemented**: `vf.sign_by_side(df, cols=[...])` - negates for Sell side
**Files**: `vizflow/ops.py`, `vizflow/__init__.py`
**Status**: Implemented