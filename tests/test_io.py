"""Tests for vizflow I/O functions with schema evolution."""

from pathlib import Path

import polars as pl
import pytest

import vizflow as vf
from vizflow.schema_evolution import YLIN_V20251204


class TestScanTrade:
    """Test scan_trade with schema evolution."""

    def test_scan_trade_with_schema(self):
        """Test scan_trade applies schema evolution."""
        config = vf.Config(
            trade_dir=Path("data/ylin/trade"),
            trade_pattern="{date}.meords",
            trade_schema="ylin_v20251204",
            market="CN",
        )
        vf.set_config(config)

        df = vf.scan_trade("20240827")
        cols = df.collect_schema().names()

        # Check renamed columns exist
        assert "ukey" in cols, "symbol should be renamed to ukey"
        assert "order_side" in cols, "orderSide should be renamed to order_side"
        assert "order_qty" in cols, "orderQty should be renamed to order_qty"
        assert "bid_px0" in cols, "bid should be renamed to bid_px0"
        assert "ask_px0" in cols, "ask should be renamed to ask_px0"
        assert "timestamp" in cols, "quoteTs should be renamed to timestamp"
        assert "current_net_pos" in cols, "pos should be renamed to current_net_pos"

        # Check original names no longer exist
        assert "symbol" not in cols, "symbol should be renamed"
        assert "orderSide" not in cols, "orderSide should be renamed"
        assert "bid" not in cols, "bid should be renamed"
        assert "pos" not in cols, "pos should be renamed"

    def test_scan_trade_passthrough_columns(self):
        """Test unmapped columns pass through unchanged."""
        config = vf.Config(
            trade_dir=Path("data/ylin/trade"),
            trade_pattern="{date}.meords",
            trade_schema="ylin_v20251204",
            market="CN",
        )
        vf.set_config(config)

        df = vf.scan_trade("20240827")
        cols = df.collect_schema().names()

        # These columns are not in schema, should pass through
        assert "ecn" in cols, "ecn should pass through unchanged"
        assert "JI" in cols, "JI should pass through unchanged"

    def test_scan_trade_drops_hftord_column(self):
        """Test #HFTORD record prefix column is dropped."""
        config = vf.Config(
            trade_dir=Path("data/ylin/trade"),
            trade_pattern="{date}.meords",
            trade_schema="ylin_v20251204",
            market="CN",
        )
        vf.set_config(config)

        df = vf.scan_trade("20240827")
        cols = df.collect_schema().names()

        assert "#HFTORD" not in cols, "#HFTORD should be dropped"

    def test_scan_trade_data_values(self):
        """Test actual data values are correct after schema evolution."""
        config = vf.Config(
            trade_dir=Path("data/ylin/trade"),
            trade_pattern="{date}.meords",
            trade_schema="ylin_v20251204",
            market="CN",
        )
        vf.set_config(config)

        df = vf.scan_trade("20240827").collect()

        # Check order_side values
        sides = df["order_side"].unique().to_list()
        assert "Buy" in sides or "Sell" in sides, "order_side should have Buy/Sell values"

        # Check ukey is integer (parsed as Int64)
        assert df["ukey"].dtype == pl.Int64, "ukey should be Int64"

    def test_scan_trade_qty_cast_to_int(self):
        """Test qty columns are cast from Float64 to Int64."""
        config = vf.Config(
            trade_dir=Path("data/ylin/trade"),
            trade_pattern="{date}.meords",
            trade_schema="ylin_v20251204",
            market="CN",
        )
        vf.set_config(config)

        df = vf.scan_trade("20240827").collect()

        # Qty columns should be Int64 after cast
        assert df["order_qty"].dtype == pl.Int64, "order_qty should be Int64"
        assert df["order_filled_qty"].dtype == pl.Int64, "order_filled_qty should be Int64"
        assert df["bid_size0"].dtype == pl.Int64, "bid_size0 should be Int64"
        assert df["ask_size0"].dtype == pl.Int64, "ask_size0 should be Int64"

    def test_scan_trade_without_schema(self):
        """Test scan_trade without schema keeps original names."""
        config = vf.Config(
            trade_dir=Path("data/ylin/trade"),
            trade_pattern="{date}.meords",
            trade_schema=None,
            market="CN",
        )
        vf.set_config(config)

        df = vf.scan_trade("20240827")
        cols = df.collect_schema().names()

        # Original names should exist (test data already uses some standard names)
        assert "ukey" in cols, "ukey should exist without schema"
        assert "order_side" in cols, "order_side should exist without schema"
        # Without schema, no casting is applied
        schema = df.collect_schema()
        # Polars infers types - qty columns may be Float64 or Int64
        assert schema["order_qty"] in [pl.Float64, pl.Int64]

    def test_scan_trade_with_schema_instance(self):
        """Test scan_trade accepts SchemaEvolution instance directly."""
        config = vf.Config(
            trade_dir=Path("data/ylin/trade"),
            trade_pattern="{date}.meords",
            trade_schema=YLIN_V20251204,  # Pass instance directly
            market="CN",
        )
        vf.set_config(config)

        df = vf.scan_trade("20240827")
        cols = df.collect_schema().names()

        assert "ukey" in cols
        assert "order_side" in cols


class TestScanTrades:
    """Test scan_trades (all files) with schema evolution."""

    def test_scan_trades_single_file(self):
        """Test scan_trades works with single file pattern."""
        # Note: Multi-file concat requires matching schemas across files.
        # Test data files have different schemas, so use single file pattern.
        config = vf.Config(
            trade_dir=Path("data/ylin/trade"),
            trade_pattern="20240827.meords",  # Single file pattern
            trade_schema="ylin_v20251204",
            market="CN",
        )
        vf.set_config(config)

        df = vf.scan_trades()
        cols = df.collect_schema().names()

        # Check renamed columns exist
        assert "ukey" in cols
        assert "order_side" in cols
        assert "timestamp" in cols


class TestUnsupportedFileFormat:
    """Test error handling for unsupported file formats."""

    def test_unsupported_extension_raises_error(self):
        """Test that unsupported file extensions raise a clear error."""
        from vizflow.io import _scan_file

        with pytest.raises(ValueError, match="Unsupported file format"):
            _scan_file("/data/trade.unknown")

    def test_error_message_lists_supported_formats(self):
        """Test error message lists all supported formats."""
        from vizflow.io import _scan_file

        try:
            _scan_file("/data/trade.xyz")
        except ValueError as e:
            error_msg = str(e)
            assert ".feather" in error_msg
            assert ".ipc" in error_msg
            assert ".arrow" in error_msg
            assert ".csv" in error_msg
            assert ".meords" in error_msg
            assert ".parquet" in error_msg
