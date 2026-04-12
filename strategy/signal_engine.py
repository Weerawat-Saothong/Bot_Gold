import pandas as pd
import numpy as np
import logging
from datetime import datetime, timezone
from config import *
from strategy.global_radar import get_global_market_status

logger = logging.getLogger(__name__)

# ------------------------
# 🧠 ADVANCED FEATURES (SMC & PRICE ACTION)
# ------------------------

def create_features(df):
    if hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(0)

    df.columns = df.columns.str.lower()
    if "volume" not in df.columns: df["volume"] = 1

    # EMAs
    df["ema9"] = df["close"].ewm(span=9).mean()
    df["ema20"] = df["close"].ewm(span=20).mean()
    df["ema50"] = df["close"].ewm(span=50).mean()
    df["ema200"] = df["close"].ewm(span=200).mean()

    # RSI
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + (gain / loss)))

    # ATR
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift()).abs()
    lc = (df["low"] - df["close"].shift()).abs()
    df["atr"] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()

    return df

# ------------------------
# 🦈 PREDATORY SMC DETECTORS
# ------------------------

def detect_fvg(df):
    """ตรวจจับช่องว่างราคา (Fair Value Gap) - พลังงานจากรายใหญ่"""
    if len(df) < 3: return "NONE"
    c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]
    
    # Bullish FVG (Gap ระหว่าง Low ของแท่ง 3 กับ High ของแท่ง 1)
    if c3["low"] > c1["high"]: return "BULL_FVG"
    # Bearish FVG (Gap ระหว่าง High ของแท่ง 3 กับ Low ของแท่ง 1)
    if c3["high"] < c1["low"]: return "BEAR_FVG"
    return "NONE"

def liquidity_sweep(df):
    """ตรวจจับการกวาดสภาพคล่อง (Liquidity Grab) - หลอกกิน SL"""
    lookback = 20
    last, prev = df.iloc[-1], df.iloc[-20:-1]
    
    # แท่งปัจจุบันแทงทะลุยอดเก่าแต่กลับมาปิดข้างใน (Pinbar / Fakeout)
    if last["high"] > prev["high"].max() and last["close"] < prev["high"].max():
        return "SELL_SWEEP"
    if last["low"] < prev["low"].min() and last["close"] > prev["low"].min():
        return "BUY_SWEEP"
    return "NONE"

def session_filter():
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5: return False
    # 04:00 - 06:00 AM Thailand
    if 21 <= now.hour <= 22: return False
    return True

# ------------------------
# 🎫 THE GOLDEN SIGNAL ENGINE
# ------------------------

def get_signal(df, df_htf):
    if df is None or len(df) < 50: return "NONE", "Initializing Data..."
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    last_htf = df_htf.iloc[-1]
    
    # --- 📊 TREND BIAS ---
    trend_up = last["ema50"] > last["ema200"] and last["close"] > last["ema50"]
    trend_down = last["ema50"] < last["ema200"] and last["close"] < last["ema50"]
    htf_up = last_htf["ema50"] > last_htf["ema200"]
    
    # --- 🎯 PATTERNS ---
    fvg = detect_fvg(df)
    sweep = liquidity_sweep(df)
    engulf_up = last["close"] > prev["high"] and last["close"] > last["open"]
    engulf_down = last["close"] < prev["low"] and last["close"] < last["open"]

    if not session_filter(): return "NONE", "Market Closed"

    # --- 🌍 GLOBAL MARKET INSIGHT (Context Only) ---
    radar = get_global_market_status()
    dxy_vibe = radar["dxy_vibe"]
    context = f" [Context: DXY {dxy_vibe}]"

    # 💎 1. INSTITUTIONAL SWEEP (Smart Filter: RSI OS/OB)
    if sweep == "BUY_SWEEP" and last["rsi"] < 45:
        return "BUY", f"Smart Liquidity Sweep (Bullish Reversal){context}"
    if sweep == "SELL_SWEEP" and last["rsi"] > 55:
        return "SELL", f"Smart Liquidity Sweep (Bearish Reversal){context}"

    # 💎 2. SMART MONEY FVG (Smart Filter: HTF Alignment)
    if fvg == "BULL_FVG" and htf_up and last["rsi"] < 65:
        return "BUY", f"Institutional FVG (Trend Alignment){context}"
    if fvg == "BEAR_FVG" and not htf_up and last["rsi"] > 35:
        return "SELL", f"Institutional FVG (Trend Alignment){context}"

    # 💎 3. PULLBACK & REJECTION (Smart Filter: Primary Trend)
    if last["low"] < last["ema20"] and (htf_up or trend_up):
        if engulf_up and last["rsi"] < 60: 
            return "BUY", f"Smart Pullback Rejection{context}"
            
    if last["high"] > last["ema20"] and (not htf_up or trend_down):
        if engulf_down and last["rsi"] > 40:
            return "SELL", f"Smart Pullback Rejection{context}"

    # 💎 4. STRONG TREND PUSH (Smart Filter: Volume Confirmation)
    avg_vol = df["volume"].iloc[-20:].mean()
    if engulf_up and trend_up and last["volume"] > avg_vol * 1.1:
        if last["rsi"] < 70: return "BUY", f"High-Volume Trend Push{context}"
        
    if engulf_down and trend_down and last["volume"] > avg_vol * 1.1:
        if last["rsi"] > 30: return "SELL", f"High-Volume Trend Push{context}"

    return "NONE", "Scanning for High-Probability Institutional Entries..."

    return "NONE", "Hunting for Institutional Entry..."