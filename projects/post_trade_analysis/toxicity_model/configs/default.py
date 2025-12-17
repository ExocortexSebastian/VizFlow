"""Default configuration for toxicity model project.

Update paths to match your real environment.
"""

from pathlib import Path

import vizflow as vf

# Data paths - UPDATE THESE for your environment
ALPHA_DIR = Path("/data/jyao/alpha")
TRADE_DIR = Path("/data/ylin/trade")

config = vf.Config(
    # Alpha data
    alpha_dir=ALPHA_DIR,
    alpha_pattern="alpha_{date}.feather",
    alpha_preset="jyao_v20251114",
    # Trade data
    trade_dir=TRADE_DIR,
    trade_pattern="{date}.meords",
    trade_preset="ylin_v20251204",
    # Market
    market="CN",
)