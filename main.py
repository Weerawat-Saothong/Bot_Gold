import logging
import os
import time
import sys
import io
from datetime import datetime, timedelta, timezone

# ✨ Fix Windows Emoji/Thai encoding error
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from config import *
from data.market_data import get_market_data, get_market_data_htf
from strategy.signal_engine import get_signal, create_features, is_overextended, market_structure
from risk.risk_engine import calculate_sl_tp, find_last_swing_low, find_last_swing_high
from execution.signal_writer import write_signal
from notify.line_notify import send_line
from notify.news_manager import is_news_active
from strategy.ai_gatekeeper import gatekeeper

# =========================
# LOGGING SETUP
# =========================

log_file = os.path.join(os.path.dirname(BASE_PATH), "bot.log")
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
🚀 [SYSTEM] GOLD QUANT BOT
──────────────────
🟢 Status : ONLINE
⏰ Time   : {thai_time.strftime("%H:%M")}
──────────────────
✅ System Ready
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
            logger.debug(f"(analysis mode) skip writing bot_active_trade: {state}")
            return
        with open(BASE_PATH + "bot_active_trade.txt", "w") as f:
            f.write(str(state))
    except Exception as e:
        logger.error(f"Error writing trade flag: {e}")

def write_bot_active_trade_dir(direction):
    try:
        with open(BASE_PATH + "bot_active_trade_dir.txt", "w") as f:
            f.write(str(direction))
        logger.info(f"Persisted bot_active_trade_dir: {direction}")
    except Exception as e:
        logger.error(f"Error writing trade direction: {e}")


def gold_market_open(thai_time):

    wd = thai_time.weekday()
    hour = thai_time.hour

    if wd == 5 and hour >= 4:
        return False

    if wd == 6:
        return False

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

# [WARN] ระบบเตือนข้อมูลค้าง (Stale Data Alert)
last_stale_alert_time = None
is_stale = False
STALE_THRESHOLD_MINUTES = 15
STALE_COOLDOWN_MINUTES = 30



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

            if last_weekday < 5:
                send_line("""
📴 [MARKET] CLOSED
──────────────────
Gold Market Closed (Weekend)
บอทกำลังเข้าสู่โหมด Standby ครับ
──────────────────
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
                time.sleep(60)
                continue



        candle_counter += 1
        ai_confidence = 0

        # =========================
        # RESET DAILY
        # =========================

        if now.day != current_day:
            logger.info(f"Daily Reset. Balance: {account_balance}, PnL: {daily_pnl}")

            send_line(f"""
📊 [REPORT] DAILY SUMMARY
──────────────────
📅 Date : {now.strftime("%Y-%m-%d")}
⏰ Time : {thai_time.strftime("%H:%M")}

🔄 Trades  : {trades_today}
💰 PnL     : {daily_pnl}$
🏦 Balance : {account_balance}$
──────────────────
⚙️ Max/Day : {MAX_TRADES_PER_DAY}
🟢 Status  : Active
──────────────────
🚀 Gold Quant Bot
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

            logger.warning(" MANUAL TRADE DETECTED")

            send_line(f"""
🚨 [ALERT] MANUAL TRADE
──────────────────
ตรวจพบการเปิดออเดอร์เอง (Manual)
บอทไม่ได้เป็นคนเปิดออเดอร์นี้ครับ!

⚠️ System Locked
⏰ {thai_time.strftime("%H:%M")}
──────────────────
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
        activation_date = datetime(2026, 3, 30, tzinfo=timezone.utc).date()
        
        if today_date >= activation_date and daily_pnl <= -daily_loss_limit:


            if not daily_loss_alert_sent:
                logger.warning(f"CRITICAL: Daily Loss Limit Reached ({daily_pnl} / {-daily_loss_limit})")
                send_line(f"""
🛡️ [RISK] STOP TRADING
──────────────────
แจ้งเตือน: ถึงวงเงินขาดทุนรายวันแล้ว!
บอทหยุดเทรดอัตโนมัติเพื่อเซฟพอร์ตครับ

📉 Current PnL : {round(daily_pnl, 2)}$
🚫 Limit       : {round(-daily_loss_limit, 2)}$

บอทจะเริ่มใหม่ในวันพรุ่งนี้ครับ 💤
⏰ {thai_time.strftime('%H:%M')}
──────────────────
""")
                daily_loss_alert_sent = True
            
            time.sleep(60)
            continue
        else:
            if daily_loss_alert_sent and daily_pnl > -daily_loss_limit:
                daily_loss_alert_sent = False

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
        # [WARN] STALE DATA CHECK (MODIFIED)
        # =========================
        try:
            mtime = os.path.getmtime(PATH_M5)
            diff_sec = time.time() - mtime
            diff_min = diff_sec / 60
            
            if diff_min > STALE_THRESHOLD_MINUTES:
                now_utc = datetime.now(timezone.utc)
                if last_stale_alert_time is None or (now_utc - last_stale_alert_time).total_seconds() >= STALE_COOLDOWN_MINUTES * 60:
                    
                    logger.error(f"[WARN] DATA STALE: MT5 has not updated for {round(diff_min, 1)} minutes!")
                    send_line(f"""
⚠️ [WARN] DATA STALE
──────────────────
ข้อมูลจาก MT5 ไม่มีการอัพเดต!
ค้างมาเป็นเวลา {round(diff_min, 1)} นาทีแล้ว

🔧 กรุณาตรวจสอบ Server และ MT5 ด่วนครับ
⏰ {thai_time.strftime('%H:%M')}
──────────────────
""")
                    last_stale_alert_time = now_utc
                    is_stale = True
            
            elif is_stale:
                logger.info("[OK] DATA RECOVERED: MT5 is updating again!")
                send_line(f"""
✅ [OK] DATA RECOVERED
──────────────────
ข้อมูลจาก MT5 กลับมาอัพเดตปกติแล้วครับ!
บอทพร้อมทำงานต่อทันที

⏰ {thai_time.strftime('%H:%M')}
──────────────────
""")
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
                    distance = abs(price - last_entry_price)
                    
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
                send_line(f"🔥 [BLACK SWAN] ACTIVATED: BUY\n\nโหมด Momentum รุนแรงขยี้ตลาด!\nChasing extreme gold momentum! 🚀")

        if signal == "SELL_SWAN":
            if black_swan_trades_today >= 1:
                signal = "NONE"
                logger.info("Black Swan limit reached for today.")
            else:
                signal = "SELL"
                black_swan_trades_today += 1
                send_line(f"🌊 [BLACK SWAN] ACTIVATED: SELL\n\nโหมดตกเหวนรก น้ำตกทองคำ!\nChasing extreme momentum waterfall! 📉")

        # =========================
        # REAL-TIME RISK MANAGEMENT (Trailing & Breakeven)
        # =========================
        
        from risk.risk_engine import apply_risk_management
        
        if current_positions > 0:
            pass

        # =========================
        # EMERGENCY TREND & CRASH EXIT 
        # =========================
        if current_positions > 0:
            from strategy.signal_engine import check_trend_safety, check_flash_crash
            trend_state, slope = check_trend_safety(df)
            crash_state = check_flash_crash(df)
            
            price = last["close"]
            ema = last["ema50"]
            atr = last["atr"]

            if crash_state == "CRASH_DOWN" and active_trade_direction == "BUY":
                logger.warning(f"[PARACHUTE] PARACHUTE EXIT BUY: Flash Crash Down!")
                signal = "CLOSE_BUY"
                logger.info(f"Decision: set {signal} (crash_state={crash_state}, active={active_trade_direction}, price={price}, atr={atr})")
            elif crash_state == "CRASH_UP" and active_trade_direction == "SELL":
                logger.warning(f"[PARACHUTE] PARACHUTE EXIT SELL: Flash Spike Up!")
                signal = "CLOSE_SELL"
                logger.info(f"Decision: set {signal} (crash_state={crash_state}, active={active_trade_direction}, price={price}, atr={atr})")

            elif trend_state == "STEEP_DOWN" and active_trade_direction == "BUY":
                logger.warning(f"[WARN] EMERGENCY EXIT BUY: Trend Reversal! (Slope: {slope:.2f})")
                signal = "CLOSE_BUY"
                logger.info(f"Decision: set {signal} (trend_state={trend_state}, slope={slope:.2f}, active={active_trade_direction})")
            elif trend_state == "STEEP_UP" and active_trade_direction == "SELL":
                logger.warning(f"[WARN] EMERGENCY EXIT SELL: Trend Reversal! (Slope: {slope:.2f})")
                signal = "CLOSE_SELL"
                logger.info(f"Decision: set {signal} (trend_state={trend_state}, slope={slope:.2f}, active={active_trade_direction})")

            if signal in ["CLOSE_BUY", "CLOSE_SELL"]:
                cause = "โดนทุบแรงกะทันหันกระชากหนี SL" if crash_state != "SAFE" else f"เทรนด์เปลี่ยนทิศรุนแรง (Slope {slope:.2f})"
                send_line(f"""
🪂 [EMERGENCY] PARACHUTE EXIT
──────────────────
บอทสั่งปิดออเดอร์เพื่อรักษาเงินทุน!

📌 สาเหตุ: {cause}
🏷️ Type: {signal}
⏰ {thai_time.strftime('%H:%M')}
──────────────────
""")
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

            if sweep == "SELL_SWEEP" and momentum_down and active_trade_direction == "BUY":

                logger.info("Liquidity Exit BUY")

                signal = "CLOSE_BUY"

                logger.info(f"Decision: set CLOSE_BUY (sweep={sweep}, momentum_down={momentum_down}, active={active_trade_direction})")

                send_line(f"""
💧 [EXIT] LIQUIDITY SWEEP
──────────────────
BUY Position Closed
ตรวจพบ Sell Liquidity Sweep

⏰ {thai_time.strftime("%H:%M")}
──────────────────
""")

            elif sweep == "BUY_SWEEP" and momentum_up and active_trade_direction == "SELL":

                logger.info("Liquidity Exit SELL")

                signal = "CLOSE_SELL"

                send_line(f"""
🎯 [EXIT] LIQUIDITY SWEEP
──────────────────
SELL Position Closed
ตรวจพบ Buy Liquidity Sweep

⏰ {thai_time.strftime("%H:%M")}
──────────────────
""")
                logger.info(f"Decision: set CLOSE_SELL (sweep={sweep}, momentum_up={momentum_up}, active={active_trade_direction})")


        # =========================
        # AI GATEKEEPER VALIDATION (NEW)
        # =========================
        if signal in ["BUY", "SELL"]:
            if is_overextended(price, last['ema50'], last['atr'], signal):
                logger.info(f" BLOCKING {signal}: Overextended (Price too far from EMA50)")
                if not IS_ANALYSIS_MODE:
                    send_line(f"""
🛑 [CANCEL] OVEREXTENDED
──────────────────
ยกเลิกสัญญาณ {signal} 
ราคาอยู่ห่างจากเส้น EMA มากเกินไป (เสี่ยงปลายไส้)

💰 Price: {round(price,2)}
⏰ {thai_time.strftime('%H:%M')}
──────────────────
""")
                signal = "NONE"

        ai_suggested_sl = None
        ai_suggested_tp = None

        if signal in ["BUY", "SELL"] and USE_AI_GATEKEEPER:
            
            market_state = {
                "price": round(price, 2),
                "htf_trend": "UP" if df_htf.iloc[-1]['ema50'] > df_htf.iloc[-1]['ema200'] else "DOWN",
                "ltf_trend": "UP" if last['ema50'] > last['ema200'] else "DOWN",
                "rsi": round(last['rsi'], 2),
                "atr": round(last['atr'], 2),
                "structure": market_structure(df),
                "swing_low": round(find_last_swing_low(df), 2),
                "swing_high": round(find_last_swing_high(df), 2),
                "ema50": round(last['ema50'], 2)
            }
            
            signal_data = {
                "direction": signal,
                "pattern": rejection_reason
            }
            
            ai_result = gatekeeper.validate_signal(market_state, signal_data)

            logger.debug(f"AI Raw Result: {ai_result}")
            if ai_result and ai_result.get('reason'):
                ai_result['reason'] = ai_result['reason'].encode('ascii', errors='replace').decode('ascii')
            ai_confidence = ai_result.get('confidence', 0)
            ai_suggested_sl = ai_result.get('suggested_sl')
            ai_suggested_tp = ai_result.get('suggested_tp')
            
            if ai_suggested_sl and ai_suggested_tp:
                logger.info(f"AI suggested SL={ai_suggested_sl}, TP={ai_suggested_tp}")
            
            if ai_result['decision'] == "REJECT" or ai_result['confidence'] < AI_CONFIDENCE_THRESHOLD:
                logger.info(f"AI Gatekeeper Rejected Signal. Reason: {ai_result['reason']} (Confidence: {ai_result['confidence']}%)")
                
                if IS_ANALYSIS_MODE:
                    logger.info(f"AI GUARD: REJECTED {signal} | Reason: {ai_result['reason']}")
                
                signal = "NONE"
            else:
                logger.info(f"AI Gatekeeper Confirmed Signal. Reason: {ai_result['reason']} (Confidence: {ai_result['confidence']}%)")
                if IS_ANALYSIS_MODE:
                    logger.info(f"AI GUARD: CONFIRMED {signal} | Reason: {ai_result['reason']}")


        # =========================
        # SL / TP
        # =========================
    
        sl = None
        tp = None

        if signal in ["BUY", "SELL"]:
            sl, tp = calculate_sl_tp(df, signal, price, ai_sl=ai_suggested_sl, ai_tp=ai_suggested_tp)
            sl_source = "AI" if (ai_suggested_sl and ai_suggested_tp and sl == round(ai_suggested_sl, 3)) else "Technical"

            if sl is None or tp is None:

                logger.error(f"Invalid SL/TP for signal {signal}")
                signal = "NONE"

            else:

                send_line(f"""
🔔 [SIGNAL] GOLD {"LAYER ADDED" if current_positions > 0 else "TRADE OPEN"}
──────────────────
🏷️ Direction : {signal}
💰 Entry     : {round(price,2)}
🔍 Pattern   : {rejection_reason}
📑 Layers    : {current_positions + 1}

🛑 Stop Loss : {round(sl,2)}
🎯 Take Profit : {round(tp,2)}
🤖 SL/TP Source : {sl_source}
⏰ {thai_time.strftime("%H:%M")}
──────────────────
🚀 Gold Quant Bot
""")

                sl_distance = abs(price - sl)

                if sl_distance < MIN_SL_DISTANCE:

                    logger.warning(f"SL ({round(sl_distance, 2)}) too close (Min: {MIN_SL_DISTANCE})")
                    signal = "NONE"

                else:

                    last_entry_price = price
                    last_trade_candle = candle_counter

        # =========================
        # ✅ DYNAMIC LOT CALCULATION (แก้ไขแล้ว - ตามความมั่นใจของ AI)
        # =========================

        if signal in ["BUY", "SELL"]:
            # Always update in-memory active trade direction
            active_trade_direction = signal

            if not IS_ANALYSIS_MODE:
                write_bot_active_trade("1")
                write_bot_active_trade_dir(signal)

                # ⚖️ DYNAMIC LOT CALCULATION (คำนวณตามความมั่นใจของ AI)
                logger.info(f"DEBUG: ai_confidence = {ai_confidence}") 
                # ✅ Confidence-based Lot Multiplier
                if ai_confidence < 40:
                    multiplier = 0.3
                elif ai_confidence < 50:
                    multiplier = 0.5
                elif ai_confidence < 80:
                    multiplier = 1.5
                else:
                    multiplier = 1.8

                # คำนวณ Lot จาก Base Lot × Multiplier
                base_lot = 0.03  # หรือใช้จาก config.BASE_LOT
                calculated_lot = base_lot * multiplier

                # จำกัดช่วง MIN-MAX
                trade_lot = round(max(0.01, min(calculated_lot, 0.05)), 2)

                logger.info(f" Dynamic Lot: Confidence {ai_confidence}% | Multiplier {multiplier}x | Final Lot: {trade_lot}")
                
                write_signal(signal, sl, tp, trade_lot)
            else:
                logger.info(f"ANALYSIS MODE: Signal '{signal}' identified but NOT written to file.")

        elif signal != "NONE":
             if signal in ["CLOSE_BUY", "CLOSE_SELL"]:
                 if active_trade_direction is None or active_trade_direction == "NONE":
                     logger.warning(f"Skipping {signal}: active_trade_direction unknown ({active_trade_direction})")
                     signal = "NONE"
                 else:
                     expected = f"CLOSE_{active_trade_direction}"
                     if signal != expected:
                         logger.warning(f"Signal {signal} mismatches active direction {active_trade_direction}; overriding to {expected}")
                         signal = expected

             if signal != "NONE" and not IS_ANALYSIS_MODE:
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
            if signal == "NONE":
                if ai_signal == "NONE":
                    status_msg = "No Pattern"
                else:
                    status_msg = f"{ai_signal} REJECTED: {rejection_reason}"
            else:
                status_msg = f"{ai_signal} CONFIRMED"

            logger.info(f"[{signal}] {status_msg} | Price: {price} | ATR: {round(last['atr'],2)} | RSI: {round(last['rsi'],1)} | Pos: {current_positions}")
            
        # =========================
        # [BOT] PERIODIC AI ANALYSIS REPORT
        # =========================
        
        if (now - last_analysis_time).total_seconds() >= ANALYSIS_INTERVAL_HOURS * 3600:
            
            if rejection_reasons:
                
                sorted_reasons = sorted(rejection_reasons.items(), key=lambda x: x[1], reverse=True)
                summary_text = "\n".join([f"• {reason}: {count} ครั้ง" for reason, count in sorted_reasons[:5]])
                
                send_line(f"""
🧠 [AI] ANALYSIS REPORT
──────────────────
สรุปเหตุผลที่ไม่เข้าเทรดในช่วง {ANALYSIS_INTERVAL_HOURS} ชม. ที่ผ่านมา

📊 สาเหตุหลัก:
{summary_text}

💡 คำแนะนำ: ตลาดอาจยังไม่มี Trend ชัดเจน บอทจึงเลือกที่จะไม่เสี่ยงครับ
──────────────────
""")
                
                rejection_reasons = {}
                last_analysis_time = now
                logger.info("AI Analysis report sent to LINE")


    except Exception as e:

        logger.exception(f"Unexpected error: {e}")

        send_line(f"""
❌ [ERROR] GOLD BOT CRASH
──────────────────
พบข้อผิดพลาดรุนแรง:
{e}

🔧 กรุณาตรวจสอบบอททันทีครับ
⏰ {thai_time.strftime("%H:%M")}
──────────────────
""")

    time.sleep(60)