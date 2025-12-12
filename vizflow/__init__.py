"""
VizFlow - TB-scale data analysis and visualization library.

Usage:
    import vizflow as vf
"""

__version__ = "0.4.0"

from .config import Config, get_config, set_config
from .market import CN, CRYPTO, Market, Session
from .ops import aggregate, bin, parse_time
