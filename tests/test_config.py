"""Tests for Config."""

from pathlib import Path

from vizflow import Config


def test_config_col_mapping():
    """Test column name mapping."""
    config = Config(
        input_dir=Path("/data"),
        output_dir=Path("/output"),
        columns={"timestamp": "ticktime", "price": "mid", "symbol": "ukey"},
    )
    assert config.col("timestamp") == "ticktime"
    assert config.col("price") == "mid"
    assert config.col("symbol") == "ukey"
    # Fallback to semantic name if not mapped
    assert config.col("unknown") == "unknown"


def test_config_path_generation():
    """Test input/output path generation."""
    config = Config(
        input_dir=Path("/data/trades"),
        output_dir=Path("/data/output"),
        input_pattern="trades_{date}.feather",
    )
    assert config.get_input_path("20241001") == Path("/data/trades/trades_20241001.feather")
    assert config.get_output_path("20241001") == Path("/data/output/20241001.parquet")


def test_config_string_paths():
    """Test that string paths are converted to Path objects."""
    config = Config(
        input_dir="/data/trades",
        output_dir="/data/output",
    )
    assert isinstance(config.input_dir, Path)
    assert isinstance(config.output_dir, Path)


def test_config_defaults():
    """Test default values."""
    config = Config(
        input_dir=Path("/data"),
        output_dir=Path("/output"),
    )
    assert config.input_pattern == "{date}.feather"
    assert config.market == "CN"
    assert config.columns == {}
    assert config.binwidths == {}
    assert config.horizons == []
