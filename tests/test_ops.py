"""Tests for ops module."""

import polars as pl
import pytest

from vizflow import Config, aggregate, bin, forward_return, parse_time, set_config


class TestParseTime:
    """Tests for parse_time function."""

    @pytest.fixture(autouse=True)
    def setup_config(self):
        """Set up global config before each test."""
        config = Config(market="CN")
        set_config(config)

    def test_morning_open(self):
        """09:30:00.000 → 0 ms"""
        df = pl.DataFrame({"ts": [93000000]}).lazy()
        result = parse_time(df, "ts").collect()

        # Check tod column
        assert "tod_ts" in result.columns
        assert result["tod_ts"][0].hour == 9
        assert result["tod_ts"][0].minute == 30
        assert result["tod_ts"][0].second == 0

        # Check elapsed column (milliseconds)
        assert "elapsed_ts" in result.columns
        assert result["elapsed_ts"][0] == 0

    def test_morning_with_ms(self):
        """09:30:12.145 → 12145 ms"""
        df = pl.DataFrame({"ts": [93012145]}).lazy()
        result = parse_time(df, "ts").collect()

        # Check tod
        assert result["tod_ts"][0].hour == 9
        assert result["tod_ts"][0].minute == 30
        assert result["tod_ts"][0].second == 12

        # Check elapsed: 12 seconds + 145 ms = 12145 ms
        assert result["elapsed_ts"][0] == 12145

    def test_ten_oclock(self):
        """10:00:00.000 → 1800000 ms (30 minutes)"""
        df = pl.DataFrame({"ts": [100000000]}).lazy()
        result = parse_time(df, "ts").collect()

        assert result["tod_ts"][0].hour == 10
        assert result["tod_ts"][0].minute == 0

        # 30 minutes * 60 seconds/min * 1000 ms/sec = 1800000 ms
        assert result["elapsed_ts"][0] == 1800000

    def test_morning_end(self):
        """11:29:59.999 → 7199999 ms"""
        df = pl.DataFrame({"ts": [112959999]}).lazy()
        result = parse_time(df, "ts").collect()

        assert result["tod_ts"][0].hour == 11
        assert result["tod_ts"][0].minute == 29
        assert result["tod_ts"][0].second == 59

        # 2 hours * 3600 - 1 second + 999ms = 7199999 ms
        assert result["elapsed_ts"][0] == 7199999

    def test_afternoon_open(self):
        """13:00:00.000 → 7200000 ms"""
        df = pl.DataFrame({"ts": [130000000]}).lazy()
        result = parse_time(df, "ts").collect()

        assert result["tod_ts"][0].hour == 13
        assert result["tod_ts"][0].minute == 0

        # 2 hours of morning session = 7200 seconds = 7200000 ms
        assert result["elapsed_ts"][0] == 7200000

    def test_afternoon_with_ms(self):
        """14:20:58.425 → 7200000 + 4858425 ms"""
        df = pl.DataFrame({"ts": [142058425]}).lazy()
        result = parse_time(df, "ts").collect()

        assert result["tod_ts"][0].hour == 14
        assert result["tod_ts"][0].minute == 20
        assert result["tod_ts"][0].second == 58

        # 2 hours morning + 1h 20m 58.425s = 7200 + 4858.425 seconds = 12058425 ms
        expected_ms = 7200000 + (1 * 3600 + 20 * 60 + 58) * 1000 + 425
        assert result["elapsed_ts"][0] == expected_ms

    def test_market_close(self):
        """15:00:00.000 → 14400000 ms"""
        df = pl.DataFrame({"ts": [150000000]}).lazy()
        result = parse_time(df, "ts").collect()

        assert result["tod_ts"][0].hour == 15
        assert result["tod_ts"][0].minute == 0

        # 2 hours morning + 2 hours afternoon = 4 hours = 14400 seconds = 14400000 ms
        assert result["elapsed_ts"][0] == 14400000

    def test_after_market_close(self):
        """15:00:00.100 → 14400100 ms (corner case: slightly after close)"""
        df = pl.DataFrame({"ts": [150000100]}).lazy()
        result = parse_time(df, "ts").collect()

        assert result["tod_ts"][0].hour == 15
        assert result["tod_ts"][0].minute == 0
        assert result["tod_ts"][0].second == 0

        # Handles events slightly after market close
        assert result["elapsed_ts"][0] == 14400100

    def test_unsupported_market(self):
        """Non-CN market raises NotImplementedError."""
        config = Config(market="CRYPTO")
        set_config(config)

        df = pl.DataFrame({"ts": [93000000]}).lazy()
        with pytest.raises(NotImplementedError, match="Market CRYPTO not supported"):
            parse_time(df, "ts").collect()


class TestBin:
    """Tests for bin function."""

    def test_single_column(self):
        """Bin single column."""
        df = pl.DataFrame({"alpha": [0.00015, 0.00025, 0.00035]}).lazy()
        result = bin(df, {"alpha": 1e-4}).collect()
        # Due to floating-point precision:
        # 0.00015/0.0001 = 1.4999999999999998 → round to 1
        # 0.00025/0.0001 = 2.5 → round to 2 (banker's rounding)
        # 0.00035/0.0001 = 3.5 → round to 4 (banker's rounding)
        assert "alpha_bin" in result.columns
        assert result["alpha_bin"].to_list() == [1, 2, 4]

    def test_multiple_columns(self):
        """Bin multiple columns."""
        df = pl.DataFrame({"alpha": [0.0001], "beta": [0.0005]}).lazy()
        result = bin(df, {"alpha": 1e-4, "beta": 1e-4}).collect()
        assert "alpha_bin" in result.columns
        assert "beta_bin" in result.columns
        assert result["alpha_bin"][0] == 1
        assert result["beta_bin"][0] == 5

    def test_negative_values(self):
        """Bin negative values."""
        df = pl.DataFrame({"x": [-0.00015, 0.0, 0.00015]}).lazy()
        result = bin(df, {"x": 1e-4}).collect()
        # Due to floating-point precision:
        # -0.00015/0.0001 = -1.4999999999999998 → round to -1
        # 0.0/0.0001 = 0.0 → round to 0
        # 0.00015/0.0001 = 1.4999999999999998 → round to 1
        assert result["x_bin"].to_list() == [-1, 0, 1]

    def test_preserves_original_columns(self):
        """Original columns are preserved."""
        df = pl.DataFrame({"alpha": [0.0001], "other": ["a"]}).lazy()
        result = bin(df, {"alpha": 1e-4}).collect()
        assert "alpha" in result.columns
        assert "other" in result.columns
        assert "alpha_bin" in result.columns


class TestAggregate:
    """Tests for aggregate function."""

    def test_simple_count(self):
        """Simple count aggregation."""
        df = pl.DataFrame({"group": ["A", "A", "B"], "value": [1, 2, 3]}).lazy()
        result = aggregate(df, ["group"], {"count": pl.len()}).collect()
        result = result.sort("group")
        assert result["count"].to_list() == [2, 1]

    def test_sum_aggregation(self):
        """Sum aggregation."""
        df = pl.DataFrame({"group": ["A", "A", "B"], "value": [1, 2, 3]}).lazy()
        result = aggregate(df, ["group"], {"total": pl.col("value").sum()}).collect()
        result = result.sort("group")
        assert result["total"].to_list() == [3, 3]

    def test_multiple_metrics(self):
        """Multiple metrics in one aggregation."""
        df = pl.DataFrame({"group": ["A", "A"], "value": [10, 20]}).lazy()
        result = aggregate(
            df,
            ["group"],
            {
                "count": pl.len(),
                "sum": pl.col("value").sum(),
                "mean": pl.col("value").mean(),
            },
        ).collect()
        assert result["count"][0] == 2
        assert result["sum"][0] == 30
        assert result["mean"][0] == 15.0

    def test_vwap_style_metric(self):
        """VWAP-style weighted average."""
        df = pl.DataFrame({
            "group": ["A", "A"],
            "price": [100.0, 110.0],
            "qty": [10, 20],
        }).lazy()
        result = aggregate(
            df,
            ["group"],
            {"vwap": pl.col("price").mul(pl.col("qty")).sum() / pl.col("qty").sum()},
        ).collect()
        # vwap = (100*10 + 110*20) / (10+20) = 3200/30 = 106.67
        assert result["vwap"][0] == pytest.approx(106.666666, rel=1e-4)


class TestForwardReturn:
    """Tests for forward_return function (two-DataFrame design)."""

    def test_single_horizon_60s(self):
        """60 second horizon creates forward_mid_60s and y_60s columns."""
        # Trade: one trade at t=0
        df_trade = pl.DataFrame({
            "ukey": [1],
            "elapsed_alpha_ts": [0],  # trade at t=0
            "mid": [100.0],
        }).lazy()

        # Alpha: prices over time
        df_alpha = pl.DataFrame({
            "ukey": [1, 1, 1],
            "elapsed_ticktime": [0, 60000, 120000],  # 0s, 60s, 120s
            "mid": [100.0, 101.0, 102.0],
        }).lazy()

        result = forward_return(df_trade, df_alpha, horizons=[60]).collect()

        assert "forward_mid_60s" in result.columns
        assert "y_60s" in result.columns
        # Trade at t=0: future price at 60s = 101, return = (101-100)/100 = 0.01
        assert result["forward_mid_60s"][0] == pytest.approx(101.0, rel=1e-6)
        assert result["y_60s"][0] == pytest.approx(0.01, rel=1e-6)

    def test_horizon_3m_naming(self):
        """180 second (3 min) horizon creates forward_mid_3m and y_3m columns."""
        df_trade = pl.DataFrame({
            "ukey": [1],
            "elapsed_alpha_ts": [0],
            "mid": [100.0],
        }).lazy()

        df_alpha = pl.DataFrame({
            "ukey": [1, 1],
            "elapsed_ticktime": [0, 180000],  # 0s, 180s
            "mid": [100.0, 103.0],
        }).lazy()

        result = forward_return(df_trade, df_alpha, horizons=[180]).collect()

        assert "forward_mid_3m" in result.columns
        assert "y_3m" in result.columns
        assert result["forward_mid_3m"][0] == pytest.approx(103.0, rel=1e-6)
        assert result["y_3m"][0] == pytest.approx(0.03, rel=1e-6)

    def test_multiple_horizons(self):
        """Multiple horizons create multiple forward_* and y_* columns."""
        df_trade = pl.DataFrame({
            "ukey": [1],
            "elapsed_alpha_ts": [0],
            "mid": [100.0],
        }).lazy()

        df_alpha = pl.DataFrame({
            "ukey": [1, 1, 1, 1],
            "elapsed_ticktime": [0, 60000, 180000, 1800000],
            "mid": [100.0, 101.0, 103.0, 110.0],
        }).lazy()

        result = forward_return(df_trade, df_alpha, horizons=[60, 180, 1800]).collect()

        assert "forward_mid_60s" in result.columns
        assert "forward_mid_3m" in result.columns
        assert "forward_mid_30m" in result.columns
        assert "y_60s" in result.columns
        assert "y_3m" in result.columns
        assert "y_30m" in result.columns

    def test_per_symbol_calculation(self):
        """Forward returns calculated separately per symbol."""
        # Two trades, one per symbol
        df_trade = pl.DataFrame({
            "ukey": [1, 2],
            "elapsed_alpha_ts": [0, 0],
            "mid": [100.0, 200.0],
        }).lazy()

        # Alpha prices for both symbols
        df_alpha = pl.DataFrame({
            "ukey": [1, 1, 2, 2],
            "elapsed_ticktime": [0, 60000, 0, 60000],
            "mid": [100.0, 110.0, 200.0, 220.0],
        }).lazy()

        result = forward_return(df_trade, df_alpha, horizons=[60]).collect()
        result = result.sort("ukey")

        # Symbol 1: (110-100)/100 = 0.10
        assert result.filter(pl.col("ukey") == 1)["y_60s"][0] == pytest.approx(0.10, rel=1e-6)
        # Symbol 2: (220-200)/200 = 0.10
        assert result.filter(pl.col("ukey") == 2)["y_60s"][0] == pytest.approx(0.10, rel=1e-6)

    def test_preserves_trade_columns(self):
        """Trade columns preserved after forward_return."""
        df_trade = pl.DataFrame({
            "ukey": [1],
            "elapsed_alpha_ts": [0],
            "mid": [100.0],
            "order_side": ["Buy"],
            "fill_price": [100.05],
        }).lazy()

        df_alpha = pl.DataFrame({
            "ukey": [1, 1],
            "elapsed_ticktime": [0, 60000],
            "mid": [100.0, 101.0],
        }).lazy()

        result = forward_return(df_trade, df_alpha, horizons=[60]).collect()

        assert "ukey" in result.columns
        assert "elapsed_alpha_ts" in result.columns
        assert "mid" in result.columns
        assert "order_side" in result.columns
        assert "fill_price" in result.columns
        assert result["order_side"][0] == "Buy"
        assert result["fill_price"][0] == pytest.approx(100.05, rel=1e-6)
