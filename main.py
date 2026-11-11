import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

# Rare mean-reversion bot for the make.fun BTC 24h bars replay.
#
# One symbol (CBBTC), long only, at most one position. The bar interval is one
# minute and a round trip costs roughly 19-26 bps in fees, modelled slippage and
# constant-product price impact, so ordinary bars are not worth trading. The bot
# waits for a rare, sharp drop over a few minutes and buys the snap-back, then
# exits on a fixed take-profit, a tighter stop or a time limit.
#
# The first two batches also send a one-USDC round trip (the minimum notional) so
# the race window always has at least one filled trade even if the strategy never
# fires.
#
# Prices and amounts are integers in the harness units; every comparison is done
# with integers so the bot is deterministic run after run.

SYMBOL = "CBBTC"

# Entry: the close this bar is DROP_BPS below the close LOOKBACK bars back.
LOOKBACK = 3
DROP_BPS = 60

# Exit, measured on the position's value at the latest close against its cost
# (fees included): take profit, stop loss, and a maximum holding time in bars.
TAKE_BPS = 80
STOP_BPS = 50
MAX_HOLD_BARS = 120

# After a stop loss the market is still falling more often than not, so wait a
# few bars before buying another dip instead of re-entering into the same move.
COOLDOWN_BARS = 15

# Fraction of the cash spent on one entry, and the slippage cap. The cap is left
# wide open: the entry filter already demands a large move, and a tight cap
# would only turn fills into rejections.
SIZE_PCT = 50
MAX_SLIPPAGE_BPS = 10000

BPS = 10000
MIN_NOTIONAL = 1_000_000  # 1 USDC in quote units

_closes = []
_held_seen = False
_entry_seq = -1
_last_stop_seq = -1
# The one-USDC probe: 0 = still to buy, 1 = bought and still to sell, 2 = done.
_compliance = 0


def _buy(state, notional):
    notional = min(notional, state.cash, state.weight_room(SYMBOL))
    if notional < MIN_NOTIONAL:
        return None
    return {
        "side": "buy",
        "symbol": SYMBOL,
        "notional_quote_units": notional,
        "max_slippage_bps": MAX_SLIPPAGE_BPS,
    }


def _sell(held):
    return {
        "side": "sell",
        "symbol": SYMBOL,
        "qty": held.qty,
        "max_slippage_bps": MAX_SLIPPAGE_BPS,
    }


def on_batch(state, batch):
    global _held_seen, _entry_seq, _last_stop_seq, _compliance

    bar = None
    for b in batch["bars"]:
        if b["symbol"] == SYMBOL:
            bar = b
    if bar is not None:
        _closes.append(int(bar["c"]))

    seq = batch["seq"]
    held = state.positions.get(SYMBOL)

    # The one-USDC probe: buy it on the first batch that has a bar, sell it as
    # soon as it fills, and retry either leg if the market refuses it (a missing
    # bar at the next open). It guarantees a filled trade on any window.
    if _compliance < 2:
        if _compliance == 0:
            if held is not None:
                _compliance = 1
            elif bar is not None:
                order = _buy(state, MIN_NOTIONAL)
                return [order] if order is not None else []
            else:
                return []
        if _compliance == 1:
            if held is None:
                _compliance = 2
            else:
                return [_sell(held)]

    if held is not None:
        if not _held_seen:
            _held_seen = True
            _entry_seq = seq
        value = state.value(SYMBOL, held.qty)
        take = value * BPS >= held.cost * (BPS + TAKE_BPS)
        stop = value * BPS <= held.cost * (BPS - STOP_BPS)
        old = _entry_seq >= 0 and seq - _entry_seq >= MAX_HOLD_BARS
        if take or stop or old:
            if stop:
                _last_stop_seq = seq
            return [_sell(held)]
        return []

    _held_seen = False
    _entry_seq = -1
    if _last_stop_seq >= 0 and seq - _last_stop_seq < COOLDOWN_BARS:
        return []
    if len(_closes) >= LOOKBACK + 1:
        now = _closes[-1]
        then = _closes[-1 - LOOKBACK]
        if now * BPS < then * (BPS - DROP_BPS):
            notional = state.cash * SIZE_PCT // 100
            order = _buy(state, notional)
            return [order] if order is not None else []
    return []


def main():
    makefun_bars.run(on_batch)


if __name__ == "__main__":
    main()
