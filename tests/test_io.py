"""Tests for vizflow I/O functions with column mapping."""

from pathlib import Path

import polars as pl
import pytest

import vizflow as vf
from vizflow.presets import YLIN


class TestYlinPreset:
    """Test YLIN preset contains expected mappings."""

    def test_ylin_has_order_columns(self):
        """Test YLIN maps order columns."""
        assert YLIN["symbol"] == "ukey"
        assert YLIN["orderId"] == "order_id"
        assert YLIN["orderSide"] == "order_side"
        assert YLIN["orderQty"] == "order_qty"
        assert YLIN["fillPrice"] == "fill_price"

    def test_ylin_has_quote_columns(self):
        """Test YLIN maps quote/TOB columns."""
        assert YLIN["bid"] == "bid_px0"
        assert YLIN["ask"] == "ask_px0"
        assert YLIN["bsize"] == "bid_size0"
        assert YLIN["asize"] == "ask_size0"
        assert YLIN["quoteTs"] == "timestamp"

    def test_ylin_has_position_columns(self):
        """Test YLIN maps position columns."""
        assert YLIN["pos"] == "current_net_pos"
        assert YLIN["startPos"] == "init_net_pos"
        assert YLIN["cumBuy"] == "cum_buy"
        assert YLIN["cumSell"] == "cum_sell"

    def test_ylin_total_mappings(self):
        """Test YLIN has expected number of mappings."""
        assert len(YLIN) == 52


class TestScanTrade:
    """Test scan_trade with column mapping."""

    def test_scan_trade_with_ylin_preset(self):
        """Test scan_trade applies ylin preset mappings."""
        config = vf.Config(
            trade_dir=Path("data/ylin/trade"),
            trade_pattern="{date}.meords",
            column_preset="ylin",
            market="CN",
        )
        vf.set_config(config)

        df = vf.scan_trade("11110101")
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
            column_preset="ylin",
            market="CN",
        )
        vf.set_config(config)

        df = vf.scan_trade("11110101")
        cols = df.collect_schema().names()

        # These columns are not in YLIN mapping, should pass through
        assert "ecn" in cols, "ecn should pass through unchanged"
        assert "JI" in cols, "JI should pass through unchanged"

    def test_scan_trade_drops_hftord_column(self):
        """Test #HFTORD record prefix column is dropped."""
        config = vf.Config(
            trade_dir=Path("data/ylin/trade"),
            trade_pattern="{date}.meords",
            column_preset="ylin",
            market="CN",
        )
        vf.set_config(config)

        df = vf.scan_trade("11110101")
        cols = df.collect_schema().names()

        assert "#HFTORD" not in cols, "#HFTORD should be dropped"

    def test_scan_trade_data_values(self):
        """Test actual data values are correct after mapping."""
        config = vf.Config(
            trade_dir=Path("data/ylin/trade"),
            trade_pattern="{date}.meords",
            column_preset="ylin",
            market="CN",
        )
        vf.set_config(config)

        df = vf.scan_trade("11110101").collect()

        # Check order_side values
        sides = df["order_side"].unique().to_list()
        assert "Buy" in sides or "Sell" in sides, "order_side should have Buy/Sell values"

        # Check ukey is numeric (stock codes)
        assert df["ukey"].dtype in [pl.Int64, pl.Float64], "ukey should be numeric"

    def test_scan_trade_without_preset(self):
        """Test scan_trade without preset keeps original names."""
        config = vf.Config(
            trade_dir=Path("data/ylin/trade"),
            trade_pattern="{date}.meords",
            column_preset=None,  # No preset
            market="CN",
        )
        vf.set_config(config)

        df = vf.scan_trade("11110101")
        cols = df.collect_schema().names()

        # Original names should exist
        assert "symbol" in cols, "symbol should exist without preset"
        assert "orderSide" in cols, "orderSide should exist without preset"
        assert "bid" in cols, "bid should exist without preset"


class TestScanTrades:
    """Test scan_trades (all files) with column mapping."""

    def test_scan_trades_with_ylin_preset(self):
        """Test scan_trades applies ylin preset mappings."""
        config = vf.Config(
            trade_dir=Path("data/ylin/trade"),
            trade_pattern="{date}.meords",
            column_preset="ylin",
            market="CN",
        )
        vf.set_config(config)

        df = vf.scan_trades()
        cols = df.collect_schema().names()

        # Check renamed columns exist
        assert "ukey" in cols
        assert "order_side" in cols
        assert "timestamp" in cols
