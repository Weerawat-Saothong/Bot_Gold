import logging
from config import *

logger = logging.getLogger(__name__)


def find_last_swing_low(df, min_confirm=3):
    """หา Swing Low ที่ยืนยันแล้ว (ห่างจากแท่งปัจจุบันอย่างน้อย min_confirm แท่ง)"""
    for i in range(len(df) - min_confirm - 1, 2, -1):
        if (
            df["low"].iloc[i] < df["low"].iloc[i-1]
            and df["low"].iloc[i] < df["low"].iloc[i+1]
        ):
            return df["low"].iloc[i]
    # Fallback: ใช้ค่าต่ำสุดของ 5 แท่งก่อนหน้า (ไม่รวมแท่งปัจจุบัน)
    return df["low"].iloc[-5:-1].min()


def find_last_swing_high(df, min_confirm=3):
    """หา Swing High ที่ยืนยันแล้ว (ห่างจากแท่งปัจจุบันอย่างน้อย min_confirm แท่ง)"""
    for i in range(len(df) - min_confirm - 1, 2, -1):
        if (
            df["high"].iloc[i] > df["high"].iloc[i-1]
            and df["high"].iloc[i] > df["high"].iloc[i+1]
        ):
            return df["high"].iloc[i]
    # Fallback: ใช้ค่าสูงสุดของ 5 แท่งก่อนหน้า
    return df["high"].iloc[-5:-1].max()


def get_smoothed_atr(df, periods=5):
    """ใช้ ATR เฉลี่ยจากหลายแท่ง ไม่ใช่แท่งเดียว → ลดความสั่นไหว"""
    return df["atr"].iloc[-periods:].mean()


def calculate_sl_tp(df, signal, price, ai_sl=None, ai_tp=None):
    """
    คำนวณ SL/TP แบบ Dynamic (ปรับปรุงใหม่)
    
    การปรับปรุง:
    1. ใช้ Smoothed ATR (ค่าเฉลี่ย 5 แท่ง) แทน ATR แท่งเดียว → ลดการสั่น
    2. ใช้ Confirmed Swing Level (ห่างอย่างน้อย 3 แท่ง) → ไม่กระโดดตาม noise
    3. รับค่า AI-suggested SL/TP เป็น optional → AI ช่วยตัดสินใจ
    4. มี min/max clamp → ป้องกันค่าบ้าๆ
    """
    last = df.iloc[-1]
    atr = get_smoothed_atr(df)  # ← ใช้ smoothed ATR แทนค่าปัจจุบัน

    # Safety: ถ้า ATR = 0 ให้ fallback
    if atr <= 0:
        atr = last["atr"]
    if atr <= 0:
        return None, None

    # Clamp limits (ป้องกัน SL ใกล้/ไกลเกินไป)
    min_sl_distance = max(atr * 0.3, MIN_SL_DISTANCE)
    max_sl_distance = atr * 6.0

    rr = 1.5
    atr_buffer = atr * 0.5

    # =============================================
    # ลองใช้ AI SL/TP ก่อน (ถ้ามีและถูกต้อง)
    # =============================================
    if ai_sl is not None and ai_tp is not None:
        try:
            ai_sl = float(ai_sl)
            ai_tp = float(ai_tp)

            if signal == "BUY":
                sl_dist = price - ai_sl
                tp_dist = ai_tp - price
                if min_sl_distance <= sl_dist <= max_sl_distance and tp_dist > 0:
                    logger.info(f" AI SL/TP accepted: SL={ai_sl:.2f}, TP={ai_tp:.2f} (SL dist={sl_dist:.2f}, TP dist={tp_dist:.2f})")
                    return round(ai_sl, 3), round(ai_tp, 3)

            elif signal == "SELL":
                sl_dist = ai_sl - price
                tp_dist = price - ai_tp
                if min_sl_distance <= sl_dist <= max_sl_distance and tp_dist > 0:
                    logger.info(f" AI SL/TP accepted: SL={ai_sl:.2f}, TP={ai_tp:.2f} (SL dist={sl_dist:.2f}, TP dist={tp_dist:.2f})")
                    return round(ai_sl, 3), round(ai_tp, 3)

            logger.warning(f" AI SL/TP invalid (sl={ai_sl}, tp={ai_tp}, price={price}), falling back to technical")
        except (ValueError, TypeError) as e:
            logger.warning(f" AI SL/TP parse error: {e}, falling back to technical")

    # =============================================
    # Fallback: Technical Calculation (Improved)
    # =============================================
    swing_low = find_last_swing_low(df, min_confirm=3)
    swing_high = find_last_swing_high(df, min_confirm=3)

    if signal == "BUY":
        sl = swing_low - atr_buffer
        risk = price - sl

        # Clamp: ถ้า SL ใกล้เกิน → ดันออก
        if risk < min_sl_distance:
            sl = price - min_sl_distance
            risk = min_sl_distance
        # Clamp: ถ้า SL ไกลเกิน → ดึงเข้า
        elif risk > max_sl_distance:
            sl = price - max_sl_distance
            risk = max_sl_distance

        if sl >= price:
            return None, None

        tp = price + risk * rr

    elif signal == "SELL":
        sl = swing_high + atr_buffer
        risk = sl - price

        if risk < min_sl_distance:
            sl = price + min_sl_distance
            risk = min_sl_distance
        elif risk > max_sl_distance:
            sl = price + max_sl_distance
            risk = max_sl_distance

        if sl <= price:
            return None, None

        tp = price - risk * rr

    else:
        return None, None

    logger.info(f" Technical SL/TP: SL={sl:.2f}, TP={tp:.2f} (ATR_smooth={atr:.2f}, buffer={atr_buffer:.2f})")
    return round(sl, 3), round(tp, 3)


# EA Logic: Trailing & Breakeven
def apply_risk_management(position, current_price):
    """
    เลื่อน SL ตาม Logic EA (Trailing Start/Step & Breakeven)
    """
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
            sl = entry + 1.0  # ล็อกกำไร 1.0 เหรียญ

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
