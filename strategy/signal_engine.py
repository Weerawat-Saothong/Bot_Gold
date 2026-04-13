import pandas as pd
import numpy as np
import logging
from datetime import datetime, timezone
from config import *
from strategy.global_radar import get_global_market_status
from strategy.sentiment_radar import get_market_sentiment

logger = logging.getLogger(__name__)

# ------------------------
# 🧠 ADVANCED FEATURES (SMC + PRICE ACTION)
# ------------------------

def create_features(df):
    if hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(0)
    df.columns = df.columns.str.lower()
    if "volume" not in df.columns: df["volume"] = 1

    df["ema9"]   = df["close"].ewm(span=9).mean()
    df["ema20"]  = df["close"].ewm(span=20).mean()
    df["ema50"]  = df["close"].ewm(span=50).mean()
    df["ema200"] = df["close"].ewm(span=200).mean()

    delta = df["close"].diff()
    gain  = delta.where(delta > 0, 0).rolling(14).mean()
    loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + (gain / loss)))

    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift()).abs()
    lc = (df["low"]  - df["close"].shift()).abs()
    df["atr"] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()

    return df

# ------------------------
# 🦈 SMC DETECTORS (Upgraded)
# ------------------------

def detect_fvg(df):
    """Fair Value Gap — ช่องว่างพลังงานจากรายใหญ่"""
    if len(df) < 3: return "NONE"
    c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]
    if c3["low"] > c1["high"]: return "BULL_FVG"
    if c3["high"] < c1["low"]: return "BEAR_FVG"
    return "NONE"

def liquidity_sweep(df):
    """Liquidity Grab — ไส้หลอกกิน SL รายย่อย"""
    last = df.iloc[-1]
    prev = df.iloc[-20:-1]
    if last["high"] > prev["high"].max() and last["close"] < prev["high"].max():
        return "SELL_SWEEP"
    if last["low"] < prev["low"].min() and last["close"] > prev["low"].min():
        return "BUY_SWEEP"
    return "NONE"

def detect_order_block(df):
    """Order Block — แท่งก่อนการระเบิดตัวของรายใหญ่"""
    if len(df) < 5: return "NONE"
    for i in range(-5, -1):
        candle = df.iloc[i]
        next_candle = df.iloc[i + 1]
        # Bullish OB: แท่งแดงก่อนการดีดขึ้นแรง
        if candle["close"] < candle["open"] and next_candle["close"] > candle["high"]:
            return "BULL_OB"
        # Bearish OB: แท่งเขียวก่อนการดิ่งลงแรง
        if candle["close"] > candle["open"] and next_candle["close"] < candle["low"]:
            return "BEAR_OB"
    return "NONE"

def detect_bos(df):
    """Break of Structure — ยืนยันการเปลี่ยนทิศทาง"""
    if len(df) < 10: return "NONE"
    recent_high = df["high"].iloc[-10:-1].max()
    recent_low  = df["low"].iloc[-10:-1].min()
    last = df.iloc[-1]
    if last["close"] > recent_high: return "BULL_BOS"
    if last["close"] < recent_low:  return "BEAR_BOS"
    return "NONE"

def session_filter():
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5: return False
    if 21 <= now.hour <= 22: return False  # Daily break (00:00–01:00 Thai)
    return True

# ------------------------
# 🎫 GOD-LEVEL SIGNAL ENGINE
# ------------------------

def get_signal(df, df_htf):
    if df is None or len(df) < 50: return "NONE", "Initializing Data..."

    last     = df.iloc[-1]
    prev     = df.iloc[-2]
    last_htf = df_htf.iloc[-1]

    # --- 📊 TREND BIAS ---
    trend_up   = last["ema50"] > last["ema200"] and last["close"] > last["ema50"]
    trend_down = last["ema50"] < last["ema200"] and last["close"] < last["ema50"]
    htf_up     = last_htf["ema50"] > last_htf["ema200"]
    htf_down   = not htf_up

    # --- 🎯 PATTERN DETECTION ---
    fvg      = detect_fvg(df)
    sweep    = liquidity_sweep(df)
    ob       = detect_order_block(df)
    bos      = detect_bos(df)
    engulf_up   = last["close"] > prev["high"] and last["close"] > last["open"]
    engulf_down = last["close"] < prev["low"]  and last["close"] < last["open"]

    if not session_filter(): return "NONE", "Market Closed"

    # --- 🌍 GLOBAL CONTEXT ---
    try:
        radar     = get_global_market_status()
        dxy_vibe  = radar["dxy_vibe"]
        oil_val   = f"{radar['oil_price']:.1f}" if radar["oil_price"] else "N/A"
    except Exception:
        dxy_vibe, oil_val = "NEUTRAL", "N/A"

    # --- 🛰️ SENTIMENT RADAR (Smart Money Positioning) ---
    try:
        sentiment       = get_market_sentiment(df)
        smart_money_dir = sentiment.get("contrarian_bias", "NEUTRAL")  # "BUY", "SELL", "NEUTRAL"
        sentiment_sum   = sentiment.get("summary", "")
    except Exception:
        smart_money_dir, sentiment_sum = "NEUTRAL", ""

    context = f" | DXY:{dxy_vibe} Oil:{oil_val} | {sentiment_sum}"

    rsi = last["rsi"]
    avg_vol = df["volume"].iloc[-20:].mean()

    # ═══ TIER 1: PRIME SETUPS (ส่งทันที — ไม่ต้องรอ Multi-confirm) ═══

    # 🏆 T1-A: Sweep + Reversal (หลอกกิน SL แล้วดีดกลับ)
    if sweep == "BUY_SWEEP"  and rsi < 45: return "BUY",  f"[T1] Liquidity Sweep + Reversal{context}"
    if sweep == "SELL_SWEEP" and rsi > 55: return "SELL", f"[T1] Liquidity Sweep + Reversal{context}"

    # 🏆 T1-B: Order Block + BOS (สถาบันฝาก + ยืนยันทิศทาง)
    if ob == "BULL_OB" and bos == "BULL_BOS": return "BUY",  f"[T1] Order Block + Break of Structure{context}"
    if ob == "BEAR_OB" and bos == "BEAR_BOS": return "SELL", f"[T1] Order Block + Break of Structure{context}"

    # ═══ TIER 2: SMART SETUPS (ต้อง Align กับ HTF) ═══

    # 🥈 T2-A: FVG + HTF
    if fvg == "BULL_FVG" and htf_up   and rsi < 65: return "BUY",  f"[T2] FVG Imbalance (Trend Aligned){context}"
    if fvg == "BEAR_FVG" and htf_down  and rsi > 35: return "SELL", f"[T2] FVG Imbalance (Trend Aligned){context}"

    # 🥈 T2-B: Pullback to EMA + Rejection
    if last["low"] < last["ema20"] and (htf_up or trend_up):
        if engulf_up and rsi < 60: return "BUY", f"[T2] Pullback Rejection at EMA20{context}"
    if last["high"] > last["ema20"] and (htf_down or trend_down):
        if engulf_down and rsi > 40: return "SELL", f"[T2] Pullback Rejection at EMA20{context}"

    # ═══ TIER 3: MOMENTUM SETUPS (ต้องมี Volume ยืนยัน) ═══

    # 🥉 T3-A: Volume Breakout
    if engulf_up   and trend_up   and last["volume"] > avg_vol * 1.2 and rsi < 72:
        return "BUY",  f"[T3] Volume Breakout Momentum{context}"
    if engulf_down and trend_down and last["volume"] > avg_vol * 1.2 and rsi > 28:
        return "SELL", f"[T3] Volume Breakout Momentum{context}"

    return "NONE", "Scanning... No institutional entry found."