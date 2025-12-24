# %% [markdown]
# # Mark-out Analysis
#
# Two plots:
# 1. **Return Profile**: Forward return curve across horizons (0m, 10m, 30m, 60m, close)
# 2. **Time-Series**: Cumulative mark-out over dates

# %% Config
import polars as pl
import vizflow as vf
import matplotlib.pyplot as plt
from pathlib import Path

vf.set_config(vf.Config(
    alpha_dir=Path("/Users/yichenlu/VizFlow/data/jyao/alpha"),
    alpha_pattern="alpha_{date}.feather",
    alpha_schema="jyao_v20251114",
    trade_dir=Path("/Users/yichenlu/VizFlow/data/ylin/trade"),
    trade_pattern="{date}.meords",
    trade_schema="ylin_v20251204",
    univ_dir=Path("/Users/yichenlu/VizFlow/data/jyao/univ"),
    univ_pattern="{date}.csv",
    market="CN",
))

# Note: Data files use dates like "20240827", "22220202"
# If running locally with limited data, adjust patterns accordingly

# %% Discover Matching Dates
# Get available dates from each source
trade_dates = set(
    vf.scan_trades()
    .select("data_date")
    .unique()
    .collect()
    .to_series()
    .to_list()
)
alpha_dates = set(
    vf.scan_alphas()
    .select("data_date")
    .unique()
    .collect()
    .to_series()
    .to_list()
)
univ_dates = set(
    vf.scan_univs()
    .select("data_date")
    .unique()
    .collect()
    .to_series()
    .to_list()
)

# Intersection of all three
matching_dates = sorted(trade_dates & alpha_dates & univ_dates)
print(f"Trade dates: {sorted(trade_dates)}")
print(f"Alpha dates: {sorted(alpha_dates)}")
print(f"Univ dates: {sorted(univ_dates)}")
print(f"Matching dates: {matching_dates}")

if not matching_dates:
    raise ValueError("No matching dates found across trade, alpha, and univ files!")

# %% Load Data (Matching Dates Only)
df_trade = vf.scan_trades().filter(pl.col("data_date").is_in(matching_dates))
df_alpha = vf.scan_alphas().filter(pl.col("data_date").is_in(matching_dates))
df_univ = vf.scan_univs().filter(pl.col("data_date").is_in(matching_dates))

print(f"Trade columns: {df_trade.collect_schema().names()[:10]}...")
print(f"Alpha columns: {df_alpha.collect_schema().names()[:10]}...")
print(f"Univ columns: {df_univ.collect_schema().names()[:10]}...")

# %% Process
# Parse time and add mid price
df = (
    vf.parse_time(df_trade, timestamp_col="alpha_ts")
    .with_columns(((pl.col("bid_px0") + pl.col("ask_px0")) / 2).alias("mid"))
)
df_alpha = vf.parse_time(df_alpha, timestamp_col="ticktime").with_columns(
    ((pl.col("bid_px0") + pl.col("ask_px0")) / 2).alias("mid")
)

# Forward returns (10m, 30m, 60m)
df = vf.forward_return(df, df_alpha, horizons=[600, 1800, 3600])

# Mark-to-close
df = vf.mark_to_close(df, df_univ)

# Sign by side (positive = favorable)
df = vf.sign_by_side(df, cols=["y_10m", "y_30m", "y_60m", "y_close"])

# Add notional for weighting
df = df.with_columns(
    (pl.col("order_filled_qty") * pl.col("fill_price")).alias("notional")
).collect()

print(f"Processed trades: {len(df):,}")
print(f"Columns: {df.columns[:15]}...")

# %% Plot 1: Return Profile
# Notional-weighted aggregation across all trades
horizons = ["0m", "10m", "30m", "60m", "close"]
y_cols = [None, "y_10m", "y_30m", "y_60m", "y_close"]

stats = []
for h, col in zip(horizons, y_cols):
    if col is None:  # 0m baseline
        stats.append({"horizon": h, "mean": 0.0, "std": 0.0})
    else:
        valid = df.filter(pl.col(col).is_not_null())
        n = valid["notional"].sum()
        if n > 0:
            weighted_mean = (valid[col] * valid["notional"]).sum() / n
            weighted_var = ((valid[col] - weighted_mean).pow(2) * valid["notional"]).sum() / n
            stats.append({"horizon": h, "mean": weighted_mean * 10000, "std": (weighted_var ** 0.5) * 10000})
        else:
            stats.append({"horizon": h, "mean": 0.0, "std": 0.0})

df_stats = pl.DataFrame(stats)
print(df_stats)

fig, ax = plt.subplots(figsize=(10, 6))
x = range(len(horizons))
means = df_stats["mean"].to_list()
stds = df_stats["std"].to_list()
ax.plot(x, means, 'b-o', linewidth=2, markersize=8)
ax.fill_between(x, [m-s for m, s in zip(means, stds)], [m+s for m, s in zip(means, stds)], alpha=0.3)
ax.set_xticks(x)
ax.set_xticklabels(horizons)
ax.set_xlabel("Horizon")
ax.set_ylabel("Mark-out Return (bps)")
ax.set_title("Return Profile (Notional-Weighted)")
ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("return_profile.png", dpi=150)
plt.show()

# %% Plot 2: Cumulative Mark-out Time Series
# Aggregate by data_date, then cumsum
df_daily = df.group_by("data_date").agg([
    # Notional-weighted mean for each horizon
    ((pl.col("y_10m") * pl.col("notional")).sum() / pl.col("notional").sum()).alias("markout_10m"),
    ((pl.col("y_30m") * pl.col("notional")).sum() / pl.col("notional").sum()).alias("markout_30m"),
    ((pl.col("y_60m") * pl.col("notional")).sum() / pl.col("notional").sum()).alias("markout_60m"),
    ((pl.col("y_close") * pl.col("notional")).sum() / pl.col("notional").sum()).alias("markout_close"),
]).sort("data_date")

print(df_daily)

fig, ax = plt.subplots(figsize=(12, 6))
dates = df_daily["data_date"].to_list()

for col, label in [("markout_10m", "10m"), ("markout_30m", "30m"),
                   ("markout_60m", "60m"), ("markout_close", "close")]:
    cumsum = df_daily[col].cum_sum() * 10000  # to bps
    ax.plot(dates, cumsum.to_list(), '-o', label=label, markersize=4)

ax.set_xlabel("Date")
ax.set_ylabel("Cumulative Mark-out (bps)")
ax.set_title("Cumulative Mark-out Over Time")
ax.legend()
ax.grid(True, alpha=0.3)
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig("cumulative_markout.png", dpi=150)
plt.show()

# %%
