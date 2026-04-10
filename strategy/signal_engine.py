import pandas as pd
import logging
from datetime import datetime, timezone
from config import *

logger = logging.getLogger(__name__)

# ------------------------
# CREATE FEATURES
# ------------------------

def create_features(df):
    if hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(0)

    df.columns = df.columns.str.lower()

    if "volume" not in df.columns:
        df["volume"] = 1

    # EMA
    df["ema9"] = df["close"].ewm(span=9).mean()
    df["ema20"] = df["close"].ewm(span=20).mean()
    df["ema50"] = df["close"].ewm(span=50).mean()
    df["ema200"] = df["close"].ewm(span=200).mean()

    # RSI
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    
    rs = avg_gain / avg_loss
    df["rsi"] = 100 - (100 / (1 + rs))

    # ATR (Volatility)
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    df["atr"] = true_range.rolling(14).mean()

    return df

# ------------------------
# FILTERS & HELPERS
# ------------------------

def session_filter():
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5: return False
    if 21 <= now.hour <= 22: return False
    return True

def breakout_detection(df):
    last = df.iloc[-1]
    high_20 = df["high"].iloc[-20:-1].max()
    low_20 = df["low"].iloc[-20:-1].min()
    if last["close"] > high_20: return "BREAKOUT_BUY"
    if last["close"] < low_20: return "BREAKOUT_SELL"
    return "NONE"

def liquidity_sweep(df):
    last = df.iloc[-1]
    high_lookback = df["high"].iloc[-20:-1].max()
    low_lookback = df["low"].iloc[-20:-1].min()
    if last["high"] > high_lookback and last["close"] < high_lookback: return "SELL_SWEEP"
    if last["low"] < low_lookback and last["close"] > low_lookback: return "BUY_SWEEP"
    return "NONE"

def detect_fvg(df):
    if len(df) < 3: return "NONE", 0, 0
    p1, p3 = df.iloc[-3], df.iloc[-1]
    if p3["low"] > p1["high"]: return "BULL_FVG", p1["high"], p3["low"]
    if p3["high"] < p1["low"]: return "BEAR_FVG", p3["high"], p1["low"]
    return "NONE", 0, 0

def detect_rejection(df):
    last = df.iloc[-1]
    body = abs(last["close"] - last["open"])
    upper_wick = last["high"] - max(last["open"], last["close"])
    lower_wick = min(last["open"], last["close"]) - last["low"]
    atr = last["atr"]
    if atr == 0: return "NONE"
    if upper_wick > (body * 2) and upper_wick > (atr * 0.5): return "BEAR_REJECT"
    if lower_wick > (body * 2) and lower_wick > (atr * 0.5): return "BULL_REJECT"
    return "NONE"

# ------------------------
# MAIN SIGNAL ENGINE
# ------------------------

def get_signal(df, df_htf):
    if len(df) < 50: return "NONE", "Insufficient data"

    last, prev = df.iloc[-1], df.iloc[-2]
    last_htf = df_htf.iloc[-1]
    
    # 🧪 ADVANCED ANALYTICS
    avg_vol = df["volume"].iloc[-20:-1].mean()
    vol_spike = last["volume"] > (avg_vol * 1.5)
    fvg_type, _, _ = detect_fvg(df)
    reject_type = detect_rejection(df)
    
    # TRENDS
    trend_up = last["ema50"] > last["ema200"] and last["ema9"] > last["ema50"]
    trend_down = last["ema50"] < last["ema200"] and last["ema9"] < last["ema50"]
    htf_up = last_htf["ema50"] > last_htf["ema200"]
    htf_down = last_htf["ema50"] < last_htf["ema200"]

    breakout = breakout_detection(df)
    sweep = liquidity_sweep(df)
    mom_up = last["high"] > prev["high"] and last["close"] > prev["high"]
    mom_down = last["low"] < prev["low"] and last["close"] < prev["low"]

    # --- 🦈 PREDATORY LOGIC (ปรับให้เจอโอกาสง่ายขึ้น แล้วส่งให้สภากรอง) ---
    if not session_filter(): return "NONE", "Market Closed"

    # 1. Sweep + Reject (High Quality)
    if htf_up and sweep == "BUY_SWEEP":
        return "BUY", "Institutional Sweep Setup (BUY)"
    if htf_down and sweep == "SELL_SWEEP":
        return "SELL", "Institutional Sweep Setup (SELL)"

    # 2. Strong Momentum + Trend Alignment
    if trend_up and htf_up and mom_up:
        if reject_type == "BULL_REJECT" or (last["close"] > prev["high"] and last["volume"] > avg_vol):
            return "BUY", "Strong Trend Continuation (BUY)"
            
    if trend_down and htf_down and mom_down:
        if reject_type == "BEAR_REJECT" or (last["close"] < prev["low"] and last["volume"] > avg_vol):
            return "SELL", "Strong Trend Continuation (SELL)"

    # 3. Safe Pullback (ย่อซื้อ-เด้งขาย)
    if htf_up and last["ema9"] > last["ema50"] and last["rsi"] < 45:
        if reject_type == "BULL_REJECT" or mom_up:
            return "BUY", "Deep Pullback in Uptrend (BUY)"
            
    if htf_down and last["ema9"] < last["ema50"] and last["rsi"] > 55:
        if reject_type == "BEAR_REJECT" or mom_down:
            return "SELL", "High Pullback in Downtrend (SELL)"

    return "NONE", "Hunting for better entry..."

# Legacy function stubs for compatibility
def market_structure(df): return "NONE"
def is_overextended(p, e, a, d): return False
def check_trend_safety(df): return "SAFE", 0.0
def check_flash_crash(df): return "SAFE"