"""Core operations for data transformation."""

from __future__ import annotations

import polars as pl

from .config import get_config


def parse_time(
    df: pl.LazyFrame,
    timestamp_col: str = "ticktime",
) -> pl.LazyFrame:
    """Parse HHMMSSMMM timestamp to time-of-day and elapsed milliseconds.

    Adds two columns:
    - tod_{timestamp_col}: pl.Time (time-of-day HH:MM:SS.mmm) - good for plotting
    - elapsed_{timestamp_col}: pl.Int64 (milliseconds since market open)

    Args:
        df: Input LazyFrame
        timestamp_col: Column with integer HHMMSSMMM format timestamps
            e.g., 93012145 = 09:30:12.145, 142058425 = 14:20:58.425

    Returns:
        LazyFrame with tod and elapsed columns added

    Raises:
        RuntimeError: If config not set via set_config()
        NotImplementedError: If market is not CN

    Example:
        >>> config = vf.Config(market="CN", input_dir=".", output_dir=".")
        >>> vf.set_config(config)
        >>> df = vf.parse_time(df, "ticktime")
        >>> # Creates: tod_ticktime (pl.Time), elapsed_ticktime (pl.Int64)
    """
    config = get_config()

    if config.market != "CN":
        raise NotImplementedError(f"Market {config.market} not supported yet")

    # Parse HHMMSSMMM to components
    df = df.with_columns([
        (pl.col(timestamp_col) // 10000000).alias("_hour"),
        (pl.col(timestamp_col) // 100000 % 100).alias("_minute"),
        (pl.col(timestamp_col) // 1000 % 100).alias("_second"),
        (pl.col(timestamp_col) % 1000).alias("_ms"),
    ])

    # Add time-of-day column (pl.Time)
    # Convert to nanoseconds since midnight
    tod_ns = (
        pl.col("_hour") * 3_600_000_000_000
        + pl.col("_minute") * 60_000_000_000
        + pl.col("_second") * 1_000_000_000
        + pl.col("_ms") * 1_000_000
    )
    df = df.with_columns(tod_ns.cast(pl.Time).alias(f"tod_{timestamp_col}"))

    # Add elapsed milliseconds (int)
    # CN market: 09:30-11:30 (morning), 13:00-15:00 (afternoon)
    # Using user's hardcoded logic
    elapsed_ms = (
        pl.when(pl.col("_hour") < 12)
        .then(
            # Morning session: from 09:30:00.000
            (
                (pl.col("_hour") - 9) * 3600
                + (pl.col("_minute") - 30) * 60
                + pl.col("_second")
            )
            * 1000
            + pl.col("_ms")
        )
        .otherwise(
            # Afternoon session: 2 hours of morning + time since 13:00
            (
                2 * 3600 + (pl.col("_hour") - 13) * 3600 + pl.col("_minute") * 60 + pl.col("_second")
            )
            * 1000
            + pl.col("_ms")
        )
    )
    df = df.with_columns(elapsed_ms.cast(pl.Int64).alias(f"elapsed_{timestamp_col}"))

    # Drop temporary columns
    df = df.drop(["_hour", "_minute", "_second", "_ms"])

    return df


def bin(df: pl.LazyFrame, widths: dict[str, float]) -> pl.LazyFrame:
    """Add bin columns for specified columns.

    Args:
        df: Input LazyFrame
        widths: Column name to bin width mapping

    Returns:
        LazyFrame with {col}_bin columns added

    Formula:
        bin_value = round(raw_value / binwidth)
        actual_value = bin_value * binwidth  # To recover
    """
    exprs = [
        (pl.col(col) / width).round().cast(pl.Int64).alias(f"{col}_bin")
        for col, width in widths.items()
    ]
    return df.with_columns(exprs)


def aggregate(
    df: pl.LazyFrame,
    group_by: list[str],
    metrics: dict[str, pl.Expr],
) -> pl.LazyFrame:
    """Aggregate data with custom metrics.

    Args:
        df: Input LazyFrame
        group_by: Columns to group by
        metrics: Name to Polars expression mapping

    Returns:
        Aggregated LazyFrame

    Example:
        metrics = {
            "count": pl.len(),
            "total_qty": pl.col("quantity").sum(),
            "vwap": pl.col("notional").sum() / pl.col("quantity").sum(),
        }
    """
    agg_exprs = [expr.alias(name) for name, expr in metrics.items()]
    return df.group_by(group_by).agg(agg_exprs)


def _horizon_to_suffix(horizon_seconds: int) -> str:
    """Convert horizon in seconds to column name suffix.

    Rule: ≤60s → use seconds (60s), >60s → use minutes (3m, 30m)
    """
    if horizon_seconds <= 60:
        return f"{horizon_seconds}s"
    else:
        minutes = horizon_seconds // 60
        return f"{minutes}m"


def forward_return(
    df_trade: pl.LazyFrame,
    df_alpha: pl.LazyFrame,
    horizons: list[int],
    trade_time_col: str = "elapsed_alpha_ts",
    alpha_time_col: str = "elapsed_ticktime",
    price_col: str = "mid",
    symbol_col: str = "ukey",
    tolerance_ms: int = 5000,
) -> pl.LazyFrame:
    """Merge alpha's future price to trade and calculate forward returns.

    For each trade row:
    1. Look up alpha price at trade_time + horizon
    2. Add forward_{price_col}_{horizon} column (the future price)
    3. Calculate y_{horizon} = (forward_price - current_price) / current_price

    Output column names follow the convention:
    - ≤60s → forward_mid_60s, y_60s
    - >60s → forward_mid_3m, y_3m

    Args:
        df_trade: Trade LazyFrame with trade_time_col and price_col
        df_alpha: Alpha LazyFrame with alpha_time_col and price_col
        horizons: List of horizon in seconds, e.g., [60, 180, 1800]
        trade_time_col: Time column in trade df (default: "elapsed_alpha_ts")
        alpha_time_col: Time column in alpha df (default: "elapsed_ticktime")
        price_col: Column name for price in both dfs (default: "mid")
        symbol_col: Symbol column for grouping (default: "ukey")
        tolerance_ms: Max time difference in ms for asof join (default: 5000)

    Returns:
        Trade LazyFrame with forward_* and y_* columns added

    Example:
        >>> df_trade = vf.parse_time(vf.scan_trade(date), "alpha_ts")
        >>> df_alpha = vf.parse_time(vf.scan_alpha(date), "ticktime")
        >>> df = vf.forward_return(df_trade, df_alpha, horizons=[60, 180, 1800])
        >>> # Creates: forward_mid_60s, forward_mid_3m, forward_mid_30m
        >>> #          y_60s, y_3m, y_30m
    """
    # Collect for asof join
    trade = df_trade.collect()
    alpha = df_alpha.collect()

    # Prepare alpha lookup table: (symbol, time) -> price
    alpha_lookup = alpha.select([
        pl.col(symbol_col),
        pl.col(alpha_time_col),
        pl.col(price_col),
    ]).sort([symbol_col, alpha_time_col])

    for horizon in horizons:
        suffix = _horizon_to_suffix(horizon)
        horizon_ms = horizon * 1000
        forward_col = f"forward_{price_col}_{suffix}"
        return_col = f"y_{suffix}"

        # Add target time column for this horizon
        trade = trade.with_columns(
            (pl.col(trade_time_col) + horizon_ms).alias("_forward_time")
        )

        # Sort by join columns (required for asof join)
        trade = trade.sort([symbol_col, "_forward_time"])

        # Asof join: find alpha price at forward_time
        joined = trade.join_asof(
            alpha_lookup.rename({alpha_time_col: "_alpha_time", price_col: "_forward_price"}),
            left_on="_forward_time",
            right_on="_alpha_time",
            by=symbol_col,
            strategy="nearest",
            tolerance=tolerance_ms,
        )

        # Add forward price and calculate return (guard against zero price)
        trade = joined.with_columns([
            pl.col("_forward_price").alias(forward_col),
            pl.when(pl.col(price_col) != 0)
            .then((pl.col("_forward_price") - pl.col(price_col)) / pl.col(price_col))
            .otherwise(pl.lit(None))
            .alias(return_col),
        ]).drop(["_forward_time", "_alpha_time", "_forward_price"])

    return trade.lazy()


def mark_to_close(
    df_trade: pl.LazyFrame,
    df_univ: pl.LazyFrame,
    mid_col: str = "mid",
    close_col: str = "close",
    symbol_col: str = "ukey",
) -> pl.LazyFrame:
    """Add mark-to-close return column.

    Joins trade with universe data to get close price, then calculates:
    y_close = (close - mid) / mid

    Args:
        df_trade: Trade LazyFrame with mid_col and symbol_col
        df_univ: Universe LazyFrame with close_col and symbol_col
        mid_col: Column name for mid price in trade df (default: "mid")
        close_col: Column name for close price in univ df (default: "close")
        symbol_col: Symbol column for joining (default: "ukey")

    Returns:
        Trade LazyFrame with y_close column added

    Example:
        >>> df_trade = vf.scan_trade(date)
        >>> df_univ = vf.scan_univ(date)
        >>> df = vf.mark_to_close(df_trade, df_univ)
        >>> # Creates: y_close
    """
    # Select only needed columns from univ to avoid column conflicts
    univ_cols = [symbol_col, close_col]
    # Check if data_date exists in both for multi-day joining
    trade_schema = df_trade.collect_schema()
    univ_schema = df_univ.collect_schema()

    if "data_date" in trade_schema.names() and "data_date" in univ_schema.names():
        # Multi-day case: join on symbol and date
        join_cols = [symbol_col, "data_date"]
        univ_cols.append("data_date")
    else:
        # Single-day case: join on symbol only
        join_cols = [symbol_col]

    # Join with univ to get close price
    df = df_trade.join(
        df_univ.select(univ_cols),
        on=join_cols,
        how="left",
    )

    # Calculate return (guard against zero mid)
    df = df.with_columns(
        pl.when(pl.col(mid_col) != 0)
        .then((pl.col(close_col) - pl.col(mid_col)) / pl.col(mid_col))
        .otherwise(pl.lit(None))
        .alias("y_close")
    )

    return df


def sign_by_side(
    df: pl.LazyFrame,
    cols: list[str],
    side_col: str = "order_side",
) -> pl.LazyFrame:
    """Sign return columns by order side.

    For Buy trades: keep sign as-is (price going up = positive = good)
    For Sell trades: negate sign (price going down = positive = good)

    This makes all returns have consistent interpretation:
    positive = favorable price move for that order side

    Args:
        df: LazyFrame with return columns
        cols: List of column names to sign (e.g., ["y_10m", "y_30m", "y_close"])
        side_col: Column containing order side (default: "order_side")
            Expected values: "Buy" or "Sell"

    Returns:
        LazyFrame with signed return columns

    Example:
        >>> df = vf.sign_by_side(df, cols=["y_10m", "y_30m", "y_close"])
        >>> # All y_* columns now have positive = favorable for that side
    """
    signed_exprs = []
    for col in cols:
        signed = (
            pl.when(pl.col(side_col) == "Sell")
            .then(-pl.col(col))
            .otherwise(pl.col(col))
            .alias(col)
        )
        signed_exprs.append(signed)

    return df.with_columns(signed_exprs)
