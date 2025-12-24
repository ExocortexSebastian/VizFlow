"""Schema Evolution for VizFlow.

This module defines how raw data evolves into standard format through:
- Column renaming (raw names → standard names)
- Parse-time type specification (for CSV parsing)
- Post-load type casting (e.g., Float64 → Int64)
- Null value handling
- Column exclusion

Example:
    >>> schema = SchemaEvolution(
    ...     columns={
    ...         "fillQty": ColumnSpec(
    ...             rename_to="order_filled_qty",
    ...             parse_dtype=pl.Float64,  # Parse as float (catch decimals)
    ...             cast_dtype=pl.Int64,     # Then cast to int
    ...         ),
    ...     },
    ...     null_values=["", "NA"],
    ...     drop=["#HFTORD"],
    ... )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import polars as pl


@dataclass
class ColumnSpec:
    """Specification for a single column's parsing and transformation.

    Attributes:
        rename_to: Standard column name after rename. None keeps original name.
        parse_dtype: Type to use when parsing CSV. None uses Polars inference.
        cast_dtype: Final type after post-load casting. None keeps parse type.

    Examples:
        # Rename only (most common)
        ColumnSpec(rename_to="ukey")

        # Parse as Float64, cast to Int64 (handle decimal errors in qty)
        ColumnSpec(rename_to="order_filled_qty",
                   parse_dtype=pl.Float64,
                   cast_dtype=pl.Int64)

        # Parse as specific type, no cast (trusted integer)
        ColumnSpec(rename_to="timestamp", parse_dtype=pl.Int64)
    """

    rename_to: str | None = None
    parse_dtype: Any = None  # pl.DataType
    cast_dtype: Any = None   # pl.DataType


@dataclass
class SchemaEvolution:
    """Defines how raw data evolves into standard format.

    Combines column renaming, parse-time types, post-load casting,
    null value handling, and column exclusion into a single structure.

    Attributes:
        columns: Mapping from original column name to ColumnSpec.
        null_values: Strings to treat as null at parse time.
        drop: Column names to exclude from output.
        parent: Optional parent schema for version inheritance.

    Example:
        >>> YLIN_V20251204 = SchemaEvolution(
        ...     columns={
        ...         "symbol": ColumnSpec(rename_to="ukey", parse_dtype=pl.Int64),
        ...         "fillQty": ColumnSpec(
        ...             rename_to="order_filled_qty",
        ...             parse_dtype=pl.Float64,
        ...             cast_dtype=pl.Int64,
        ...         ),
        ...     },
        ...     null_values=["", "NA", "null"],
        ...     drop=["#HFTORD"],
        ... )
    """

    columns: dict[str, ColumnSpec] = field(default_factory=dict)
    null_values: list[str] = field(default_factory=lambda: ["", "NA", "null"])
    drop: list[str] = field(default_factory=list)
    parent: SchemaEvolution | None = None

    def get_schema_overrides(self) -> dict[str, Any]:
        """Get schema_overrides dict for pl.scan_csv().

        Returns:
            Mapping from original column name to Polars dtype.
        """
        result = {}
        if self.parent:
            result.update(self.parent.get_schema_overrides())
        for col_name, spec in self.columns.items():
            if spec.parse_dtype is not None:
                result[col_name] = spec.parse_dtype
        return result

    def get_rename_map(self) -> dict[str, str]:
        """Get rename mapping dict for df.rename().

        Returns:
            Mapping from original column name to new name.
        """
        result = {}
        if self.parent:
            result.update(self.parent.get_rename_map())
        for col_name, spec in self.columns.items():
            if spec.rename_to is not None:
                result[col_name] = spec.rename_to
        return result

    def get_cast_map(self) -> dict[str, Any]:
        """Get post-load cast mapping dict.

        Returns:
            Mapping from FINAL column name (after rename) to cast dtype.
        """
        result = {}
        if self.parent:
            result.update(self.parent.get_cast_map())
        for col_name, spec in self.columns.items():
            if spec.cast_dtype is not None:
                final_name = spec.rename_to or col_name
                result[final_name] = spec.cast_dtype
        return result

    def get_drop_columns(self) -> set[str]:
        """Get set of columns to drop.

        Returns:
            Set of original column names to exclude.
        """
        result = set()
        if self.parent:
            result.update(self.parent.get_drop_columns())
        result.update(self.drop)
        return result

    def get_null_values(self) -> list[str]:
        """Get list of null value strings.

        Returns:
            List of strings to treat as null at parse time.
        """
        return self.null_values

    def validate(self) -> list[str]:
        """Validate schema configuration.

        Returns:
            List of warnings about potential issues.
        """
        warnings = []
        for col_name, spec in self.columns.items():
            if spec.cast_dtype is not None and spec.parse_dtype is None:
                warnings.append(
                    f"{col_name}: cast_dtype without parse_dtype may fail "
                    "if Polars infers wrong type"
                )
        return warnings


# =============================================================================
# YLIN Trade Format (v2025-12-04)
# =============================================================================

YLIN_V20251204 = SchemaEvolution(
    columns={
        # === Order columns (18) ===
        "symbol": ColumnSpec(rename_to="ukey", parse_dtype=pl.Int64),
        "orderId": ColumnSpec(rename_to="order_id", parse_dtype=pl.Int64),
        "orderSide": ColumnSpec(rename_to="order_side", parse_dtype=pl.String),
        "orderQty": ColumnSpec(
            rename_to="order_qty",
            parse_dtype=pl.Float64,
            cast_dtype=pl.Int64,
        ),
        "orderPrice": ColumnSpec(rename_to="order_price", parse_dtype=pl.Float64),
        "priceType": ColumnSpec(rename_to="order_price_type", parse_dtype=pl.String),
        "fillQty": ColumnSpec(
            rename_to="order_filled_qty",
            parse_dtype=pl.Float64,
            cast_dtype=pl.Int64,
        ),
        "fillPrice": ColumnSpec(rename_to="fill_price", parse_dtype=pl.Float64),
        "lastExchangeTs": ColumnSpec(rename_to="update_exchange_ts", parse_dtype=pl.Int64),
        "createdTs": ColumnSpec(rename_to="create_exchange_ts", parse_dtype=pl.Int64),
        "localTs": ColumnSpec(rename_to="create_local_ts", parse_dtype=pl.Int64),
        "qtyAhead": ColumnSpec(
            rename_to="qty_ahead",
            parse_dtype=pl.Float64,
            cast_dtype=pl.Int64,
        ),
        "qtyBehind": ColumnSpec(
            rename_to="qty_behind",
            parse_dtype=pl.Float64,
            cast_dtype=pl.Int64,
        ),
        "orderStatus": ColumnSpec(rename_to="order_curr_state", parse_dtype=pl.String),
        "orderTposType": ColumnSpec(rename_to="order_tpos_type", parse_dtype=pl.String),
        "alphaTs": ColumnSpec(rename_to="alpha_ts", parse_dtype=pl.Int64),
        "event": ColumnSpec(rename_to="event_type", parse_dtype=pl.String),
        "cumFilledNotional": ColumnSpec(
            rename_to="order_filled_notional",
            parse_dtype=pl.Float64,
        ),
        # === Quote columns (20) ===
        "bid": ColumnSpec(rename_to="bid_px0", parse_dtype=pl.Float64),
        "bid2": ColumnSpec(rename_to="bid_px1", parse_dtype=pl.Float64),
        "bid3": ColumnSpec(rename_to="bid_px2", parse_dtype=pl.Float64),
        "bid4": ColumnSpec(rename_to="bid_px3", parse_dtype=pl.Float64),
        "bid5": ColumnSpec(rename_to="bid_px4", parse_dtype=pl.Float64),
        "ask": ColumnSpec(rename_to="ask_px0", parse_dtype=pl.Float64),
        "ask2": ColumnSpec(rename_to="ask_px1", parse_dtype=pl.Float64),
        "ask3": ColumnSpec(rename_to="ask_px2", parse_dtype=pl.Float64),
        "ask4": ColumnSpec(rename_to="ask_px3", parse_dtype=pl.Float64),
        "ask5": ColumnSpec(rename_to="ask_px4", parse_dtype=pl.Float64),
        "bsize": ColumnSpec(
            rename_to="bid_size0",
            parse_dtype=pl.Float64,
            cast_dtype=pl.Int64,
        ),
        "bsize2": ColumnSpec(
            rename_to="bid_size1",
            parse_dtype=pl.Float64,
            cast_dtype=pl.Int64,
        ),
        "bsize3": ColumnSpec(
            rename_to="bid_size2",
            parse_dtype=pl.Float64,
            cast_dtype=pl.Int64,
        ),
        "bsize4": ColumnSpec(
            rename_to="bid_size3",
            parse_dtype=pl.Float64,
            cast_dtype=pl.Int64,
        ),
        "bsize5": ColumnSpec(
            rename_to="bid_size4",
            parse_dtype=pl.Float64,
            cast_dtype=pl.Int64,
        ),
        "asize": ColumnSpec(
            rename_to="ask_size0",
            parse_dtype=pl.Float64,
            cast_dtype=pl.Int64,
        ),
        "asize2": ColumnSpec(
            rename_to="ask_size1",
            parse_dtype=pl.Float64,
            cast_dtype=pl.Int64,
        ),
        "asize3": ColumnSpec(
            rename_to="ask_size2",
            parse_dtype=pl.Float64,
            cast_dtype=pl.Int64,
        ),
        "asize4": ColumnSpec(
            rename_to="ask_size3",
            parse_dtype=pl.Float64,
            cast_dtype=pl.Int64,
        ),
        "asize5": ColumnSpec(
            rename_to="ask_size4",
            parse_dtype=pl.Float64,
            cast_dtype=pl.Int64,
        ),
        "isRebasedQuote": ColumnSpec(rename_to="is_rebased", parse_dtype=pl.String),
        "quoteSeqNum": ColumnSpec(rename_to="seq_num", parse_dtype=pl.Int64),
        "quoteTs": ColumnSpec(rename_to="timestamp", parse_dtype=pl.Int64),
        # === Position columns (11) ===
        "startPos": ColumnSpec(
            rename_to="init_net_pos",
            parse_dtype=pl.Float64,
            cast_dtype=pl.Int64,
        ),
        "pos": ColumnSpec(
            rename_to="current_net_pos",
            parse_dtype=pl.Float64,
            cast_dtype=pl.Int64,
        ),
        "realizedPos": ColumnSpec(
            rename_to="current_realized_net_pos",
            parse_dtype=pl.Float64,
            cast_dtype=pl.Int64,
        ),
        "openBuyPos": ColumnSpec(
            rename_to="open_buy",
            parse_dtype=pl.Float64,
            cast_dtype=pl.Int64,
        ),
        "openSellPos": ColumnSpec(
            rename_to="open_sell",
            parse_dtype=pl.Float64,
            cast_dtype=pl.Int64,
        ),
        "cumBuy": ColumnSpec(
            rename_to="cum_buy",
            parse_dtype=pl.Float64,
            cast_dtype=pl.Int64,
        ),
        "cumSell": ColumnSpec(
            rename_to="cum_sell",
            parse_dtype=pl.Float64,
            cast_dtype=pl.Int64,
        ),
        "cashFlow": ColumnSpec(rename_to="cash_flow", parse_dtype=pl.Float64),
        "frozenCash": ColumnSpec(rename_to="frozen_cash", parse_dtype=pl.Float64),
        "globalCumBuyNotional": ColumnSpec(
            rename_to="cum_buy_filled_notional",
            parse_dtype=pl.Float64,
        ),
        "globalCumSellNotional": ColumnSpec(
            rename_to="cum_sell_filled_notional",
            parse_dtype=pl.Float64,
        ),
    },
    null_values=["", "NA", "null", "NULL"],
    drop=["#HFTORD"],
)


# =============================================================================
# JYAO Alpha Format (v2025-11-14)
# =============================================================================

JYAO_V20251114 = SchemaEvolution(
    columns={
        # Symbol column - parse_dtype for CSV, cast_dtype for feather/IPC
        # (feather files have embedded types, so cast is needed post-load)
        "ukey": ColumnSpec(parse_dtype=pl.Int64, cast_dtype=pl.Int64),
        # Quote columns
        "BidPrice1": ColumnSpec(rename_to="bid_px0", parse_dtype=pl.Float64),
        "AskPrice1": ColumnSpec(rename_to="ask_px0", parse_dtype=pl.Float64),
        "BidVolume1": ColumnSpec(
            rename_to="bid_size0",
            parse_dtype=pl.Float64,
            cast_dtype=pl.Int64,
        ),
        "AskVolume1": ColumnSpec(
            rename_to="ask_size0",
            parse_dtype=pl.Float64,
            cast_dtype=pl.Int64,
        ),
        # Time columns
        "TimeStamp": ColumnSpec(rename_to="timestamp", parse_dtype=pl.Int64),
        "GlobalExTime": ColumnSpec(rename_to="global_exchange_ts", parse_dtype=pl.Int64),
        "DataDate": ColumnSpec(rename_to="data_date", parse_dtype=pl.String),
        # Volume
        "Volume": ColumnSpec(
            rename_to="volume",
            parse_dtype=pl.Float64,
            cast_dtype=pl.Int64,
        ),
        # Predictor columns (x_* = alpha predictions)
        # Rule: ≤60s → s, >60s → m
        "x10s": ColumnSpec(rename_to="x_10s", parse_dtype=pl.Float64),
        "x60s": ColumnSpec(rename_to="x_60s", parse_dtype=pl.Float64),
        "alpha1": ColumnSpec(rename_to="x_3m", parse_dtype=pl.Float64),
        "alpha2": ColumnSpec(rename_to="x_30m", parse_dtype=pl.Float64),
    },
    null_values=["", "NA"],
)


# =============================================================================
# Schema Registry
# =============================================================================

SCHEMAS: dict[str, SchemaEvolution] = {
    "ylin_v20251204": YLIN_V20251204,
    "jyao_v20251114": JYAO_V20251114,
}


def get_schema(name: str | None) -> SchemaEvolution | None:
    """Get SchemaEvolution by name.

    Args:
        name: Schema name (e.g., "ylin_v20251204") or None.

    Returns:
        SchemaEvolution or None if name is None or not found.
    """
    if not name:
        return None
    return SCHEMAS.get(name.lower())
