"""Configuration classes for VizFlow."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Global config instance
_global_config: Config | None = None


@dataclass
class Config:
    """Central configuration for a pipeline run.

    Attributes:
        input_dir: Directory containing input files
        output_dir: Directory for output files
        input_pattern: Pattern for input files, e.g. "{date}.feather"
        market: Market identifier, e.g. "CN", "crypto"
        columns: Mapping from semantic names to actual column names
        binwidths: Mapping from column names to bin widths
        horizons: List of forward return horizons in seconds
        time_cutoff: Optional time cutoff (e.g. 143000000 for 14:30:00)
    """

    input_dir: Path
    output_dir: Path
    input_pattern: str = "{date}.feather"
    market: str = "CN"
    columns: dict[str, str] = field(default_factory=dict)
    binwidths: dict[str, float] = field(default_factory=dict)
    group_by: list[str] = field(default_factory=list)
    horizons: list[int] = field(default_factory=list)
    time_cutoff: int | None = None

    def __post_init__(self):
        """Convert paths to Path objects if needed."""
        if isinstance(self.input_dir, str):
            self.input_dir = Path(self.input_dir)
        if isinstance(self.output_dir, str):
            self.output_dir = Path(self.output_dir)

    def col(self, semantic: str) -> str:
        """Get actual column name from semantic name.

        Args:
            semantic: Semantic column name (e.g. "timestamp", "price")

        Returns:
            Actual column name, or the semantic name if no mapping exists
        """
        return self.columns.get(semantic, semantic)

    def get_input_path(self, date: str) -> Path:
        """Get input file path for a date.

        Args:
            date: Date string, e.g. "20241001"

        Returns:
            Full path to input file
        """
        return self.input_dir / self.input_pattern.format(date=date)

    def get_output_path(self, date: str, suffix: str = ".parquet") -> Path:
        """Get output file path for a date.

        Args:
            date: Date string, e.g. "20241001"
            suffix: File suffix, default ".parquet"

        Returns:
            Full path to output file
        """
        return self.output_dir / f"{date}{suffix}"


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
