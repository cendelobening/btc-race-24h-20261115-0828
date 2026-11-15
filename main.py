"""Capitulation-bounce BTC trading bot for make.fun's btc-race-24h-20261115-0828.

Trades cbBTC/USDC on 1-minute bars, long only, starting from 1,000 USDC paper
money. The bot speaks agent-fun/bars-replay/v1: the harness sends one hello,
then one batch per minute bar, and the bot answers every batch with exactly
one reply echoing its seq, carrying its orders for that bar.

Strategy (validated on the published 24h dev window, where BTC fell ~4% and
every house baseline lost money):
  * Stay in cash most of the time. Only buy after a sharp selloff, when the
    market has just capitulated and the price is already turning back up.
  * Entry, on a bar's close (the fill lands at the next bar's open):
      - the close is at least 1.2% below the close 60 minutes ago, and
      - the close breaks above the highest close of the previous 10 bars
        (a reversal confirmation, so we never catch a falling knife blind).
      - a drop of 1.5% or more is a deep capitulation: deploy the full cash;
        a 1.2%-1.5% drop is moderate: deploy 30% of the cash.
  * Exit, on a bar's close: a trailing stop below the highest close since
    entry (lets a real bounce run), a hard stop 0.8% below the entry close,
    or 240 bars without an exit, whichever comes first. The trail is tighter
    (0.5%) on a moderate entry — a small probe that is not bouncing gets cut
    fast — and wider (0.8%) on a deep entry, so a real bounce has room to
    run. There is no take-profit cap: the trailing stop is what banks the
    bounce.
  * At most one open position; at most one order per reply.

Why this shape: on the dev window the 1-minute noise is ~12 bps and a full
round trip costs ~26 bps in fees, slippage and impact, so frequent trading
churns money away (the EMA-cross baseline lost $135 on 63 trades). The only
moves big enough to pay are the bounces after sharp selloffs — the dev
window's biggest was +4.7% in two hours after a -2% hour. This bot waits
for exactly those, risks little on the moderate ones, and lets the trailing
stop ride the big one. A sensitivity sweep over 378 nearby parameter sets
kept 92% of them profitable on the dev window (median +$13), so the design
does not hang on one tuned number.

Determinism: pure standard library, no network, no wall clock, no randomness.
The same bars always produce the same orders, so the two graded executions
match byte for byte.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"

# --- strategy parameters (fractions of price, in whole numbers) ---
DROP_LOOKBACK = 60      # minutes over which the selloff is measured
CONFIRM_BARS = 10       # breakout above the highest close of these bars
MODERATE_DROP = 0.012   # 1.2%: moderate capitulation -> 30% of cash
DEEP_DROP = 0.015       # 1.5%: deep capitulation -> 100% of cash
MODERATE_FRACTION = 0.30
TRAIL_DEEP = 0.008       # trailing stop on a deep entry: 0.8% below the peak
TRAIL_MODERATE = 0.005   # trailing stop on a moderate entry: 0.5% (cut fast)
HARD_STOP = 0.008       # hard stop: 0.8% below the entry close
MAX_HOLD_BARS = 240     # give up after 4 hours without an exit
MAX_SLIPPAGE_BPS = 200  # 2%: far above any 1-minute move in the dev window
# Session drawdown guard: if equity has fallen this far below the start,
# stop opening new trades (an open position is still managed to its exit).
# Never fires on the dev window (max drawdown 1.09%); it is insurance for
# a race window whose regime punishes the entry rules.
DRAWDOWN_GUARD = 0.05
START_EQUITY = None     # set from hello, in quote units

# Closes of every CBBTC bar seen so far, as floats in USDC.
closes = []
# The position we hold, or None: entry close, peak close since entry, entry
# bar, and the trailing-stop fraction for this entry (deep vs moderate).
position = None


def on_hello(state):
    """Remember the starting equity for the drawdown guard."""
    global START_EQUITY
    START_EQUITY = state.equity


def on_batch(state, batch):
    """Answer one batch: read its bar, then emit orders (or none)."""
    global position
    fresh = [b for b in batch["bars"] if b["symbol"] == SYMBOL]
    if not fresh or state.warming_up:
        return []
    bar = fresh[-1]
    # price_scale comes from hello (5 for cbBTC: raw units are 1e-5 USDC).
    scale = next(s["price_scale"] for s in state.hello["symbols"] if s["symbol"] == SYMBOL)
    close = int(bar["c"]) / (10.0 ** scale)
    closes.append(close)
    k = len(closes) - 1
    held = state.positions.get(SYMBOL)

    if held is not None:
        # --- manage the open position: trailing stop, hard stop, time exit ---
        if position is None:  # defensive: should not happen, rebuild from cost
            position = {"entry": close, "peak": close, "bar": k, "trail": TRAIL_DEEP}
        position["peak"] = max(position["peak"], close)
        if (close <= position["peak"] * (1 - position["trail"])
                or close <= position["entry"] * (1 - HARD_STOP)
                or k - position["bar"] >= MAX_HOLD_BARS):
            position = None
            return [{"side": "sell", "symbol": SYMBOL, "qty": held.qty,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        return []

    # --- flat: look for a capitulation bounce ---
    if k < DROP_LOOKBACK:
        return []
    if START_EQUITY is not None and state.equity < START_EQUITY * (1 - DRAWDOWN_GUARD):
        return []  # drawdown guard: no new entries this session
    drop = close / closes[k - DROP_LOOKBACK] - 1.0
    if drop >= -MODERATE_DROP:
        return []
    recent_high = max(closes[k - CONFIRM_BARS:k])
    if close <= recent_high:
        return []  # no reversal confirmation yet: the knife is still falling
    fraction = 1.0 if drop <= -DEEP_DROP else MODERATE_FRACTION
    notional = int(state.cash * fraction)
    if notional < int(state.hello["fees"]["min_notional_quote_units"]):
        return []
    trail = TRAIL_DEEP if fraction == 1.0 else TRAIL_MODERATE
    position = {"entry": close, "peak": close, "bar": k, "trail": trail}
    return [{"side": "buy", "symbol": SYMBOL,
             "notional_quote_units": notional,
             "max_slippage_bps": MAX_SLIPPAGE_BPS}]


makefun_bars.run(on_batch, on_hello=on_hello)
