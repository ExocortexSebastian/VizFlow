"""Configuration classes for VizFlow."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Global config instance
_global_config: Config | None = None


@dataclass
class ColumnSchema:
    """Schema for a column with type casting.

    Attributes:
        cast_to: Target type after casting (e.g. pl.Int64)

    Example:
        # Handle float precision errors: 1.00000002 → 1
        ColumnSchema(cast_to=pl.Int64)
    """

    cast_to: Any  # pl.DataType, but avoid import for now


@dataclass
class Config:
    """Central configuration for a pipeline run.

    Attributes:
        alpha_dir: Directory containing alpha files
        alpha_pattern: Pattern for alpha files, e.g. "alpha_{date}.feather"
        trade_dir: Directory containing trade files
        trade_pattern: Pattern for trade files, e.g. "trade_{date}.feather"
        calendar_path: Path to calendar parquet file
        replay_dir: Directory for FIFO replay output (materialization 1)
        aggregate_dir: Directory for aggregation output (materialization 2)
        market: Market identifier, e.g. "CN"
        alpha_columns: Mapping from semantic names to alpha column names
        trade_columns: Mapping from semantic names to trade column names
        alpha_schema: Schema evolution for alpha columns
        trade_schema: Schema evolution for trade columns
        binwidths: Mapping from column names to bin widths
        group_by: Columns to group by in aggregation
        horizons: List of forward return horizons in seconds
        time_cutoff: Optional time cutoff (e.g. 143000000 for 14:30:00)
    """

    # === Input Paths ===
    alpha_dir: Path | None = None
    alpha_pattern: str = "alpha_{date}.feather"
    trade_dir: Path | None = None
    trade_pattern: str = "trade_{date}.feather"
    calendar_path: Path | None = None

    # === Output Paths ===
    replay_dir: Path | None = None      # FIFO output (materialization 1)
    aggregate_dir: Path | None = None   # Aggregation output (materialization 2)

    # === Market ===
    market: str = "CN"

    # === Column Mapping ===
    alpha_columns: dict[str, str] = field(default_factory=dict)
    trade_columns: dict[str, str] = field(default_factory=dict)

    # === Schema Evolution ===
    alpha_schema: dict[str, ColumnSchema] = field(default_factory=dict)
    trade_schema: dict[str, ColumnSchema] = field(default_factory=dict)

    # === Column Mapping ===
    column_preset: str | None = None  # "ylin" or None
    column_rename: dict[str, str] = field(default_factory=dict)  # Custom rename map

    # === Aggregation ===
    binwidths: dict[str, float] = field(default_factory=dict)
    group_by: list[str] = field(default_factory=list)

    # === Analysis ===
    horizons: list[int] = field(default_factory=list)
    time_cutoff: int | None = None

    def __post_init__(self):
        """Convert paths to Path objects if needed."""
        if isinstance(self.alpha_dir, str):
            self.alpha_dir = Path(self.alpha_dir)
        if isinstance(self.trade_dir, str):
            self.trade_dir = Path(self.trade_dir)
        if isinstance(self.calendar_path, str):
            self.calendar_path = Path(self.calendar_path)
        if isinstance(self.replay_dir, str):
            self.replay_dir = Path(self.replay_dir)
        if isinstance(self.aggregate_dir, str):
            self.aggregate_dir = Path(self.aggregate_dir)

    def col(self, semantic: str, source: str = "trade") -> str:
        """Get actual column name from semantic name.

        Args:
            semantic: Semantic column name (e.g. "timestamp", "price")
            source: "alpha" or "trade"

        Returns:
            Actual column name, or the semantic name if no mapping exists
        """
        if source == "alpha":
            return self.alpha_columns.get(semantic, semantic)
        return self.trade_columns.get(semantic, semantic)

    def get_alpha_path(self, date: str) -> Path:
        """Get alpha file path for a date.

        Args:
            date: Date string, e.g. "20241001"

        Returns:
            Full path to alpha file

        Raises:
            ValueError: If alpha_dir is not set
        """
        if self.alpha_dir is None:
            raise ValueError("alpha_dir is not set in Config")
        return self.alpha_dir / self.alpha_pattern.format(date=date)

    def get_trade_path(self, date: str) -> Path:
        """Get trade file path for a date.

        Args:
            date: Date string, e.g. "20241001"

        Returns:
            Full path to trade file

        Raises:
            ValueError: If trade_dir is not set
        """
        if self.trade_dir is None:
            raise ValueError("trade_dir is not set in Config")
        return self.trade_dir / self.trade_pattern.format(date=date)

    def get_replay_path(self, date: str, suffix: str = ".parquet") -> Path:
        """Get replay output file path for a date (FIFO results).

        Args:
            date: Date string, e.g. "20241001"
            suffix: File suffix, default ".parquet"

        Returns:
            Full path to replay output file

        Raises:
            ValueError: If replay_dir is not set
        """
        if self.replay_dir is None:
            raise ValueError("replay_dir is not set in Config")
        return self.replay_dir / f"{date}{suffix}"

    def get_aggregate_path(self, date: str, suffix: str = ".parquet") -> Path:
        """Get aggregate output file path for a date (partial results).

        Args:
            date: Date string, e.g. "20241001"
            suffix: File suffix, default ".parquet"

        Returns:
            Full path to aggregate output file

        Raises:
            ValueError: If aggregate_dir is not set
        """
        if self.aggregate_dir is None:
            raise ValueError("aggregate_dir is not set in Config")
        return self.aggregate_dir / f"{date}{suffix}"


def set_config(config: Config) -> None:
    """Set the global config.

    Args:
        config: Config instance to set as global
    """
    global _global_config
    _global_config = config


def get_config() -> Config:
    """Get the global config.

    Returns:
        The global Config instance

    Raises:
        RuntimeError: If config has not been set via set_config()
    """
    if _global_config is None:
        raise RuntimeError(
            "Config not set. Call vf.set_config(config) first."
        )
    return _global_config
