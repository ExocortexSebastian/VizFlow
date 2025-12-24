"""I/O functions for VizFlow with automatic schema evolution."""

from __future__ import annotations

import re
from pathlib import Path

import polars as pl

from .config import Config, get_config
from .schema_evolution import SchemaEvolution, get_schema


def _extract_date_from_path(path: Path, pattern: str) -> str | None:
    """Extract date from filename using pattern.

    Args:
        path: File path.
        pattern: Pattern with {date} placeholder, e.g., "{date}.meords"

    Returns:
        Extracted date string, or None if no match or no {date} in pattern.

    Example:
        >>> _extract_date_from_path(Path("data/11110101.meords"), "{date}.meords")
        "11110101"
    """
    # If pattern has no {date} placeholder, return None
    if "{date}" not in pattern:
        return None

    # Convert pattern to regex: "{date}" -> "(?P<date>.+)"
    # Escape other special chars first
    regex_pattern = re.escape(pattern).replace(r"\{date\}", r"(?P<date>[^/]+)")
    match = re.search(regex_pattern, path.name)
    if match:
        return match.group("date")
    return None


def _resolve_schema(
    schema_ref: str | SchemaEvolution | None,
) -> SchemaEvolution | None:
    """Resolve schema reference to SchemaEvolution instance.

    Args:
        schema_ref: Schema name string, SchemaEvolution instance, or None.

    Returns:
        SchemaEvolution instance or None.
    """
    if schema_ref is None:
        return None
    if isinstance(schema_ref, SchemaEvolution):
        return schema_ref
    return get_schema(schema_ref)


def _scan_file(
    path,
    schema: SchemaEvolution | None = None,
) -> pl.LazyFrame:
    """Scan a file based on its extension with optional schema.

    Args:
        path: Path to file.
        schema: Optional SchemaEvolution for CSV parsing options.

    Returns:
        LazyFrame from the file.

    Supported formats:
        - .feather, .ipc, .arrow: IPC format (pl.scan_ipc)
        - .csv, .meords: CSV format (pl.scan_csv)
        - .parquet: Parquet format (pl.scan_parquet)
    """
    suffix = str(path).lower().split(".")[-1]

    if suffix in ("feather", "ipc", "arrow"):
        return pl.scan_ipc(path)
    elif suffix in ("csv", "meords"):
        csv_kwargs = {}
        if schema:
            schema_overrides = schema.get_schema_overrides()
            if schema_overrides:
                csv_kwargs["schema_overrides"] = schema_overrides
            null_values = schema.get_null_values()
            if null_values:
                csv_kwargs["null_values"] = null_values
        return pl.scan_csv(path, **csv_kwargs)
    elif suffix == "parquet":
        return pl.scan_parquet(path)
    else:
        raise ValueError(
            f"Unsupported file format: .{suffix}. "
            "Supported: .feather, .ipc, .arrow, .csv, .meords, .parquet"
        )


def _apply_schema_evolution(
    df: pl.LazyFrame,
    schema: SchemaEvolution,
) -> pl.LazyFrame:
    """Apply full schema evolution: drop, rename, cast.

    Args:
        df: LazyFrame to transform.
        schema: SchemaEvolution with transformation rules.

    Returns:
        Transformed LazyFrame.
    """
    existing = set(df.collect_schema().names())

    # Step 1: Drop excluded columns
    drop_cols = schema.get_drop_columns()
    to_drop = [c for c in drop_cols if c in existing]
    if to_drop:
        df = df.drop(to_drop)
        existing -= set(to_drop)

    # Step 2: Rename columns
    rename_map = schema.get_rename_map()
    to_rename = {k: v for k, v in rename_map.items() if k in existing}
    if to_rename:
        df = df.rename(to_rename)
        # Update existing names after rename
        for old, new in to_rename.items():
            existing.discard(old)
            existing.add(new)

    # Step 3: Cast columns (using FINAL names after rename)
    cast_map = schema.get_cast_map()
    for col_name, dtype in cast_map.items():
        if col_name in existing:
            df = df.with_columns(pl.col(col_name).cast(dtype))

    return df


def scan_trade(date: str, config: Config | None = None) -> pl.LazyFrame:
    """Scan single date trade file with schema evolution.

    Supports IPC/feather, CSV (including .meords), and Parquet formats.

    Args:
        date: Date string, e.g. "20241001"
        config: Config to use, or get_config() if None

    Returns:
        LazyFrame with schema evolution applied

    Example:
        >>> config = vf.Config(
        ...     trade_dir=Path("/data/ylin/trade"),
        ...     trade_pattern="{date}.meords",
        ...     trade_schema="ylin_v20251204",
        ... )
        >>> vf.set_config(config)
        >>> df = vf.scan_trade("20241001")
    """
    config = config or get_config()
    path = config.get_trade_path(date)
    schema = _resolve_schema(config.trade_schema)

    df = _scan_file(path, schema=schema)
    if schema:
        df = _apply_schema_evolution(df, schema)

    return df


def scan_trades(config: Config | None = None) -> pl.LazyFrame:
    """Scan all trade files with schema evolution and data_date column.

    Extracts date from each filename using the pattern and adds a "data_date" column.

    Args:
        config: Config to use, or get_config() if None

    Returns:
        LazyFrame with schema evolution applied and data_date column added

    Raises:
        ValueError: If trade_dir is not set or no files found

    Example:
        >>> config = vf.Config(
        ...     trade_dir=Path("/data/ylin/trade"),
        ...     trade_pattern="{date}.meords",
        ...     trade_schema="ylin_v20251204",
        ... )
        >>> vf.set_config(config)
        >>> df = vf.scan_trades()  # Has "data_date" column
    """
    config = config or get_config()
    if config.trade_dir is None:
        raise ValueError("trade_dir is not set in Config")

    pattern = config.trade_pattern.replace("{date}", "*")
    files = sorted(config.trade_dir.glob(pattern))
    if not files:
        raise ValueError(f"No files found matching {pattern} in {config.trade_dir}")

    schema = _resolve_schema(config.trade_schema)

    # Scan each file, apply schema evolution, and add data_date column
    # Schema evolution must be applied per-file BEFORE concat to ensure matching schemas
    dfs = []
    for f in files:
        df = _scan_file(f, schema=schema)
        if schema:
            df = _apply_schema_evolution(df, schema)
        date = _extract_date_from_path(f, config.trade_pattern)
        if date:
            df = df.with_columns(pl.lit(date).alias("data_date"))
        dfs.append(df)

    return pl.concat(dfs)


def scan_alpha(date: str, config: Config | None = None) -> pl.LazyFrame:
    """Scan single date alpha file with schema evolution.

    Args:
        date: Date string, e.g. "20241001"
        config: Config to use, or get_config() if None

    Returns:
        LazyFrame with schema evolution applied

    Example:
        >>> config = vf.Config(
        ...     alpha_dir=Path("/data/jyao/alpha"),
        ...     alpha_pattern="alpha_{date}.feather",
        ...     alpha_schema="jyao_v20251114",
        ... )
        >>> vf.set_config(config)
        >>> df = vf.scan_alpha("20251114")
    """
    config = config or get_config()
    path = config.get_alpha_path(date)
    schema = _resolve_schema(config.alpha_schema)

    df = _scan_file(path, schema=schema)
    if schema:
        df = _apply_schema_evolution(df, schema)

    return df


def scan_alphas(config: Config | None = None) -> pl.LazyFrame:
    """Scan all alpha files with schema evolution.

    Args:
        config: Config to use, or get_config() if None

    Returns:
        LazyFrame with schema evolution applied

    Raises:
        ValueError: If alpha_dir is not set or no files found
    """
    config = config or get_config()
    if config.alpha_dir is None:
        raise ValueError("alpha_dir is not set in Config")

    pattern = config.alpha_pattern.replace("{date}", "*")
    files = sorted(config.alpha_dir.glob(pattern))
    if not files:
        raise ValueError(f"No files found matching {pattern} in {config.alpha_dir}")

    schema = _resolve_schema(config.alpha_schema)

    # Apply schema evolution per-file BEFORE concat to ensure matching schemas
    # Note: Alpha files already have data_date column, no need to add it
    dfs = []
    for f in files:
        df = _scan_file(f, schema=schema)
        if schema:
            df = _apply_schema_evolution(df, schema)
        dfs.append(df)

    return pl.concat(dfs)


def scan_univ(date: str, config: Config | None = None) -> pl.LazyFrame:
    """Scan single date universe file with schema evolution.

    Args:
        date: Date string, e.g. "20241001"
        config: Config to use, or get_config() if None

    Returns:
        LazyFrame with schema evolution applied

    Example:
        >>> config = vf.Config(
        ...     univ_dir=Path("/data/jyao/univ"),
        ...     univ_pattern="{date}.csv",
        ... )
        >>> vf.set_config(config)
        >>> df = vf.scan_univ("20241001")
    """
    config = config or get_config()
    path = config.get_univ_path(date)
    schema = _resolve_schema(config.univ_schema)

    df = _scan_file(path, schema=schema)
    if schema:
        df = _apply_schema_evolution(df, schema)

    return df


def scan_univs(config: Config | None = None) -> pl.LazyFrame:
    """Scan all universe files with schema evolution and data_date column.

    Extracts date from each filename using the pattern and adds a "data_date" column.

    Args:
        config: Config to use, or get_config() if None

    Returns:
        LazyFrame with schema evolution applied and data_date column added

    Raises:
        ValueError: If univ_dir is not set or no files found
    """
    config = config or get_config()
    if config.univ_dir is None:
        raise ValueError("univ_dir is not set in Config")

    pattern = config.univ_pattern.replace("{date}", "*")
    files = sorted(config.univ_dir.glob(pattern))
    if not files:
        raise ValueError(f"No files found matching {pattern} in {config.univ_dir}")

    schema = _resolve_schema(config.univ_schema)

    # Scan each file, apply schema evolution, and add data_date column
    # Schema evolution must be applied per-file BEFORE concat to ensure matching schemas
    dfs = []
    for f in files:
        df = _scan_file(f, schema=schema)
        if schema:
            df = _apply_schema_evolution(df, schema)
        date = _extract_date_from_path(f, config.univ_pattern)
        if date:
            df = df.with_columns(pl.lit(date).alias("data_date"))
        dfs.append(df)

    return pl.concat(dfs)


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
        ...     calendar_path=Path("/data/calendar.parquet")
        ... )
        >>> vf.set_config(config)
        >>> calendar = vf.load_calendar()
    """
    config = config or get_config()
    if config.calendar_path is None:
        raise ValueError("calendar_path is not set in Config")
    return pl.read_parquet(config.calendar_path)
