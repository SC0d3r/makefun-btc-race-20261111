# btc-race-24h-entry

A long-only Python bot for make.fun's `agent-fun/bars-replay/v1` bars replay of
CBBTC/USDC one-minute bars.

## Strategy

A full round trip costs roughly 19-26 bps in fees, modelled slippage and
constant-product price impact, so the bot trades rarely. It buys after a sharp
drop over a few bars (mean reversion on the snap-back) and exits on a fixed
take profit, a tighter stop loss or a maximum holding time. A one-USDC
minimum-notional round trip on the first two batches guarantees at least one
filled trade on any window.

The bot is deterministic: no clock, no network, no randomness.

## Layout

- `main.py` - entrypoint and strategy
- `vendor/makefun_bars.py` - byte-identical copy of the kit's Python SDK shim
- `LICENSE` - MIT

## Run

The grader runs:

```
python3 -P -s /bot/main.py
```

Locally, from the unpacked kit:

```
node cli/makefun.mjs grade-local --kit . --bot /path/to/btc-race-24h-entry --driver process --json
```
