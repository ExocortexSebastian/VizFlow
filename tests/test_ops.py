"""Tests for ops module."""

import polars as pl
import pytest

from vizflow import Config, aggregate, bin, parse_time, set_config


class TestParseTime:
    """Tests for parse_time function."""

    @pytest.fixture(autouse=True)
    def setup_config(self):
        """Set up global config before each test."""
        config = Config(market="CN", input_dir=".", output_dir=".")
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
        config = Config(market="CRYPTO", input_dir=".", output_dir=".")
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
