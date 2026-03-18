import pandas as pd
from datetime import datetime, timezone
from config import *


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

    # ATR
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()

    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()

    df = df.dropna()

    return df


# ------------------------
# SESSION FILTER
# ------------------------

def session_filter():

    now = datetime.now(timezone.utc)

    hour = now.hour
    day = now.weekday()

    if day >= 5:
        return False

    return True


# ------------------------
# MARKET STRUCTURE
# ------------------------

def market_structure(df):

    highs = df["high"].iloc[-MARKET_STRUCTURE_PERIOD:]
    lows = df["low"].iloc[-MARKET_STRUCTURE_PERIOD:]

    if highs.iloc[-1] > highs.iloc[-2] and lows.iloc[-1] > lows.iloc[-2]:
        return "HH"

    if highs.iloc[-1] < highs.iloc[-2] and lows.iloc[-1] < lows.iloc[-2]:
        return "LL"

    if highs.iloc[-1] < highs.iloc[-2] and lows.iloc[-1] > lows.iloc[-2]:
        return "HL"

    if highs.iloc[-1] > highs.iloc[-2] and lows.iloc[-1] < lows.iloc[-2]:
        return "LH"

    return "RANGE"


# ------------------------
# TREND STRENGTH
# ------------------------

def trend_strength_filter(df, period=200):
    last = df.iloc[-1]
    strength = abs(last["ema50"] - last["ema200"])
    if strength < 0.2:
        return False, "RANGE"
    return True, "TRENDING"


# ------------------------
# LIQUIDITY SWEEP
# ------------------------

def liquidity_sweep(df):

    last = df.iloc[-1]

    recent_high = df["high"].iloc[-(LIQUIDITY_LOOKBACK+1):-1].max()
    recent_low = df["low"].iloc[-(LIQUIDITY_LOOKBACK+1):-1].min()

    if last["high"] > recent_high and last["close"] < recent_high:
        return "SELL_SWEEP"

    if last["low"] < recent_low and last["close"] > recent_low:
        return "BUY_SWEEP"

    return None


# ------------------------
# BREAKOUT
# ------------------------

def breakout_detection(df):

    last = df.iloc[-1]

    recent_high = df["high"].iloc[-(LIQUIDITY_LOOKBACK+1):-1].max()
    recent_low = df["low"].iloc[-(LIQUIDITY_LOOKBACK+1):-1].min()

    if last["close"] > recent_high:
        return "BREAKOUT_BUY"

    if last["close"] < recent_low:
        return "BREAKOUT_SELL"

    return None


# ------------------------
# FAKE BREAKOUT
# ------------------------

def fake_breakout(df):

    last = df.iloc[-1]
    prev = df.iloc[-2]

    recent_high = df["high"].iloc[-(LIQUIDITY_LOOKBACK+1):-1].max()
    recent_low = df["low"].iloc[-(LIQUIDITY_LOOKBACK+1):-1].min()

    if prev["close"] > recent_high and last["close"] < recent_high:
        return "FAKE_BUY"

    if prev["close"] < recent_low and last["close"] > recent_low:
        return "FAKE_SELL"

    return None


# ------------------------
# RANGE FILTER
# ------------------------

def range_filter(df):

    last = df.iloc[-1]

    candle_range = last["high"] - last["low"]

    if candle_range > CANDLE_RANGE_THRESHOLD:
        return False

    return True


def distance_filter(df):

    if len(df) < 5: return True
    last = df.iloc[-1]["close"]
    prev = df.iloc[-5]["close"]

    if abs(last - prev) < MIN_DISTANCE_FOR_SIGNAL:
        return False

    return True


# ------------------------
# VOLATILITY EXPANSION
# ------------------------

def volatility_expansion(df):

    atr_now = df["atr"].iloc[-1]
    atr_prev = df["atr"].iloc[-5:-1].mean()

    # Optimized for more entries
    if atr_now > atr_prev * 1.05 or atr_now > ATR_MIN_VOLATILITY:
        return True

    return False

def check_pullback(df, trend="UP"):
    last = df.iloc[-1]
    # Price near EMA20 or EMA50 (within 0.3 ATR)
    atr = last["atr"]
    dist_20 = abs(last["close"] - last["ema20"])
    dist_50 = abs(last["close"] - last["ema50"])
    
    if trend == "UP":
        if last["close"] > last["ema20"] and dist_20 < atr * 0.4:
            return True, "EMA20 Pullback"
        if last["close"] > last["ema50"] and dist_50 < atr * 0.4:
            return True, "EMA50 Pullback"
    else:
        if last["close"] < last["ema20"] and dist_20 < atr * 0.4:
            return True, "EMA20 Pullback"
        if last["close"] < last["ema50"] and dist_50 < atr * 0.4:
            return True, "EMA50 Pullback"
            
    return False, None


# ------------------------
# SIGNAL ENGINE
# ------------------------

# ------------------------
# BLACK SWAN (MOMENTUM) SIGNAL
# ------------------------
def get_black_swan_signal(df):
    if not ENABLE_BLACK_SWAN:
        return "NONE"

    last = df.iloc[-1]
    atr = last["atr"]
    rsi = last["rsi"]
    
    # คำนวณค่าเฉลี่ย Volume ย้อนหลัง 14 แท่ง
    avg_volume = df["volume"].iloc[-15:-1].mean()
    current_volume = last["volume"]

    # ต้องมีความผันผวนระดับพายุลูกใหญ่
    if atr < BLACK_SWAN_ATR_MIN:
        return "NONE"
        
    # ต้องมีปริมาณซื้อขายหนาแน่น (ป้องกันรายย่อยสับหลอก)
    if current_volume < (avg_volume * 1.5):
        return "NONE"

    # ทุบสุดแรง
    if rsi < BLACK_SWAN_RSI_SELL:
        return "SELL_SWAN"
    
    # ลากสุดแรง
    if rsi > BLACK_SWAN_RSI_BUY:
        return "BUY_SWAN"

    return "NONE"

def get_signal(df, df_htf):

    if len(df) < 50 or len(df_htf) < 50:
        return "NONE", "Insufficient data (need 50+ candles)"

    prev = df.iloc[-2]
    last = df.iloc[-1]
    last_htf = df_htf.iloc[-1]

    rsi = last["rsi"]
    atr = last["atr"]

    # 1. TIME FILTER (Broker Time)
    if "datetime" in last:
        current_hour = last["datetime"].hour
    else:
        current_hour = datetime.now().hour

    if not (TRADE_START_HOUR <= current_hour <= TRADE_END_HOUR):
        return "NONE", f"Outside trading hours ({current_hour}:00)"

    # 2. BLACK SWAN EMERGENCY OVERRIDE
    swan_signal = get_black_swan_signal(df)
    if swan_signal != "NONE":
        return swan_signal, f"Black Swan Event Detected (ATR: {round(atr,2)}, RSI: {round(rsi,2)})"

    # 3. NORMAL VOLATILITY LIMIT
    if atr > MAX_ATR_LIMIT:
        return "NONE", f"High volatility (ATR: {round(atr,2)} > {MAX_ATR_LIMIT})"

    # LTF TREND
    trend_up = last["ema50"] > last["ema200"]
    trend_down = last["ema50"] < last["ema200"]

    # HTF TREND & STRENGTH (กล้องส่องทางไกล)
    htf_ok, htf_mode = trend_strength_filter(df_htf)
    htf_up = last_htf["ema50"] > last_htf["ema200"]
    htf_down = last_htf["ema50"] < last_htf["ema200"]

    # PATTERN DETECTION
    structure = market_structure(df)
    breakout = breakout_detection(df)
    sweep = liquidity_sweep(df)

    momentum_up = last["high"] > prev["high"]
    momentum_down = last["low"] < prev["low"]

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
        # Relaxed: Only check if ATR is extremely low
        if atr < 0.5:
            return "NONE", "No volatility expansion detected"

    # SIGNAL GENERATION
    # 1. LIQUIDITY SWEEP (High Priority)
    if trend_up and sweep == "BUY_SWEEP" and momentum_up and rsi < RSI_BUY_MAX:
        return "BUY", "Liquidity Sweep Buy"
    if trend_down and sweep == "SELL_SWEEP" and momentum_down and rsi > RSI_SELL_MIN:
        return "SELL", "Liquidity Sweep Sell"

    # 2. PULLBACK & STRUCTURE (Relaxed HTF)
    # Allow BUY if HTF is UP OR HTF is RANGE
    if trend_up and (htf_up or htf_mode == "RANGE"):
        pb_ok, pb_msg = check_pullback(df, "UP")
        if pb_ok and momentum_up and rsi < 75:
            return "BUY", pb_msg
            
        if structure == "HL" and RSI_BUY_MIN <= rsi <= RSI_BUY_MAX and momentum_up:
            return "BUY", "Trend HL Buy"

        if breakout == "BREAKOUT_BUY" and rsi <= RSI_BUY_MAX and momentum_up:
            return "BUY", "Breakout Buy"

    # Allow SELL if HTF is DOWN OR HTF is RANGE
    if trend_down and (htf_down or htf_mode == "RANGE"):
        pb_ok, pb_msg = check_pullback(df, "DOWN")
        if pb_ok and momentum_down and rsi > RSI_SELL_MIN:
            return "SELL", pb_msg

        if structure == "LH" and RSI_SELL_MIN <= rsi <= RSI_SELL_MAX and momentum_down:
            return "SELL", "Trend LH Sell"

        if breakout == "BREAKOUT_SELL" and rsi >= RSI_SELL_MIN and momentum_down:
            return "SELL", "Breakout Sell"

    return "NONE", "No trade patterns identified"