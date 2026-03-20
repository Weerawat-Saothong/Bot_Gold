from config import *

def find_last_swing_low(df):
    for i in range(len(df)-3, 2, -1):
        if (
            df["low"].iloc[i] < df["low"].iloc[i-1]
            and df["low"].iloc[i] < df["low"].iloc[i+1]
        ):
            return df["low"].iloc[i]
    return df["low"].iloc[-2]


def find_last_swing_high(df):
    for i in range(len(df)-3, 2, -1):
        if (
            df["high"].iloc[i] > df["high"].iloc[i-1]
            and df["high"].iloc[i] > df["high"].iloc[i+1]
        ):
            return df["high"].iloc[i]
    return df["high"].iloc[-2]


def calculate_sl_tp(df, signal, price):
    last = df.iloc[-1]
    atr = last["atr"]

    swing_low = find_last_swing_low(df)
    swing_high = find_last_swing_high(df)

    atr_buffer = atr * 0.5
    rr = 2

    min_risk = atr * 0.3

    if signal == "BUY":
        sl = swing_low - atr_buffer
        risk = price - sl
        if sl >= price: return None, None
        if risk < min_risk: return None, None
        tp = price + risk * rr

    elif signal == "SELL":
        sl = swing_high + atr_buffer
        risk = sl - price
        if sl <= price: return None, None
        if risk < min_risk: return None, None
        tp = price - risk * rr

    else:
        return None, None

    return round(sl,3), round(tp,3)


# 🔥 EA Logic: Trailing & Breakeven
def apply_risk_management(position, current_price):
    """
    เลื่อน SL ตาม Logic EA (Trailing Start/Step & Breakeven)
    """
    # Import inside to avoid circular imports
    from config import (
        TRAILING_START, TRAILING_STEP, BREAKEVEN_START,
        USE_TRAILING_STOP, USE_BREAKEVEN
    )
    
    sl = position['sl']
    entry = position['entry']
    type = position['type']
    
    if type == 'BUY':
        profit = current_price - entry
        
        # 1. Breakeven
        if USE_BREAKEVEN and profit >= BREAKEVEN_START and sl < entry:
            sl = entry + 1.0 # ล็อกกำไร 1.0 เหรียญ
            
        # 2. Trailing Stop
        if USE_TRAILING_STOP and profit >= TRAILING_START:
            potential_sl = current_price - TRAILING_START
            if potential_sl > sl + TRAILING_STEP:
                sl = potential_sl
                
    elif type == 'SELL':
        profit = entry - current_price
        
        # 1. Breakeven
        if USE_BREAKEVEN and profit >= BREAKEVEN_START and sl > entry:
            sl = entry - 0.1
            
        # 2. Trailing Stop
        if USE_TRAILING_STOP and profit >= TRAILING_START:
            potential_sl = current_price + TRAILING_START
            if potential_sl < sl - TRAILING_STEP:
                sl = potential_sl
                
    return round(sl, 3)
