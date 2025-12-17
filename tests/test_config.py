"""Tests for Config."""

from pathlib import Path

import polars as pl
import pytest

from vizflow import ColumnSchema, Config


def test_config_col_mapping_trade():
    """Test column name mapping for trade data."""
    config = Config(
        trade_columns={"timestamp": "fillTs", "price": "fillPrice", "symbol": "ukey"},
    )
    assert config.col("timestamp") == "fillTs"
    assert config.col("timestamp", source="trade") == "fillTs"
    assert config.col("price") == "fillPrice"
    assert config.col("symbol") == "ukey"
    # Fallback to semantic name if not mapped
    assert config.col("unknown") == "unknown"


def test_config_col_mapping_alpha():
    """Test column name mapping for alpha data."""
    config = Config(
        alpha_columns={"timestamp": "ticktime", "price": "mid", "symbol": "ukey"},
    )
    assert config.col("timestamp", source="alpha") == "ticktime"
    assert config.col("price", source="alpha") == "mid"
    assert config.col("symbol", source="alpha") == "ukey"
    # Fallback to semantic name if not mapped
    assert config.col("unknown", source="alpha") == "unknown"


def test_config_path_generation_alpha():
    """Test alpha path generation."""
    config = Config(
        alpha_dir=Path("/data/alpha"),
        alpha_pattern="alpha_{date}.feather",
    )
    assert config.get_alpha_path("20241001") == Path("/data/alpha/alpha_20241001.feather")


def test_config_path_generation_trade():
    """Test trade path generation."""
    config = Config(
        trade_dir=Path("/data/trade"),
        trade_pattern="trade_{date}.feather",
    )
    assert config.get_trade_path("20241001") == Path("/data/trade/trade_20241001.feather")


def test_config_path_generation_replay():
    """Test replay output path generation."""
    config = Config(
        replay_dir=Path("/data/replay"),
    )
    assert config.get_replay_path("20241001") == Path("/data/replay/20241001.parquet")


def test_config_path_generation_aggregate():
    """Test aggregate output path generation."""
    config = Config(
        aggregate_dir=Path("/data/partials"),
    )
    assert config.get_aggregate_path("20241001") == Path("/data/partials/20241001.parquet")


def test_config_path_not_set():
    """Test error when path not set."""
    config = Config()

    with pytest.raises(ValueError, match="alpha_dir is not set"):
        config.get_alpha_path("20241001")

    with pytest.raises(ValueError, match="trade_dir is not set"):
        config.get_trade_path("20241001")

    with pytest.raises(ValueError, match="replay_dir is not set"):
        config.get_replay_path("20241001")

    with pytest.raises(ValueError, match="aggregate_dir is not set"):
        config.get_aggregate_path("20241001")


def test_config_string_paths():
    """Test that string paths are converted to Path objects."""
    config = Config(
        alpha_dir="/data/alpha",
        trade_dir="/data/trade",
        calendar_path="/data/calendar.parquet",
        replay_dir="/data/replay",
        aggregate_dir="/data/partials",
    )
    assert isinstance(config.alpha_dir, Path)
    assert isinstance(config.trade_dir, Path)
    assert isinstance(config.calendar_path, Path)
    assert isinstance(config.replay_dir, Path)
    assert isinstance(config.aggregate_dir, Path)


def test_config_defaults():
    """Test default values."""
    config = Config()

    assert config.alpha_dir is None
    assert config.trade_dir is None
    assert config.calendar_path is None
    assert config.replay_dir is None
    assert config.aggregate_dir is None
    assert config.alpha_pattern == "alpha_{date}.feather"
    assert config.trade_pattern == "trade_{date}.feather"
    assert config.market == "CN"
    assert config.alpha_columns == {}
    assert config.trade_columns == {}
    assert config.alpha_schema == {}
    assert config.trade_schema == {}
    assert config.binwidths == {}
    assert config.horizons == []


def test_column_schema():
    """Test ColumnSchema dataclass."""
    schema = ColumnSchema(cast_to=pl.Int64)
    assert schema.cast_to == pl.Int64


def test_config_with_schema():
    """Test Config with schema evolution."""
    config = Config(
        trade_schema={
            "qty": ColumnSchema(cast_to=pl.Int64),
            "price": ColumnSchema(cast_to=pl.Float64),
        },
    )
    assert "qty" in config.trade_schema
    assert config.trade_schema["qty"].cast_to == pl.Int64
    assert config.trade_schema["price"].cast_to == pl.Float64


class TestDateValidation:
    """Test date validation to prevent path traversal."""

    def test_valid_date_format(self):
        """Test valid date format is accepted."""
        config = Config(alpha_dir=Path("/data/alpha"))
        # Should not raise
        path = config.get_alpha_path("20241001")
        assert path == Path("/data/alpha/alpha_20241001.feather")

    def test_path_traversal_attack_rejected(self):
        """Test path traversal attempts are rejected."""
        config = Config(alpha_dir=Path("/data/alpha"))
        with pytest.raises(ValueError, match="Invalid date format"):
            config.get_alpha_path("../../../etc/passwd")

    def test_short_date_rejected(self):
        """Test date shorter than 8 characters is rejected."""
        config = Config(trade_dir=Path("/data/trade"))
        with pytest.raises(ValueError, match="Invalid date format"):
            config.get_trade_path("2024101")  # Only 7 digits

    def test_long_date_rejected(self):
        """Test date longer than 8 characters is rejected."""
        config = Config(replay_dir=Path("/data/replay"))
        with pytest.raises(ValueError, match="Invalid date format"):
            config.get_replay_path("202410011")  # 9 digits

    def test_non_digit_date_rejected(self):
        """Test date with non-digit characters is rejected."""
        config = Config(aggregate_dir=Path("/data/partials"))
        with pytest.raises(ValueError, match="Invalid date format"):
            config.get_aggregate_path("2024-10-01")  # Contains hyphens

    def test_date_with_slash_rejected(self):
        """Test date containing slashes is rejected."""
        config = Config(alpha_dir=Path("/data/alpha"))
        with pytest.raises(ValueError, match="Invalid date format"):
            config.get_alpha_path("20241001/../malicious")
