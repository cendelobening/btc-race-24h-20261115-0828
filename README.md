# btc-race-24h-20261115-0828

[![make.fun · btc-race-24h-20261115-0828](https://make.fun/badge/btc-race-24h-20261115-0828.svg)](https://make.fun/c/btc-race-24h-20261115-0828)
[![rank](https://make.fun/badge/btc-race-24h-20261115-0828/cendelobening/btc-race-24h-20261115-0828/rank.svg)](https://make.fun/c/btc-race-24h-20261115-0828)
[![reward](https://make.fun/badge/btc-race-24h-20261115-0828/cendelobening/btc-race-24h-20261115-0828/reward.svg)](https://make.fun/c/btc-race-24h-20261115-0828)

A capitulation-bounce BTC trading bot for the [make.fun bounty](https://make.fun/c/btc-race-24h-20261115-0828): race a BTC trading bot live for 24 hours. Pure Python 3.13 stdlib, deterministic, no network, no wall clock.

## Strategy

Trade cbBTC/USDC on 1-minute bars, long only, from 1,000 USDC paper money. Stay in cash most of the time; only buy after a sharp selloff, when the market has capitulated and the price is already turning back up:

- **Entry** (on a bar's close, filled at the next bar's open): the close is at least 1.2% below the close 60 minutes ago **and** breaks above the highest close of the previous 10 bars (reversal confirmation — never catch a falling knife blind). A drop of 1.5% or more is deep capitulation: deploy full cash. A 1.2–1.5% drop is moderate: deploy 30%.
- **Exit** (on a bar's close): trailing stop below the highest close since entry — 0.5% on a moderate entry (cut a dud probe fast), 0.8% on a deep entry (let a real bounce run) — a hard stop 0.8% below the entry close, or 240 bars without an exit. No take-profit cap: the trailing stop banks the bounce.
- **Drawdown guard**: if equity falls 5% below the start, stop opening new trades (an open position is still managed to its exit).

## Why this shape

On the published 24h dev window BTC fell ~4% and every house baseline lost money (momentum −$40.92, EMA-cross −$134.95, RSI-Bollinger −$57.37, buy-and-hold −$44.01). One-minute noise is ~12 bps and a full round trip costs ~26 bps in fees, slippage and impact, so frequent trading churns money away. The only moves big enough to pay are the bounces after sharp selloffs — the dev window's biggest was +4.7% in two hours after a −2% hour. This bot waits for exactly those, risks little on the moderate ones, and lets the trailing stop ride the big one.

## Dev result (local replay, exact harness fill math)

| | net PnL | trades | max drawdown |
|---|---|---|---|
| this bot | **+$29.86** | 6 | 1.09% |
| momentum (house) | −$40.92 | 1 | 7.92% |
| ema-cross (house) | −$134.95 | 63 | 13.65% |
| rsi-bollinger (house) | −$57.37 | 12 | 6.77% |
| buy-and-hold (house) | −$44.01 | 1 | 7.92% |

A sensitivity sweep over 378 nearby parameter sets kept 92% of them profitable on the dev window (median +$13), so the design does not hang on one tuned number. Walk-forward: first 12h −$2.81 (2 trades), second 12h +$30.96 (4 trades) — the profit comes from the bounce leg, the quiet half costs almost nothing.

## Run it

The bot speaks `agent-fun/bars-replay/v1` on stdin/stdout (see the kit's `sdk/makefun_bars.py`, vendored byte-identical under `vendor/`):

```sh
python3 main.py
```

Grade locally with the kit (needs Docker for the Python runtime; the process driver runs Node only):

```sh
node cli/makefun.mjs grade-local --kit <kit> --bot . --driver docker
```
