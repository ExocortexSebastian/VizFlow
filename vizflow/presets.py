"""Column mapping presets for VizFlow."""

# ylin's trade format (v2025-12-04)
YLIN_V20251204 = {
    # Order columns (18)
    "symbol": "ukey",
    "orderId": "order_id",
    "orderSide": "order_side",
    "orderQty": "order_qty",
    "orderPrice": "order_price",
    "priceType": "order_price_type",
    "fillQty": "order_filled_qty",
    "fillPrice": "fill_price",
    "lastExchangeTs": "update_exchange_ts",
    "createdTs": "create_exchange_ts",
    "localTs": "create_local_ts",
    "qtyAhead": "qty_ahead",
    "qtyBehind": "qty_behind",
    "orderStatus": "order_curr_state",
    "orderTposType": "order_tpos_type",
    "alphaTs": "alpha_ts",
    "event": "event_type",
    "cumFilledNotional": "order_filled_notional",
    # Quote columns (15)
    "bid": "bid_px0",
    "bid2": "bid_px1",
    "bid3": "bid_px2",
    "bid4": "bid_px3",
    "bid5": "bid_px4",
    "ask": "ask_px0",
    "ask2": "ask_px1",
    "ask3": "ask_px2",
    "ask4": "ask_px3",
    "ask5": "ask_px4",
    "bsize": "bid_size0",
    "bsize2": "bid_size1",
    "bsize3": "bid_size2",
    "bsize4": "bid_size3",
    "bsize5": "bid_size4",
    "asize": "ask_size0",
    "asize2": "ask_size1",
    "asize3": "ask_size2",
    "asize4": "ask_size3",
    "asize5": "ask_size4",
    "isRebasedQuote": "is_rebased",
    "quoteSeqNum": "seq_num",
    "quoteTs": "timestamp",
    # Position columns (11)
    "startPos": "init_net_pos",
    "pos": "current_net_pos",
    "realizedPos": "current_realized_net_pos",
    "openBuyPos": "open_buy",
    "openSellPos": "open_sell",
    "cumBuy": "cum_buy",
    "cumSell": "cum_sell",
    "cashFlow": "cash_flow",
    "frozenCash": "frozen_cash",
    "globalCumBuyNotional": "cum_buy_filled_notional",
    "globalCumSellNotional": "cum_sell_filled_notional",
}

# jyao's alpha format (v2025-11-14)
JYAO_V20251114 = {
    # Quote columns
    "BidPrice1": "bid_px0",
    "AskPrice1": "ask_px0",
    "BidVolume1": "bid_size0",
    "AskVolume1": "ask_size0",
    # Time columns
    "TimeStamp": "timestamp",
    "GlobalExTime": "global_exchange_ts",
    "DataDate": "data_date",
    # Volume
    "Volume": "volume",
    # Predictor columns (x_* = alpha predictions)
    # Rule: ≤60s → s, >60s → m
    "x10s": "x_10s",
    "x60s": "x_60s",
    "alpha1": "x_3m",
    "alpha2": "x_30m",
}

# Preset registry for dynamic lookup
PRESETS: dict[str, dict[str, str]] = {
    "ylin_v20251204": YLIN_V20251204,
    "jyao_v20251114": JYAO_V20251114,
}
