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
# SECONDARY FILTERS
# ------------------------

def session_filter():
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5: # Sat/Sun
        return False
    return True

def range_filter(df):
    last = df.iloc[-1]
    candle_range = last["high"] - last["low"]
    return candle_range <= CANDLE_RANGE_THRESHOLD

def distance_filter(df):
    last = df.iloc[-1]
    ema = last["ema50"]
    dist = abs(last["close"] - ema)
    return dist >= MIN_DISTANCE_FOR_SIGNAL

def trend_strength_filter(df):
    last = df.iloc[-1]
    ema50 = last["ema50"]
    ema200 = last["ema200"]
    diff = abs(ema50 - ema200)
    
    if diff > (last["atr"] * 2):
        return True, "STRONG"
    elif diff > (last["atr"] * 0.5):
        return True, "STABLE"
    return False, "RANGE"

def volatility_expansion(df):
    last = df.iloc[-1]
    avg_atr = df["atr"].iloc[-20:-1].mean()
    return last["atr"] > (avg_atr * ATR_VOLATILITY_MULTIPLIER)

# ------------------------
# MARKET STRUCTURE LOGIC
# ------------------------

def market_structure(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    if last["high"] > prev["high"] and last["low"] > prev["low"]:
        return "HH" # Higher High
    if last["high"] < prev["high"] and last["low"] < prev["low"]:
        return "LL" # Lower Low
    if last["high"] < prev["high"] and last["low"] > prev["low"]:
        return "INSIDE"
    
    # Check for swings
    if last["low"] > df["low"].iloc[-5:].min():
        return "HL" # Higher Low
    if last["high"] < df["high"].iloc[-5:].max():
        return "LH" # Lower High
        
    return "NONE"

def breakout_detection(df):
    last = df.iloc[-1]
    high_20 = df["high"].iloc[-20:-1].max()
    low_20 = df["low"].iloc[-20:-1].min()
    
    if last["close"] > high_20:
        return "BREAKOUT_BUY"
    if last["close"] < low_20:
        return "BREAKOUT_SELL"
    return "NONE"

def liquidity_sweep(df):
    last = df.iloc[-1]
    high_lookback = df["high"].iloc[-LIQUIDITY_LOOKBACK:-1].max()
    low_lookback = df["low"].iloc[-LIQUIDITY_LOOKBACK:-1].min()
    
    if last["high"] > high_lookback and last["close"] < high_lookback:
        return "SELL_SWEEP"
    if last["low"] < low_lookback and last["close"] > low_lookback:
        return "BUY_SWEEP"
    return "NONE"

# ------------------------
# SIGNAL STRATEGIES
# ------------------------

def check_pullback(df, trend):
    last = df.iloc[-1]
    ema = last["ema50"]
    rsi = last["rsi"]
    
    if trend == "UP":
        if last["low"] <= ema and last["close"] > ema and rsi < 60:
            return True, "Pullback Buy at EMA50"
    else:
        if last["high"] >= ema and last["close"] < ema and rsi > 40:
            return True, "Pullback Sell at EMA50"
    return False, ""

def get_black_swan_signal(df):
    """
    ตรวจจับความผันผวนรุนแรง (กระชากบ้าคลั่ง)
    """
    if not ENABLE_BLACK_SWAN:
        return "NONE"
        
    last = df.iloc[-1]
    atr = last["atr"]
    rsi = last["rsi"]
    
    # ต้องมีความผันผวนระดับพายุลูกใหญ่
    if atr < BLACK_SWAN_ATR_MIN:
        return "NONE"
    
    # Volume check: ข้ามถ้าไม่มีข้อมูล volume จริง (ทุกค่าเป็น 1)
    avg_volume = df["volume"].iloc[-15:-1].mean()
    current_volume = last["volume"]
    has_real_volume = df["volume"].iloc[-15:].nunique() > 1
    
    if has_real_volume and current_volume < (avg_volume * 1.5):
        return "NONE"

    # ทุบสุดแรง (ขาลง)
    if rsi < BLACK_SWAN_RSI_SELL:
        return "SELL_SWAN"
    
    # ลากสุดแรง (ขาขึ้น)
    if rsi > BLACK_SWAN_RSI_BUY:
        return "BUY_SWAN"

    return "NONE"

def is_overextended(price, ema, atr, direction):
    """
    เช็คว่าราคาห่างจาก EMA มากเกินไปจนมีความเสี่ยงว่าจะดีดกลับหรือไม่
    """
    dist = abs(price - ema)
    limit = atr * MAX_EMA_ATR_DISTANCE
    
    if dist > limit:
        # ถ้าราคาอยู่ต่ำกว่า EMA มากๆ (SELL) แล้วยังจะ SELL ต่อ -> เสี่ยงปลายไส้
        if direction == "SELL" and price < ema:
            return True
        # ถ้าราคาอยู่สูงกว่า EMA มากๆ (BUY) แล้วยังจะ BUY ต่อ -> เสี่ยงยอดดอย
        if direction == "BUY" and price > ema:
            return True
            
    return False

def check_trend_safety(df):
    """
    ตรวจสอบความชันของ EMA50 เพื่อดูว่าเทรนด์แรงเกินไปจนไม่ควรสวนหรือไม่
    """
    if not STRICT_TREND_FILTER:
        return "CLEAR", 0.0

    last = df.iloc[-1]
    prev_5 = df.iloc[-6] # ดูความชันย้อนหลัง 5 แท่ง
    
    ema_now = last["ema50"]
    ema_prev = prev_5["ema50"]
    atr = last["atr"]
    
    if atr == 0: return "CLEAR", 0.0
    
    # คำนวณความชันเทียบกับ ATR (Normalize Slope)
    slope = (ema_now - ema_prev) / atr
    
    if slope > MAX_EMA_SLOPE:
        return "STEEP_UP", slope
    if slope < -MAX_EMA_SLOPE:
        return "STEEP_DOWN", slope
        
    return "STABLE", slope

def get_signal(df, df_htf):
    if len(df) < 50 or len(df_htf) < 50:
        return "NONE", "Insufficient data"

    last = df.iloc[-1]
    prev = df.iloc[-2]
    last_htf = df_htf.iloc[-1]
    
    price = last["close"]
    rsi = last["rsi"]
    atr = last["atr"]

    # TREND ANALYSIS
    trend_up = last["ema50"] > last["ema200"]
    trend_down = last["ema50"] < last["ema200"]
    
    htf_up = last_htf["ema50"] > last_htf["ema200"]
    htf_down = last_htf["ema50"] < last_htf["ema200"]

    # PATTERN DETECTION
    structure = market_structure(df)
    breakout = breakout_detection(df)
    sweep = liquidity_sweep(df)

    momentum_up = last["high"] > prev["high"]
    momentum_down = last["low"] < prev["low"]

    # TREND SAFETY CHECK (Strict Trend Filter)
    trend_state, slope = check_trend_safety(df)

    # PRE-TRADE FILTERS
    if not session_filter():
        return "NONE", "Weekend/Closed session"

    if not range_filter(df):
        return "NONE", "Candle range exceeds threshold"

    if not distance_filter(df):
        return "NONE", "Price distance too small for signal"

    # Relaxed Trend Strength
    _, ltf_mode = trend_strength_filter(df)
    if ltf_mode == "RANGE" and atr < 0.8:
        return "NONE", "Flat range market (ATR < 0.8)"

    if not volatility_expansion(df):
        if atr < 0.5:
            return "NONE", "No volatility expansion detected"

    # BLACK SWAN (High Priority)
    swan = get_black_swan_signal(df)
    if swan != "NONE":
        if swan == "BUY_SWAN":
            if trend_state == "STEEP_DOWN": return "NONE", f"Blocked: Steep Down Trend (Slope: {slope:.2f})"
            return "BUY", "Black Swan Momentum Buy"
        if swan == "SELL_SWAN":
            if trend_state == "STEEP_UP": return "NONE", f"Blocked: Steep Up Trend (Slope: {slope:.2f})"
            return "SELL", "Black Swan Momentum Sell"

    # SIGNAL GENERATION
    # 1. LIQUIDITY SWEEP
    if trend_up and sweep == "BUY_SWEEP" and momentum_up and rsi < RSI_BUY_MAX:
        return "BUY", "Liquidity Sweep Buy"
    if trend_down and sweep == "SELL_SWEEP" and momentum_down and rsi > RSI_SELL_MIN:
        return "SELL", "Liquidity Sweep Sell"

    # 2. PULLBACK & STRUCTURE
    if trend_up and (htf_up or ltf_mode == "RANGE"):
        pb_ok, pb_msg = check_pullback(df, "UP")
        if pb_ok and momentum_up and rsi < 75:
            # Check for Overextended or Steep Down
            if trend_state == "STEEP_DOWN": return "NONE", f"Blocked: Steep Down Trend (Slope: {slope:.2f})"
            if is_overextended(price, last["ema50"], atr, "BUY"): return "NONE", "Blocked: Price Overextended (Buy at top)"
            return "BUY", pb_msg
            
        if structure == "HL" and RSI_BUY_MIN <= rsi <= RSI_BUY_MAX and momentum_up:
            if trend_state == "STEEP_DOWN": return "NONE", f"Blocked: Steep Down Trend (Slope: {slope:.2f})"
            if is_overextended(price, last["ema50"], atr, "BUY"): return "NONE", "Blocked: Price Overextended (Buy at top)"
            return "BUY", "Trend HL Buy"

        if breakout == "BREAKOUT_BUY" and rsi <= RSI_BUY_MAX and momentum_up:
            if trend_state == "STEEP_DOWN": return "NONE", f"Blocked: Steep Down Trend (Slope: {slope:.2f})"
            if is_overextended(price, last["ema50"], atr, "BUY"): return "NONE", "Blocked: Price Overextended (Buy at top)"
            return "BUY", "Breakout Buy"

    if trend_down and (htf_down or ltf_mode == "RANGE"):
        pb_ok, pb_msg = check_pullback(df, "DOWN")
        if pb_ok and momentum_down and rsi > RSI_SELL_MIN:
            # Check for Overextended or Steep Up
            if trend_state == "STEEP_UP": return "NONE", f"Blocked: Steep Up Trend (Slope: {slope:.2f})"
            if is_overextended(price, last["ema50"], atr, "SELL"): return "NONE", "Blocked: Price Overextended (Sell at bottom)"
            return "SELL", pb_msg

        if structure == "LH" and RSI_SELL_MIN <= rsi <= RSI_SELL_MAX and momentum_down:
            if trend_state == "STEEP_UP": return "NONE", f"Blocked: Steep Up Trend (Slope: {slope:.2f})"
            if is_overextended(price, last["ema50"], atr, "SELL"): return "NONE", "Blocked: Price Overextended (Sell at bottom)"
            return "SELL", "Trend LH Sell"

        if breakout == "BREAKOUT_SELL" and rsi >= RSI_SELL_MIN and momentum_down:
            if trend_state == "STEEP_UP": return "NONE", f"Blocked: Steep Up Trend (Slope: {slope:.2f})"
            if is_overextended(price, last["ema50"], atr, "SELL"): return "NONE", "Blocked: Price Overextended (Sell at bottom)"
            return "SELL", "Breakout Sell"

    return "NONE", "No trade patterns identified"