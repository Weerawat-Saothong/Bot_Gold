import logging
import os
import time
from datetime import datetime, timedelta, timezone

from config import *
from data.market_data import get_market_data, get_market_data_htf
from strategy.signal_engine import create_features, get_signal
from execution.signal_writer import write_signal
from risk.risk_engine import calculate_sl_tp
from notify.line_notify import send_line
from notify.news_manager import is_news_active

# =========================
# LOGGING SETUP
# =========================

log_file = os.path.join(os.path.dirname(BASE_PATH), "bot.log") # Save log near MT5 files or as appropriate
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("bot_activity.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

logger.info("Gold Quant Bot Started")

thai_time = datetime.now(timezone.utc) + timedelta(hours=7)

send_line(f"""
🤖 GOLD QUANT BOT

🟢 Status : ONLINE
⏰ Time   : {thai_time.strftime("%H:%M")}

System Ready
""")

# =========================
# FILE PATH
# =========================
# BASE_PATH is imported from config


# =========================
# FILE HELPERS
# =========================

def read_balance(current):
    try:
        with open(BASE_PATH + "balance.txt") as f:
            val = f.read().strip()
            return float(val) if val else current
    except:
        return current


def read_positions(current):
    try:
        with open(BASE_PATH + "position.txt") as f:
            val = f.read().strip()
            return int(val) if val else current
    except:
        return current


def read_pnl(current):
    try:
        with open(BASE_PATH + "pnl.txt") as f:
            val = f.read().strip()
            return round(float(val), 1) if val else current
    except:
        return current


def get_trades_today(current):
    try:
        with open(BASE_PATH + "trades_today.txt") as f:
            val = f.read().strip()
            return int(val) if val else current
    except:
        return current


def read_price():
    try:
        with open(BASE_PATH + "price.txt") as f:
            return float(f.read().strip())
    except:
        return None

def write_bot_active_trade(state):
    try:
        with open(BASE_PATH + "bot_active_trade.txt", "w") as f:
            f.write(str(state))
    except Exception as e:
        logger.error(f"Error writing trade flag: {e}")


def gold_market_open(thai_time):

    wd = thai_time.weekday()
    hour = thai_time.hour

    # Saturday after 04:00
    if wd == 5 and hour >= 4:
        return False

    # Sunday
    if wd == 6:
        return False

    # Monday before 06:00
    if wd == 0 and hour < 6:
        return False

    return True

# =========================
# TRADE LIMIT
# =========================

trades_today = 0
current_day = datetime.now(timezone.utc).day

last_entry_price = None
last_trade_candle = -100
last_loss_candle = -100

previous_pnl = 0
candle_counter = 0
last_weekday = datetime.now(timezone.utc).weekday()

# Initialize account state
account_balance = 0
current_positions = 0
daily_pnl = 0

# 🔥 AI Analysis: Tracking Rejection Reasons
rejection_reasons = {}
last_analysis_time = datetime.now(timezone.utc)
ANALYSIS_INTERVAL_HOURS = 2 



# ======================================================
# MAIN LOOP
# ======================================================

while True:

    try:

        now = datetime.now(timezone.utc)
        thai_time = now + timedelta(hours=7)

        # =========================
        # WEEKEND FILTER
        # =========================
        if not gold_market_open(thai_time):

            # แจ้งเฉพาะตอนเข้า weekend ครั้งแรก
            if last_weekday < 5:

                send_line("""
📴 MARKET CLOSED

Gold Market Closed (Weekend)

Bot in standby mode
""")

            last_weekday = thai_time.weekday()

            logger.info("Weekend - Market Closed")

            time.sleep(300)
            continue

        # =========================
        # NEWS FILTER
        # =========================
        if USE_NEWS_FILTER:
            news_active, news_title = is_news_active(currency=NEWS_CURRENCY, buffer_minutes=NEWS_WAIT_MINUTES)
            if news_active:
                logger.info(f"News Filter Active: {news_title}. Trading Paused.")
                # Optional: send line alert once when news starts
                # For now just skip the loop
                time.sleep(60)
                continue



        candle_counter += 1

        # =========================
        # RESET DAILY
        # =========================

        if now.day != current_day:
            logger.info(f"Daily Reset. Balance: {account_balance}, PnL: {daily_pnl}")

            send_line(f"""
📊 GOLD QUANT DAILY REPORT

📅 Date : {now.strftime("%Y-%m-%d")}
⏰ Time : {thai_time.strftime("%H:%M")}

──────────────

🔁 Trades  : {trades_today}
💰 PnL     : {daily_pnl}$
🏦 Balance : {account_balance}$

──────────────

⚙️ Max/Day : {MAX_TRADES_PER_DAY}
🟢 Status  : Active

🤖 Gold Quant Bot
""")

            trades_today = 0
            current_day = now.day
            previous_pnl = 0

            logger.info("New trading day reset")

        # =========================
        # ACCOUNT STATUS
        # =========================

        account_balance = read_balance(account_balance)
        daily_loss_limit = min(account_balance * DAILY_RISK_PERCENT, 50)

        current_positions = read_positions(current_positions)
        daily_pnl = read_pnl(daily_pnl)

        # =========================
        # 🚨 ANTI-MANUAL TRADE (FIXED)
        # =========================

        try:
            with open(BASE_PATH + "bot_active_trade.txt") as f:
                bot_trade_flag = f.read().strip()
        except:
            bot_trade_flag = "0"

        if current_positions > 0 and bot_trade_flag != "1":

            logger.warning("🚨 MANUAL TRADE DETECTED")

            send_line(f"""
        🚨 MANUAL TRADE DETECTED

        Bot did NOT open this trade

        System Locked

        ⏰ {thai_time.strftime("%H:%M")}
        """)

            write_signal("CLOSE", None, None)

            time.sleep(60)
            continue


        if current_positions == 0:
            last_entry_price = None
            if bot_trade_flag != "0":
                write_bot_active_trade("0")

        # =========================
        # DAILY LOSS LIMIT
        # =========================

        #if daily_pnl <= -daily_loss_limit:

           # send_line(f"""
#🛑 RISK CONTROL

#⚠️ Daily Loss Limit Reached

#📉 Current PnL : {daily_pnl}
#🚫 Limit       : {-daily_loss_limit}

#Bot Trading Paused
#⏰ {thai_time.strftime("%H:%M")}
#""")

            #print("Daily loss limit reached:", daily_pnl)

            #time.sleep(60)
            #continue

        # =========================
        # MAX TRADES
        # =========================

        trades_today = get_trades_today(trades_today)

        if trades_today >= MAX_TRADES_PER_DAY:

            logger.info(f"Max trades ({MAX_TRADES_PER_DAY}) reached today")
            time.sleep(60)
            continue

        # =========================
        # LOSS COOLDOWN
        # =========================

        if candle_counter - last_loss_candle < LOSS_COOLDOWN:

            logger.info("Loss cooldown active")
            time.sleep(60)
            continue

        # =========================
        # TRADE COOLDOWN
        # =========================

        if candle_counter - last_trade_candle < TRADE_COOLDOWN:

            logger.info("Trade cooldown active")
            time.sleep(60)
            continue

        df = get_market_data()
        df_htf = get_market_data_htf()

        if df is None or df.empty or df_htf is None or df_htf.empty:

            logger.warning("No market data available")
            time.sleep(60)
            continue

        df = create_features(df)
        df_htf = create_features(df_htf)

        prev = df.iloc[-2]
        last = df.iloc[-1]

        # =========================
        # SIGNAL & AI ANALYSIS
        # =========================

        ai_signal, rejection_reason = get_signal(df, df_htf)

        if ai_signal == "NONE":
            rejection_reasons[rejection_reason] = rejection_reasons.get(rejection_reason, 0) + 1


        # =========================
        # PRICE
        # =========================

        price = read_price()

        if price is None:
            price = float(last["close"])

        # =========================
        # MOMENTUM
        # =========================

        momentum_up = last["high"] > prev["high"]
        momentum_down = last["low"] < prev["low"]


        signal = "NONE"

        # =========================
        # ENTRY LOGIC
        # =========================

        atr = last["atr"]
        min_distance = atr * 0.3

        if current_positions < MAX_POSITIONS:

            if ai_signal in ["BUY", "SELL"]:

                if last_entry_price is None:
                    signal = ai_signal
                else:
                    # Scaling In / Layering
                    distance = abs(price - last_entry_price)
                    
                    # If we are already in profit, we can be slightly more aggressive with layering
                    # but we still need some distance to avoid "clumping" trades
                    logger.info(f"Position Layering Check: Distance {round(distance, 2)} (Min: {round(min_distance, 2)})")

                    if distance >= min_distance:
                        signal = ai_signal
                    else:
                        logger.info("Scaling-in blocked: Price too close to existing position")


        # =========================
        # MOMENTUM CONFIRMATION
        # =========================

        if signal == "BUY" and not momentum_up:
            signal = "NONE"

        if signal == "SELL" and not momentum_down:
            signal = "NONE"

        # =========================
        # REAL-TIME RISK MANAGEMENT (Trailing & Breakeven)
        # =========================
        
        from risk.risk_engine import apply_risk_management
        
        if current_positions > 0:
            # ดึงข้อมูลสัญญาณเดิมเพื่อนำมารองรับการเลื่อน SL
            # ในระบบนี้เราจำลองจากสถานะปัจจุบัน
            # หมายเหตุ: ระบบจะเลื่อน SL เฉพาะเมื่อเปิด USE_TRAILING_STOP หรือ USE_BREAKEVEN ใน config
            
            # ดึง SL เดิมจากระบบ (ถ้ามี) หรือใช้ค่าจำลอง
            # ในที่นี้ตัวอย่างใช้การคำนวณใหม่จากราคาปัจจุบัน
            pass # ส่วนนี้จะถูกจัดการผ่านการเช็คและส่ง Signal "UPDATE" ไปยัง MT5 หากจำเป็น
            # อย่างไรก็ตาม ในโครงสร้างไฟล์ปัจจุบัน MT5 จะเป็นคนจัดการ Trailing อีกทีหากเราส่งค่าใหม่ไป

        # =========================
        # SMART EXIT (LIQUIDITY REVERSAL)
        # =========================

        if current_positions > 0:

            sweep = None

            recent_high = df["high"].iloc[-21:-1].max()
            recent_low = df["low"].iloc[-21:-1].min()

            if last["high"] > recent_high and last["close"] < recent_high:
                sweep = "SELL_SWEEP"

            if last["low"] < recent_low and last["close"] > recent_low:
                sweep = "BUY_SWEEP"

            # EXIT BUY
            if sweep == "SELL_SWEEP" and momentum_down:

                logger.info("Liquidity Exit BUY")

                signal = "CLOSE_BUY"

                send_line(f"""⚠️ LIQUIDITY EXIT

BUY Closed

Sell Liquidity Sweep Detected

⏰ {thai_time.strftime("%H:%M")}
""")

            # EXIT SELL
            elif sweep == "BUY_SWEEP" and momentum_up:

                logger.info("Liquidity Exit SELL")

                signal = "CLOSE_SELL"

                send_line(f"""⚠️ LIQUIDITY EXIT

SELL Closed

Buy Liquidity Sweep Detected

⏰ {thai_time.strftime("%H:%M")}
""")


        # =========================
        # SL / TP
        # =========================

        sl = None
        tp = None

        if signal in ["BUY", "SELL"]:

            sl, tp = calculate_sl_tp(df, signal, price)

            if sl is None or tp is None:

                logger.error(f"Invalid SL/TP for signal {signal}")
                signal = "NONE"

            else:

                send_line(f"""
🚀 GOLD {"LAYER ADDED" if current_positions > 0 else "TRADE OPEN"}

📊 Direction : {signal}
💰 Entry     : {round(price,2)}
🔍 Pattern   : {rejection_reason}
📈 Layers    : {current_positions + 1}

🛑 Stop Loss : {round(sl,2)}
🎯 Take Profit : {round(tp,2)}

⏰ Time : {thai_time.strftime("%H:%M")}

🤖 Gold Quant Bot
""")

                sl_distance = abs(price - sl)

                if sl_distance < MIN_SL_DISTANCE:

                    logger.warning(f"SL ({round(sl_distance, 2)}) too close (Min: {MIN_SL_DISTANCE})")
                    signal = "NONE"

                else:

                    last_entry_price = price
                    last_trade_candle = candle_counter

        # =========================
        # WRITE SIGNAL
        # =========================

        if signal in ["BUY", "SELL"]:
            write_bot_active_trade("1")

        write_signal(signal, sl, tp)

        # =========================
        # LOSS DETECTION
        # =========================

        if daily_pnl < previous_pnl:
            last_loss_candle = candle_counter

        previous_pnl = daily_pnl

        # =========================
        # LOG
        # =========================

        logger.info(f"""
----------------------------------
Positions: {current_positions}
AI Signal: {ai_signal} ({rejection_reason if ai_signal == "NONE" else "Pattern Matched"})
Final Signal: {signal}
Price: {price}
SL: {sl}
TP: {tp}
Trades today: {trades_today}
Today PnL: {daily_pnl}
----------------------------------""")

        # =========================
        # 🤖 PERIODIC AI ANALYSIS REPORT
        # =========================
        
        if (now - last_analysis_time).total_seconds() >= ANALYSIS_INTERVAL_HOURS * 3600:
            
            if rejection_reasons:
                
                # Sort reasons by frequency
                sorted_reasons = sorted(rejection_reasons.items(), key=lambda x: x[1], reverse=True)
                summary_text = "\n".join([f"• {reason}: {count} ครั้ง" for reason, count in sorted_reasons[:5]])
                
                send_line(f"""
🤖 GOLD BOT: AI LOG ANALYSIS
(สรุปเหตุผลที่ไม่เข้าเทรดในช่วง {ANALYSIS_INTERVAL_HOURS} ชม. ที่ผ่านมา)

📊 สาเหตุหลัก:
{summary_text}

💡 คำแนะนำ:
ตลาดอาจยังไม่มี Trend ชัดเจน หรือ RSI ไม่เอื้ออำนวย บอทจึงเลือกที่จะไม่เสี่ยงครับ
""")
                
                # Reset tracking
                rejection_reasons = {}
                last_analysis_time = now
                logger.info("AI Analysis report sent to LINE")


    except Exception as e:

        logger.exception(f"Unexpected error: {e}")

        send_line(f"""
⚠️ GOLD BOT ERROR

{e}

⏰ Time : {thai_time.strftime("%H:%M")}
""")

    time.sleep(60)