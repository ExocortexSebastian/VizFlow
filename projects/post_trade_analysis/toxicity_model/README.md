# Toxicity Model

Post-trade analysis project for identifying trade conditions where alpha predictions are unreliable.

## Overview

Toxicity model handles outliers that predictive models cannot learn:

| Condition | Description | Signal |
|-----------|-------------|--------|
| **Adverse Selection** | Opponent's L1 size too large | Track subsequent price movement |
| **Information Leakage** | Opponent's L1 size too small | Track subsequent price movement |
| **Large Spread** | Abnormal bid-ask spread | Model uncertainty |
| **Touch Anomaly** | Unusual touch size patterns | Market microstructure noise |

## Workflow

1. Tag trades with conditions (spread > X, touch_size < Y, etc.)
2. Calculate forward returns (y_60s, y_3m, etc.)
3. Analyze: Do tagged trades have worse model performance?
4. Build toxicity flags to filter unreliable predictions

## Project Structure

```
toxicity_model/
├── README.md           # This file
├── FEEDBACK.md         # Pain points → VizFlow improvements
├── configs/
│   └── default.py      # vf.Config with data paths
└── notebooks/
    ├── 01_data_explore.ipynb      # Understand data structure
    ├── 02_forward_return.ipynb    # Test y_* calculation
    └── 03_toxicity_analysis.ipynb # Main research
```

## Usage

```python
# In your real environment:
# 1. pip install vizflow
# 2. Copy notebooks to your environment
# 3. Update configs/default.py with real data paths
# 4. Run notebooks

from configs.default import config
import vizflow as vf

vf.set_config(config)
df = vf.scan_alpha("20251114")
```

## Design Principle

**Generalize to VizFlow**: Any reusable pattern discovered here should be implemented in VizFlow, not as ad-hoc functions.

Example:
- Need: Tag trades where spread > X
- Generalize: Conditional tagging operation
- VizFlow: `vf.tag_condition(df, "large_spread", pl.col("spread") > 0.01)`