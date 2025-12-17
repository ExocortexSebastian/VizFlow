"""
VizFlow - TB-scale data analysis and visualization library.

Usage:
    import vizflow as vf
"""

__version__ = "0.4.3"

from .config import ColumnSchema, Config, get_config, set_config
from .io import (
    load_alpha,
    load_calendar,
    load_trade,
    scan_alpha,
    scan_alphas,
    scan_trade,
    scan_trades,
)
from .market import CN, CRYPTO, Market, Session
from .ops import aggregate, bin, parse_time
from .presets import JYAO_V20251114, PRESETS, YLIN_V20251204
