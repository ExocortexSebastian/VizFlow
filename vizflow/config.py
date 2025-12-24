"""Configuration classes for VizFlow."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .schema_evolution import SchemaEvolution

# Global config instance
_global_config: Config | None = None


def _validate_date(date: str) -> None:
    """Validate date string format to prevent path traversal.

    Args:
        date: Date string to validate

    Raises:
        ValueError: If date is not exactly 8 digits (YYYYMMDD format)
    """
    if not (len(date) == 8 and date.isdigit()):
        raise ValueError(
            f"Invalid date format: {date!r}. Expected YYYYMMDD (8 digits)."
        )


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
        trade_schema: Schema evolution for trade data (name or SchemaEvolution)
        alpha_schema: Schema evolution for alpha data (name or SchemaEvolution)
        binwidths: Mapping from column names to bin widths
        group_by: Columns to group by in aggregation
        horizons: List of forward return horizons in seconds
        time_cutoff: Optional time cutoff (e.g. 143000000 for 14:30:00)

    Example:
        >>> config = vf.Config(
        ...     trade_dir=Path("data/ylin/trade"),
        ...     trade_pattern="{date}.meords",
        ...     trade_schema="ylin_v20251204",  # Use registered schema by name
        ...     market="CN",
        ... )
    """

    # === Input Paths ===
    alpha_dir: Path | None = None
    alpha_pattern: str = "alpha_{date}.feather"
    trade_dir: Path | None = None
    trade_pattern: str = "trade_{date}.feather"
    univ_dir: Path | None = None
    univ_pattern: str = "{date}.csv"
    calendar_path: Path | None = None

    # === Output Paths ===
    replay_dir: Path | None = None      # FIFO output (materialization 1)
    aggregate_dir: Path | None = None   # Aggregation output (materialization 2)

    # === Market ===
    market: str = "CN"

    # === Schema Evolution ===
    # Can be a string (schema name) or SchemaEvolution instance
    trade_schema: str | SchemaEvolution | None = None
    alpha_schema: str | SchemaEvolution | None = None
    univ_schema: str | SchemaEvolution | None = None

    # === Aggregation ===
    binwidths: dict[str, float] = field(default_factory=dict)
    group_by: list[str] = field(default_factory=list)

    # === Analysis ===
    horizons: list[int] = field(default_factory=list)
    time_cutoff: int | None = None

    def __post_init__(self):
        """Convert string paths to Path objects.

        Note: String values for path fields (alpha_dir, trade_dir, univ_dir,
        calendar_path, replay_dir, aggregate_dir) are automatically converted
        to Path objects.
        """
        if isinstance(self.alpha_dir, str):
            self.alpha_dir = Path(self.alpha_dir)
        if isinstance(self.trade_dir, str):
            self.trade_dir = Path(self.trade_dir)
        if isinstance(self.univ_dir, str):
            self.univ_dir = Path(self.univ_dir)
        if isinstance(self.calendar_path, str):
            self.calendar_path = Path(self.calendar_path)
        if isinstance(self.replay_dir, str):
            self.replay_dir = Path(self.replay_dir)
        if isinstance(self.aggregate_dir, str):
            self.aggregate_dir = Path(self.aggregate_dir)

    def get_alpha_path(self, date: str) -> Path:
        """Get alpha file path for a date.

        Args:
            date: Date string, e.g. "20241001"

        Returns:
            Full path to alpha file

        Raises:
            ValueError: If alpha_dir is not set or date format is invalid
        """
        _validate_date(date)
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
            ValueError: If trade_dir is not set or date format is invalid
        """
        _validate_date(date)
        if self.trade_dir is None:
            raise ValueError("trade_dir is not set in Config")
        return self.trade_dir / self.trade_pattern.format(date=date)

    def get_univ_path(self, date: str) -> Path:
        """Get universe file path for a date.

        Args:
            date: Date string, e.g. "20241001"

        Returns:
            Full path to univ file

        Raises:
            ValueError: If univ_dir is not set or date format is invalid
        """
        _validate_date(date)
        if self.univ_dir is None:
            raise ValueError("univ_dir is not set in Config")
        return self.univ_dir / self.univ_pattern.format(date=date)

    def get_replay_path(self, date: str, suffix: str = ".parquet") -> Path:
        """Get replay output file path for a date (FIFO results).

        Args:
            date: Date string, e.g. "20241001"
            suffix: File suffix, default ".parquet"

        Returns:
            Full path to replay output file

        Raises:
            ValueError: If replay_dir is not set or date format is invalid
        """
        _validate_date(date)
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
            ValueError: If aggregate_dir is not set or date format is invalid
        """
        _validate_date(date)
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
