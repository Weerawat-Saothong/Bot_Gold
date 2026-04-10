import logging
from config import *

logger = logging.getLogger(__name__)

def find_last_swing_low(df, min_confirm=3):
    """หาฐานแนวรับล่าสุดที่แข็งแกร่ง (Strong Support)"""
    for i in range(len(df) - min_confirm - 1, 10, -1):
        if (df["low"].iloc[i] < df["low"].iloc[i-1] and 
            df["low"].iloc[i] < df["low"].iloc[i+1] and
            df["low"].iloc[i] < df["low"].iloc[i-2]): # คอนเฟิร์มเพิ่มเป็น 2 แท่ง
            return df["low"].iloc[i]
    return df["low"].iloc[-10:-1].min()

def find_last_swing_high(df, min_confirm=3):
    """หาฐานแนวต้านล่าสุดที่แข็งแกร่ง (Strong Resistance)"""
    for i in range(len(df) - min_confirm - 1, 10, -1):
        if (df["high"].iloc[i] > df["high"].iloc[i-1] and 
            df["high"].iloc[i] > df["high"].iloc[i+1] and
            df["high"].iloc[i] > df["high"].iloc[i-2]):
            return df["high"].iloc[i]
    return df["high"].iloc[-10:-1].max()

def calculate_sl_tp(df, signal, price, ai_sl=None, ai_tp=None):
    """
    คำนวณ SL/TP ระดับมหาเทพ (Predatory Risk Management)
    - SL: วางใต้/เหนือแนวรับแนวต้านจริง + ระยะเผื่อ ATR_SL_BUFFER
    - TP: เป้าหมายขั้นต่ำ 1:2 หรือสูงกว่าตามที่สภาเทพแนะนำ
    """
    last = df.iloc[-1]
    atr = df["atr"].iloc[-5:].mean() # Smoothed ATR
    
    if atr <= 0: atr = 1.0 # Safety fallback
    
    buffer = atr * ATR_SL_BUFFER
    
    # 🕵️‍♂️ ประเมิน AI suggested values
    if ai_sl and ai_tp:
        try:
            ai_sl, ai_tp = float(ai_sl), float(ai_tp)
            # ตรวจสอบความสมเหตุสมผลของ AI SL/TP
            if signal == "BUY" and ai_sl < price and ai_tp > price:
                return round(ai_sl, 3), round(ai_tp, 3)
            if signal == "SELL" and ai_sl > price and ai_tp < price:
                return round(ai_sl, 3), round(ai_tp, 3)
        except: pass

    # 🏹 Technical Calculation (Fallback/Validation)
    swing_low = find_last_swing_low(df)
    swing_high = find_last_swing_high(df)

    if signal == "BUY":
        sl = min(swing_low - buffer, price - (atr * 1.5)) # เอาค่าที่ปลอดภัยกว่า
        risk = price - sl
        if risk < MIN_SL_DISTANCE:
            sl = price - MIN_SL_DISTANCE
            risk = MIN_SL_DISTANCE
        
        tp = price + (risk * RR_RATIO) # เป้าหมายขั้นต่ำตาม RR_RATIO
        
    elif signal == "SELL":
        sl = max(swing_high + buffer, price + (atr * 1.5))
        risk = sl - price
        if risk < MIN_SL_DISTANCE:
            sl = price + MIN_SL_DISTANCE
            risk = MIN_SL_DISTANCE
            
        tp = price - (risk * RR_RATIO)
    else:
        return None, None

    logger.info(f"🛡️ [Risk Engine] Calculated SL: {sl:.2f} | TP: {tp:.2f} (Risk: {risk:.2f})")
    return round(sl, 3), round(tp, 3)

def apply_risk_management(position, current_price):
    """
    เลื่อนหน้าทุน (Breakeven) อัตโนมัติ ปกป้องเงินทุนบอส
    """
    if not USE_BREAKEVEN: return position['sl']

    entry = position['entry']
    sl = position['sl']
    pnl = (current_price - entry) if position['type'] == 'BUY' else (entry - current_price)
    
    # ถ้ากำไรถึงจุดที่กำหนด และยังไม่ได้เลื่อนหน้าทุน
    if pnl >= BREAKEVEN_START:
        if position['type'] == 'BUY' and sl < entry:
            new_sl = entry + BREAKEVEN_PROFIT
            logger.info(f"🛸 [BE] BUY Position Protected! Moving SL to {new_sl}")
            return round(new_sl, 3)
        elif position['type'] == 'SELL' and sl > entry:
            new_sl = entry - BREAKEVEN_PROFIT
            logger.info(f"🛸 [BE] SELL Position Protected! Moving SL to {new_sl}")
            return round(new_sl, 3)
            
    return sl
