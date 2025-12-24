"""Tests for schema evolution functionality."""

import polars as pl
import pytest

from vizflow.schema_evolution import (
    JYAO_V20251114,
    SCHEMAS,
    YLIN_V20251204,
    ColumnSpec,
    SchemaEvolution,
    get_schema,
)


class TestColumnSpec:
    """Tests for ColumnSpec dataclass."""

    def test_rename_only(self):
        """ColumnSpec with only rename."""
        spec = ColumnSpec(rename_to="ukey")
        assert spec.rename_to == "ukey"
        assert spec.parse_dtype is None
        assert spec.cast_dtype is None

    def test_parse_and_cast(self):
        """ColumnSpec with parse and cast types."""
        spec = ColumnSpec(
            rename_to="order_filled_qty",
            parse_dtype=pl.Float64,
            cast_dtype=pl.Int64,
        )
        assert spec.rename_to == "order_filled_qty"
        assert spec.parse_dtype == pl.Float64
        assert spec.cast_dtype == pl.Int64

    def test_parse_only(self):
        """ColumnSpec with only parse type (no cast)."""
        spec = ColumnSpec(rename_to="timestamp", parse_dtype=pl.Int64)
        assert spec.parse_dtype == pl.Int64
        assert spec.cast_dtype is None


class TestSchemaEvolution:
    """Tests for SchemaEvolution dataclass."""

    def test_get_rename_map(self):
        """get_rename_map returns correct mapping."""
        schema = SchemaEvolution(
            columns={
                "symbol": ColumnSpec(rename_to="ukey"),
                "fillQty": ColumnSpec(rename_to="order_filled_qty"),
            }
        )
        rename_map = schema.get_rename_map()
        assert rename_map == {"symbol": "ukey", "fillQty": "order_filled_qty"}

    def test_get_schema_overrides(self):
        """get_schema_overrides returns parse types."""
        schema = SchemaEvolution(
            columns={
                "symbol": ColumnSpec(rename_to="ukey", parse_dtype=pl.Int64),
                "fillQty": ColumnSpec(
                    rename_to="order_filled_qty",
                    parse_dtype=pl.Float64,
                    cast_dtype=pl.Int64,
                ),
                "orderSide": ColumnSpec(rename_to="order_side"),  # No parse_dtype
            }
        )
        overrides = schema.get_schema_overrides()
        assert overrides == {"symbol": pl.Int64, "fillQty": pl.Float64}
        assert "orderSide" not in overrides

    def test_get_cast_map(self):
        """get_cast_map returns cast types with final column names."""
        schema = SchemaEvolution(
            columns={
                "fillQty": ColumnSpec(
                    rename_to="order_filled_qty",
                    parse_dtype=pl.Float64,
                    cast_dtype=pl.Int64,
                ),
                "bid": ColumnSpec(rename_to="bid_px0", parse_dtype=pl.Float64),
            }
        )
        cast_map = schema.get_cast_map()
        # Uses final name (after rename)
        assert cast_map == {"order_filled_qty": pl.Int64}
        assert "bid_px0" not in cast_map  # No cast_dtype

    def test_get_drop_columns(self):
        """get_drop_columns returns set of columns to drop."""
        schema = SchemaEvolution(
            columns={},
            drop=["#HFTORD", "temp_col"],
        )
        drop_cols = schema.get_drop_columns()
        assert drop_cols == {"#HFTORD", "temp_col"}

    def test_get_null_values(self):
        """get_null_values returns null strings."""
        schema = SchemaEvolution(
            columns={},
            null_values=["", "NA", "null"],
        )
        assert schema.get_null_values() == ["", "NA", "null"]

    def test_validate_warns_cast_without_parse(self):
        """validate warns when cast_dtype is set without parse_dtype."""
        schema = SchemaEvolution(
            columns={
                "good": ColumnSpec(parse_dtype=pl.Float64, cast_dtype=pl.Int64),
                "bad": ColumnSpec(cast_dtype=pl.Int64),  # Missing parse_dtype
            }
        )
        warnings = schema.validate()
        assert len(warnings) == 1
        assert "bad" in warnings[0]

    def test_parent_inheritance(self):
        """Child schema inherits from parent."""
        parent = SchemaEvolution(
            columns={
                "symbol": ColumnSpec(rename_to="ukey", parse_dtype=pl.Int64),
                "bid": ColumnSpec(rename_to="bid_px0", parse_dtype=pl.Float64),
            },
            drop=["#HFTORD"],
        )
        child = SchemaEvolution(
            columns={
                "newCol": ColumnSpec(rename_to="new_col"),
                "symbol": ColumnSpec(rename_to="ticker"),  # Override parent
            },
            parent=parent,
        )

        rename_map = child.get_rename_map()
        assert rename_map["symbol"] == "ticker"  # Child overrides
        assert rename_map["bid"] == "bid_px0"  # Inherited from parent
        assert rename_map["newCol"] == "new_col"  # Child's own

        drop_cols = child.get_drop_columns()
        assert "#HFTORD" in drop_cols  # Inherited


class TestSchemaRegistry:
    """Tests for schema registry."""

    def test_get_schema_by_name(self):
        """get_schema returns schema by name."""
        schema = get_schema("ylin_v20251204")
        assert schema is YLIN_V20251204

    def test_get_schema_case_insensitive(self):
        """get_schema is case insensitive."""
        schema = get_schema("YLIN_V20251204")
        assert schema is YLIN_V20251204

    def test_get_schema_none(self):
        """get_schema returns None for None input."""
        assert get_schema(None) is None

    def test_get_schema_unknown(self):
        """get_schema returns None for unknown name."""
        assert get_schema("unknown_schema") is None

    def test_schemas_registry_contains_all(self):
        """SCHEMAS registry contains all defined schemas."""
        assert "ylin_v20251204" in SCHEMAS
        assert "jyao_v20251114" in SCHEMAS


class TestYlinSchema:
    """Tests for YLIN_V20251204 schema definition."""

    def test_has_order_columns(self):
        """YLIN schema has order column mappings."""
        rename_map = YLIN_V20251204.get_rename_map()
        assert rename_map["symbol"] == "ukey"
        assert rename_map["orderId"] == "order_id"
        assert rename_map["orderSide"] == "order_side"
        assert rename_map["fillQty"] == "order_filled_qty"

    def test_has_quote_columns(self):
        """YLIN schema has quote column mappings."""
        rename_map = YLIN_V20251204.get_rename_map()
        assert rename_map["bid"] == "bid_px0"
        assert rename_map["ask"] == "ask_px0"
        assert rename_map["bsize"] == "bid_size0"
        assert rename_map["asize"] == "ask_size0"

    def test_qty_columns_parse_float_cast_int(self):
        """Qty columns parse as Float64 and cast to Int64."""
        overrides = YLIN_V20251204.get_schema_overrides()
        cast_map = YLIN_V20251204.get_cast_map()

        # fillQty parses as Float64
        assert overrides["fillQty"] == pl.Float64
        # After rename to order_filled_qty, cast to Int64
        assert cast_map["order_filled_qty"] == pl.Int64

    def test_timestamp_columns_parse_int(self):
        """Timestamp columns parse as Int64."""
        overrides = YLIN_V20251204.get_schema_overrides()
        assert overrides["lastExchangeTs"] == pl.Int64
        assert overrides["createdTs"] == pl.Int64
        assert overrides["quoteTs"] == pl.Int64

    def test_string_columns_parse_string(self):
        """String columns parse as String."""
        overrides = YLIN_V20251204.get_schema_overrides()
        assert overrides["orderSide"] == pl.String
        assert overrides["event"] == pl.String

    def test_drops_hftord(self):
        """YLIN schema drops #HFTORD column."""
        drop_cols = YLIN_V20251204.get_drop_columns()
        assert "#HFTORD" in drop_cols


class TestJyaoSchema:
    """Tests for JYAO_V20251114 schema definition."""

    def test_has_quote_columns(self):
        """JYAO schema has quote column mappings."""
        rename_map = JYAO_V20251114.get_rename_map()
        assert rename_map["BidPrice1"] == "bid_px0"
        assert rename_map["AskPrice1"] == "ask_px0"
        assert rename_map["BidVolume1"] == "bid_size0"

    def test_has_alpha_columns(self):
        """JYAO schema has alpha predictor mappings."""
        rename_map = JYAO_V20251114.get_rename_map()
        assert rename_map["x10s"] == "x_10s"
        assert rename_map["x60s"] == "x_60s"
        assert rename_map["alpha1"] == "x_3m"
        assert rename_map["alpha2"] == "x_30m"

    def test_volume_parse_float_cast_int(self):
        """Volume columns parse as Float64 and cast to Int64."""
        overrides = JYAO_V20251114.get_schema_overrides()
        cast_map = JYAO_V20251114.get_cast_map()

        assert overrides["Volume"] == pl.Float64
        assert cast_map["volume"] == pl.Int64
