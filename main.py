import logging
import os
import time
import sys
import pandas as pd
from datetime import datetime, timedelta, timezone

from config import *
from data.market_data import get_market_data, get_market_data_htf
from strategy.signal_engine import get_signal, create_features
from risk.risk_engine import calculate_sl_tp, find_last_swing_low, find_last_swing_high
from execution.signal_writer import write_signal
from notify.line_notify import send_line
from notify.news_manager import is_news_active
from strategy.ai_gatekeeper import gatekeeper

# =========================
# 📝 LOGGING SETUP
# =========================
import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler("bot_gold_pro.log", encoding='utf-8'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# =========================
# 🛠️ HELPERS
# =========================
def read_file_safe(filename, default):
    try:
        if not os.path.exists(BASE_PATH + filename): return default
        with open(BASE_PATH + filename) as f:
            val = f.read().strip()
            return type(default)(val) if val else default
    except: return default

def write_file_safe(filename, content):
    try:
        with open(BASE_PATH + filename, "w") as f:
            f.write(str(content))
    except Exception as e: logger.error(f"Error writing {filename}: {e}")

# =========================
# 🔄 MAIN EXECUTION LOOP
# =========================
def main():
    logger.info("GOLD QUANT PRO (SIGNAL ONLY): SYSTEM START")
    send_line("🟢 [GOLD PRO] Radar Scanner is now ONLINE!")
    
    current_day = datetime.now(timezone.utc).day
    trades_today = 0
    last_trade_candle = -100

    while True:
        try:
            now = datetime.now(timezone.utc)
            thai_time = now + timedelta(hours=7)
            
            # --- ⏰ Market Session Check ---
            wd = thai_time.weekday()
            if wd >= 5: 
                time.sleep(300); continue

            # --- 📊 Account Status ---
            balance = read_file_safe("balance.txt", 1000.0)
            daily_pnl = read_file_safe("pnl.txt", 0.0)

            # --- 🚨 Risk Threshold ---
            if daily_pnl <= -(balance * DAILY_RISK_PERCENT):
                logger.warning("Daily Loss Limit Reached. Sleeping...")
                time.sleep(300); continue

            # --- 📰 News Filter ---
            if USE_NEWS_FILTER:
                news_active, _ = is_news_active(currency="USD", buffer_minutes=NEWS_WAIT_MINUTES)
                if news_active:
                    time.sleep(60); continue

            # --- 🔍 Market Scanning ---
            df = get_market_data()
            df_htf = get_market_data_htf()
            if df is None or df_htf is None:
                time.sleep(10); continue

            df = create_features(df)
            df_htf = create_features(df_htf)
            candle_counter = len(df)

            # --- 🎯 Signal Identification ---
            signal, reason = get_signal(df, df_htf)
            price = df.iloc[-1]["close"]

            # --- 🛡️ Risk, AI Gatekeeper & Execution ---
            if signal in ["BUY", "SELL"]:
                if (candle_counter - last_trade_candle) < TRADE_COOLDOWN:
                    logger.info("Trade cooldown active")
                    signal = "NONE"
                else:
                    # --- 🧔 AI Gatekeeper Validation ---
                    ai_confidence = 50
                    if USE_AI_GATEKEEPER:
                        logger.info(f"Checking {signal} with AI Council...")
                        market_state = {
                            "price": round(price, 2),
                            "htf_trend": "UP" if df_htf.iloc[-1]['ema50'] > df_htf.iloc[-1]['ema200'] else "DOWN",
                            "rsi": round(df.iloc[-1]['rsi'], 2), "atr": round(df.iloc[-1]['atr'], 2),
                            "swing_low": find_last_swing_low(df), "swing_high": find_last_swing_high(df)
                        }
                        ai_res = gatekeeper.validate_signal(market_state, {"direction": signal, "pattern": reason})
                        ai_confidence = ai_res.get('confidence', 50)
                        if ai_res['decision'] == "REJECT" or ai_confidence < AI_CONFIDENCE_THRESHOLD:
                            logger.warning(f"AI Council Rejected {signal}: {ai_res['reason']}")
                            signal = "NONE"

            # --- Execution (ONLY OPEN TRADES) ---
            if signal in ["BUY", "SELL"]:
                sl, tp = calculate_sl_tp(df, signal, price)
                if sl and tp:
                    mult = 1.5 if ai_confidence >= 80 else (0.5 if ai_confidence < 50 else 1.0)
                    lot = round(max(MIN_LOT, min(BASE_LOT * mult, MAX_LOT)), 2)
                    
                    logger.info(f"[SIGNAL] {signal} CONFIRMED | Price: {price:.2f} | Lot: {lot}")
                    if not IS_ANALYSIS_MODE:
                        write_file_safe("bot_active_trade.txt", "1")
                        write_file_safe("bot_active_trade_dir.txt", signal)
                        write_signal(signal, sl, tp, lot)
                        last_trade_candle = candle_counter
                        send_line(f"🎯 [GOLD PRO] {signal} AT {price}\n🏆 TP: {tp} | 🛡️ SL: {sl}\n⚖️ Lot: {lot} (Conf: {ai_confidence}%)")
                else:
                    logger.error("Failed to calculate SL/TP levels.")
                    signal = "NONE"

            if signal == "NONE":
                logger.info(f"[NONE] No Pattern | Price: {price:.2f} | ATR: {df.iloc[-1]['atr']:.2f} | RSI: {df.iloc[-1]['rsi']:.2f}")

            # --- ⏳ Wait for Next Candle ---
            time.sleep(30)

        except Exception as e:
            logger.error(f"SYSTEM ERROR: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()