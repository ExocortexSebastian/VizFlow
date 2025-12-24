"""
VizFlow - TB-scale data analysis and visualization library.

Usage:
    import vizflow as vf
"""

__version__ = "0.5.5"

from .config import Config, get_config, set_config
from .io import (
    load_calendar,
    scan_alpha,
    scan_alphas,
    scan_trade,
    scan_trades,
    scan_univ,
    scan_univs,
)
from .market import CN, CRYPTO, Market, Session
from .ops import aggregate, bin, forward_return, mark_to_close, parse_time, sign_by_side
from .schema_evolution import (
    JYAO_V20251114,
    SCHEMAS,
    YLIN_V20251204,
    ColumnSpec,
    SchemaEvolution,
    get_schema,
)
