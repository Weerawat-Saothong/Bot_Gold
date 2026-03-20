import logging
import os
import time
from datetime import datetime, timedelta, timezone

from config import *
from data.market_data import get_market_data, get_market_data_htf
from strategy.signal_engine import get_signal, create_features, is_overextended, market_structure
from execution.signal_writer import write_signal
from risk.risk_engine import calculate_sl_tp
from notify.line_notify import send_line
from notify.news_manager import is_news_active
from strategy.ai_gatekeeper import gatekeeper

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
        if IS_ANALYSIS_MODE:
            return
        with open(BASE_PATH + "bot_active_trade.txt", "w") as f:
            f.write(str(state))
    except Exception as e:
        logger.error(f"Error writing trade flag: {e}")

def write_bot_active_trade_dir(direction):
    try:
        if IS_ANALYSIS_MODE:
            return
        with open(BASE_PATH + "bot_active_trade_dir.txt", "w") as f:
            f.write(str(direction))
    except Exception as e:
        logger.error(f"Error writing trade direction: {e}")


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
black_swan_trades_today = 0
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
daily_loss_alert_sent = False

active_trade_direction = None
try:
    with open(BASE_PATH + "bot_active_trade_dir.txt") as f:
        val = f.read().strip()
        if val in ["BUY", "SELL"]:
            active_trade_direction = val
except:
    pass


# Check if trade file is from a previous day (for startup reset)
try:
    trade_file_path = BASE_PATH + "trades_today.txt"
    if os.path.exists(trade_file_path):
        mtime = os.path.getmtime(trade_file_path)
        file_date = datetime.fromtimestamp(mtime, timezone.utc).date()
        today_date = datetime.now(timezone.utc).date()
        if file_date < today_date:
            logger.info("Startup: Reseting yesterday's trades from file")
            with open(trade_file_path, "w") as f:
                f.write("0")
            # Also reset PnL file if it exists
            pnl_file_path = BASE_PATH + "pnl.txt"
            if os.path.exists(pnl_file_path):
                with open(pnl_file_path, "w") as f:
                    f.write("0.0")
except Exception as e:
    logger.error(f"Error checking daily reset on startup: {e}")

# 🔥 AI Analysis: Tracking Rejection Reasons
rejection_reasons = {}
last_analysis_time = datetime.now(timezone.utc)
ANALYSIS_INTERVAL_HOURS = 2 

# ⚠️ ระบบเตือนข้อมูลค้าง (Stale Data Alert)
last_stale_alert_time = None
is_stale = False
STALE_THRESHOLD_MINUTES = 15  # เตือนถ้าค้างเกิน 15 นาที
STALE_COOLDOWN_MINUTES = 30   # เตือนซ้ำทุก 30 นาที



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
        ai_confidence = 0 # Initialize confidence per iteration

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
            black_swan_trades_today = 0
            current_day = now.day
            previous_pnl = 0

            logger.info("New trading day reset")

        # =========================
        # ACCOUNT STATUS
        # =========================

        account_balance = read_balance(account_balance)
        daily_loss_limit = account_balance * DAILY_RISK_PERCENT
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
            if active_trade_direction is not None:
                active_trade_direction = None
                write_bot_active_trade_dir("NONE")
            if bot_trade_flag != "0":
                write_bot_active_trade("0")

        # =========================
        # DAILY LOSS LIMIT
        # =========================

        today_date = thai_time.date()
        activation_date = datetime(2026, 3, 23, tzinfo=timezone.utc).date()
        
        if today_date >= activation_date and daily_pnl <= -daily_loss_limit:


            if not daily_loss_alert_sent:
                logger.warning(f"CRITICAL: Daily Loss Limit Reached ({daily_pnl} / {-daily_loss_limit})")
                send_line(f"🛑 RISK CONTROL: STOP TRADING\n\n⚠️ Daily Loss Limit Reached!\n\n📉 Current PnL : {round(daily_pnl, 2)}$\n🚫 Limit       : {round(-daily_loss_limit, 2)}$\n\nบอทหยุดเทรดอัตโนมัติเพื่อเซฟพอร์ตครับ\nจะเริ่มใหม่พรุ่งนี้เข้านะครับ\n\n⏰ {thai_time.strftime('%H:%M')}")
                daily_loss_alert_sent = True
            
            time.sleep(60)
            continue
        else:
            if daily_loss_alert_sent and daily_pnl > -daily_loss_limit:
                daily_loss_alert_sent = False












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

        # =========================
        # ⚠️ STALE DATA CHECK (MODIFIED)
        # =========================
        try:
            mtime = os.path.getmtime(PATH_M5)
            diff_sec = time.time() - mtime
            diff_min = diff_sec / 60
            
            if diff_min > STALE_THRESHOLD_MINUTES:
                now_utc = datetime.now(timezone.utc)
                if last_stale_alert_time is None or (now_utc - last_stale_alert_time).total_seconds() >= STALE_COOLDOWN_MINUTES * 60:
                    
                    logger.error(f"⚠️ DATA STALE: MT5 has not updated for {round(diff_min, 1)} minutes!")
                    send_line(f"⚠️ GOLD BOT: DATA STALE\n\nข้อมูลจาก MT5 ไม่มีการอัพเดตมาเป็นเวลา {round(diff_min, 1)} นาทีแล้วครับ!\n\nกรุณาตรวจสอบ MT5 บน Server ด้วยนะครับ\n\n⏰ {thai_time.strftime('%H:%M')}")
                    last_stale_alert_time = now_utc
                    is_stale = True
            
            elif is_stale:
                # Data recovered!
                logger.info("✅ DATA RECOVERED: MT5 is updating again!")
                send_line(f"✅ GOLD BOT: DATA RECOVERED\n\nข้อมูลจาก MT5 กลับมาอัพเดตปกติแล้วครับ\n\n⏰ {thai_time.strftime('%H:%M')}")
                is_stale = False
                last_stale_alert_time = None

        except Exception as e:
            logger.warning(f"Could not check data age: {e}")


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

            if ai_signal in ["BUY", "SELL", "BUY_SWAN", "SELL_SWAN"]:

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
        # MOMENTUM CONFIRMATION & SWAN OVERRIDE
        # =========================

        if signal == "BUY" and not momentum_up:
            signal = "NONE"

        if signal == "SELL" and not momentum_down:
            signal = "NONE"

        if signal == "BUY_SWAN":
            if black_swan_trades_today >= 1:
                signal = "NONE"
                logger.info("Black Swan limit reached for today.")
            else:
                signal = "BUY"
                black_swan_trades_today += 1
                send_line("🚨 BLACK SWAN MODE ACTIVATED: BUY 🚨\n\nChasing extreme momentum!")

        if signal == "SELL_SWAN":
            if black_swan_trades_today >= 1:
                signal = "NONE"
                logger.info("Black Swan limit reached for today.")
            else:
                signal = "SELL"
                black_swan_trades_today += 1
                send_line("🚨 BLACK SWAN MODE ACTIVATED: SELL 🚨\n\nChasing extreme momentum waterfall!")

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
        # ENERGENCY TREND EXIT (NEW)
        # =========================
        if current_positions > 0:
            from strategy.signal_engine import check_trend_safety
            trend_state, slope = check_trend_safety(df)
            price = last["close"]
            ema = last["ema50"]
            atr = last["atr"]

            # Exit BUY only if trend is steep down (Reversal)
            if trend_state == "STEEP_DOWN" and active_trade_direction == "BUY":
                logger.warning(f"⚠️ EMERGENCY EXIT BUY: Trend Reversal! (Slope: {slope:.2f})")
                signal = "CLOSE_BUY"
            # Exit SELL only if trend is steep up (Reversal)
            elif trend_state == "STEEP_UP" and active_trade_direction == "SELL":
                logger.warning(f"⚠️ EMERGENCY EXIT SELL: Trend Reversal! (Slope: {slope:.2f})")
                signal = "CLOSE_SELL"

            if signal in ["CLOSE_BUY", "CLOSE_SELL"]:
                send_line(f"⚠️ EMERGENCY EXIT\n\nบอทสั่งปิดออเดอร์ทันทีเพราะเทรนด์เปลี่ยนทิศทางรุนแรงครับ\n\n💰 Type: {signal}\n📉 Slope: {slope:.2f}\n⏰ {thai_time.strftime('%H:%M')}")
                # Skip normal signal engine until next loop
                pass 

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
            if sweep == "SELL_SWEEP" and momentum_down and active_trade_direction == "BUY":

                logger.info("Liquidity Exit BUY")

                signal = "CLOSE_BUY"

                send_line(f"""⚠️ LIQUIDITY EXIT

BUY Closed

Sell Liquidity Sweep Detected

⏰ {thai_time.strftime("%H:%M")}
""")

            # EXIT SELL
            elif sweep == "BUY_SWEEP" and momentum_up and active_trade_direction == "SELL":

                logger.info("Liquidity Exit SELL")

                signal = "CLOSE_SELL"

                send_line(f"""⚠️ LIQUIDITY EXIT

SELL Closed

Buy Liquidity Sweep Detected

⏰ {thai_time.strftime("%H:%M")}
""")


        # =========================
        # AI GATEKEEPER VALIDATION (NEW)
        # =========================
        if signal in ["BUY", "SELL"]:
            # 🛑 BREAK: CHECK OVEREXTENDED (ป้องกันดอย/เหว)
            if is_overextended(price, last['ema50'], last['atr'], signal):
                logger.info(f"🚫 BLOCKING {signal}: Overextended (Price too far from EMA50)")
                if not IS_ANALYSIS_MODE:
                    send_line(f"🚫 {signal} CANCELLED\n\nบอทระงับสัญญาณ {signal} เพราะราคาอยู่ห่างจากเส้น EMA มากเกินไป (เสี่ยงปลายไส้)\n\n💰 Price: {round(price,2)}\n⏰ {thai_time.strftime('%H:%M')}")
                signal = "NONE"

        if signal in ["BUY", "SELL"] and USE_AI_GATEKEEPER:
            
            # Prepare market state for AI
            market_state = {
                "price": round(price, 2),
                "htf_trend": "UP" if df_htf.iloc[-1]['ema50'] > df_htf.iloc[-1]['ema200'] else "DOWN",
                "ltf_trend": "UP" if last['ema50'] > last['ema200'] else "DOWN",
                "rsi": round(last['rsi'], 2),
                "atr": round(last['atr'], 2),
                "structure": market_structure(df)
            }
            
            signal_data = {
                "direction": signal,
                "pattern": rejection_reason # Rejection reason becomes pattern if signal found
            }
            
            ai_result = gatekeeper.validate_signal(market_state, signal_data)
            ai_confidence = ai_result.get('confidence', 0) # เก็บค่าความมั่นใจไว้ใช้คำนวณ Lot
            
            if ai_result['decision'] == "REJECT" or ai_result['confidence'] < AI_CONFIDENCE_THRESHOLD:
                logger.info(f"AI Gatekeeper Rejected Signal. Reason: {ai_result['reason']} (Confidence: {ai_result['confidence']}%)")
                
                # แจ้งเตือนผ่าน LINE เฉพาะในโหมดวิเคราะห์ (ถ้าคุยกับ User ไว้ว่าไม่ให้รบกวน อาจจะข้ามไป แต่เป็นข้อมูลที่ดี)
                if IS_ANALYSIS_MODE:
                    logger.info(f"AI GUARD: REJECTED {signal} | Reason: {ai_result['reason']}")
                
                signal = "NONE" # ยกเลิกการเข้าออเดอร์
            else:
                logger.info(f"AI Gatekeeper Confirmed Signal. Reason: {ai_result['reason']} (Confidence: {ai_result['confidence']}%)")
                if IS_ANALYSIS_MODE:
                    logger.info(f"AI GUARD: CONFIRMED {signal} | Reason: {ai_result['reason']}")


        # =========================
        # SL / TP
        # =========================

        # RESET AI DATA FOR THIS LOOP
        ai_confidence = 0
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
            if not IS_ANALYSIS_MODE:
                write_bot_active_trade("1")
                write_bot_active_trade_dir(signal)
                active_trade_direction = signal

                # ⚖️ DYNAMIC LOT CALCULATION (คำนวณตามความเสี่ยงจริง)
                # สูตร: Lot = Risk_USD / (SL_Distance * ContractSize)
                risk_amount = RISK_PER_TRADE_USD
                
                # ถ้า AI มั่นใจสูงมาก ให้เพิ่มความเสี่ยง 2 เท่า ($20)
                if ai_confidence >= 90:
                    risk_amount = RISK_PER_TRADE_USD * 2
                    logger.info(f"🔥 HIGH CONFIDENCE: Doubling risk to ${risk_amount}")
                
                # คำนวณ Lot (ทองคำ 1 lot = 100 oz)
                # ปรับแต่งให้รองรับระยะ SL ขั้นต่ำเพื่อป้องกัน Lot บวมเกินไป
                calculated_lot = risk_amount / (max(sl_distance, 0.5) * 100)
                
                # ปรับเป็นเลข 2 ตำแหน่ง (MT5 Standard) และคุมไม่ให้เกิน Limit
                trade_lot = round(max(0.01, min(calculated_lot, 1.0)), 2)
                
                logger.info(f"⚖️ Dynamic Lot: Risk ${risk_amount} | SL Dist {round(sl_distance,2)} | Final Lot: {trade_lot}")
                
                write_signal(signal, sl, tp, trade_lot)
            else:
                logger.info(f"ANALYSIS MODE: Signal '{signal}' identified but NOT written to file.")

        elif signal != "NONE":
             # Handle non-trade signals (CLOSE_BUY, CLOSE_SELL)
             if not IS_ANALYSIS_MODE:
                 write_signal(signal, None, None)

        # =========================
        # LOSS DETECTION
        # =========================

        if daily_pnl < previous_pnl:
            last_loss_candle = candle_counter

        previous_pnl = daily_pnl

        # =========================
        # LOG
        # =========================

        if IS_ANALYSIS_MODE:
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
        else:
            # Log ทุกรอบเพื่อให้เห็นว่าบอททำอะไรอยู่บน server
            logger.info(f"[{signal}] AI: {ai_signal} ({rejection_reason if ai_signal == 'NONE' else 'OK'}) | Price: {price} | ATR: {round(last['atr'],2)} | RSI: {round(last['rsi'],1)} | Pos: {current_positions}")

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