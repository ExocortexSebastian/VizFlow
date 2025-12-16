"""I/O functions for VizFlow with automatic schema evolution."""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl

from .config import Config, get_config

if TYPE_CHECKING:
    pass


def load_alpha(date: str, config: Config | None = None) -> pl.LazyFrame:
    """Load alpha data for a date with automatic schema evolution.

    Args:
        date: Date string, e.g. "20241001"
        config: Config to use, or get_config() if None

    Returns:
        LazyFrame with schema evolution applied

    Example:
        >>> config = vf.Config(
        ...     output_dir=Path("/data/output"),
        ...     alpha_dir=Path("/data/alpha"),
        ...     alpha_schema={"qty": vf.ColumnSchema(cast_to=pl.Int64)}
        ... )
        >>> vf.set_config(config)
        >>> alpha = vf.load_alpha("20241001")
    """
    config = config or get_config()
    path = config.get_alpha_path(date)
    df = pl.scan_ipc(path)

    # Apply schema evolution (type casting)
    for col_name, schema in config.alpha_schema.items():
        df = df.with_columns(pl.col(col_name).cast(schema.cast_to))

    return df


def load_trade(date: str, config: Config | None = None) -> pl.LazyFrame:
    """Load trade data for a date with automatic schema evolution.

    Args:
        date: Date string, e.g. "20241001"
        config: Config to use, or get_config() if None

    Returns:
        LazyFrame with schema evolution applied

    Example:
        >>> config = vf.Config(
        ...     output_dir=Path("/data/output"),
        ...     trade_dir=Path("/data/trade"),
        ...     trade_schema={"qty": vf.ColumnSchema(cast_to=pl.Int64)}
        ... )
        >>> vf.set_config(config)
        >>> trade = vf.load_trade("20241001")  # qty: 1.00000002 → 1
    """
    config = config or get_config()
    path = config.get_trade_path(date)
    df = pl.scan_ipc(path)

    # Apply schema evolution (type casting)
    for col_name, schema in config.trade_schema.items():
        df = df.with_columns(pl.col(col_name).cast(schema.cast_to))

    return df


def load_calendar(config: Config | None = None) -> pl.DataFrame:
    """Load trading calendar.

    Args:
        config: Config to use, or get_config() if None

    Returns:
        DataFrame with date, prev_date, next_date columns

    Raises:
        ValueError: If calendar_path is not set in config

    Example:
        >>> config = vf.Config(
        ...     output_dir=Path("/data/output"),
        ...     calendar_path=Path("/data/calendar.parquet")
        ... )
        >>> vf.set_config(config)
        >>> calendar = vf.load_calendar()
    """
    config = config or get_config()
    if config.calendar_path is None:
        raise ValueError("calendar_path is not set in Config")
    return pl.read_parquet(config.calendar_path)


def _scan_file(path) -> pl.LazyFrame:
    """Scan a file based on its extension.

    Args:
        path: Path to file

    Returns:
        LazyFrame from the file

    Supported formats:
        - .feather, .ipc, .arrow: IPC format (pl.scan_ipc)
        - .csv, .meords: CSV format (pl.scan_csv)
        - .parquet: Parquet format (pl.scan_parquet)
    """
    suffix = str(path).lower().split(".")[-1]

    if suffix in ("feather", "ipc", "arrow"):
        return pl.scan_ipc(path)
    elif suffix in ("csv", "meords"):
        return pl.scan_csv(path)
    elif suffix == "parquet":
        return pl.scan_parquet(path)
    else:
        # Default to IPC
        return pl.scan_ipc(path)


def scan_trade(date: str, config: Config | None = None) -> pl.LazyFrame:
    """Scan single date trade file with column mapping.

    Supports both IPC/feather format and CSV format (including .meords files).

    Args:
        date: Date string, e.g. "20241001"
        config: Config to use, or get_config() if None

    Returns:
        LazyFrame with column mapping and schema evolution applied

    Example:
        >>> config = vf.Config(
        ...     trade_dir=Path("/data/yuanzhao/"),
        ...     trade_pattern="{date}.meords",
        ...     column_preset="ylin",
        ... )
        >>> vf.set_config(config)
        >>> df = vf.scan_trade("20241001")
    """
    config = config or get_config()
    path = config.get_trade_path(date)
    df = _scan_file(path)
    return _apply_mapping(df, config)


def scan_trades(config: Config | None = None) -> pl.LazyFrame:
    """Scan all trade files with column mapping.

    Args:
        config: Config to use, or get_config() if None

    Returns:
        LazyFrame with column mapping and schema evolution applied

    Raises:
        ValueError: If trade_dir is not set or no files found

    Example:
        >>> config = vf.Config(
        ...     trade_dir=Path("/data/yuanzhao/"),
        ...     trade_pattern="{date}.feather",
        ...     column_preset="ylin",
        ... )
        >>> vf.set_config(config)
        >>> df = vf.scan_trades()
    """
    config = config or get_config()
    if config.trade_dir is None:
        raise ValueError("trade_dir is not set in Config")

    pattern = config.trade_pattern.replace("{date}", "*")
    files = sorted(config.trade_dir.glob(pattern))
    if not files:
        raise ValueError(f"No files found matching {pattern} in {config.trade_dir}")

    # Concatenate all files using lazy scanning
    dfs = [_scan_file(f) for f in files]
    df = pl.concat(dfs)
    return _apply_mapping(df, config)


def _apply_mapping(df: pl.LazyFrame, config: Config) -> pl.LazyFrame:
    """Apply column rename + schema evolution.

    Args:
        df: Input LazyFrame
        config: Config with mapping settings

    Returns:
        LazyFrame with mapping applied
    """
    # Drop record type prefix column if present (from CSV files)
    existing = set(df.collect_schema().names())
    if "#HFTORD" in existing:
        df = df.drop("#HFTORD")
        existing.remove("#HFTORD")

    # Get rename map from preset or custom
    rename_map = _get_rename_map(config)

    if rename_map:
        existing = set(df.collect_schema().names())
        to_rename = {k: v for k, v in rename_map.items() if k in existing}
        if to_rename:
            df = df.rename(to_rename)

    # Schema evolution (type casting) - use renamed column names
    for col_name, schema in config.trade_schema.items():
        df = df.with_columns(pl.col(col_name).cast(schema.cast_to))

    return df


def _get_rename_map(config: Config) -> dict[str, str]:
    """Get rename map from preset name or custom dict.

    Args:
        config: Config with column_preset or column_rename

    Returns:
        Dict mapping old column names to new names
    """
    if config.column_rename:
        return config.column_rename
    if config.column_preset:
        from .presets import YLIN

        presets = {"ylin": YLIN}
        return presets.get(config.column_preset.lower(), {})
    return {}
