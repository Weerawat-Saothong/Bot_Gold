import pandas as pd
import os
from config import *
from strategy.signal_engine import create_features, get_signal
from risk.risk_engine import calculate_sl_tp, apply_risk_management

# =========================
# LOAD DATA
# =========================

BACKTEST_FILE = os.path.join(BASE_PATH, "gold_m5.csv")
print(f"Loading data from: {BACKTEST_FILE}")

try:
    df = pd.read_csv(BACKTEST_FILE, sep=r"\s+", names=["date","time","open","high","low","close","volume"])
except FileNotFoundError:
    BACKTEST_FILE = PATH_M5
    df = pd.read_csv(BACKTEST_FILE, sep=r"\s+", names=["date","time","open","high","low","close","volume"])

df["datetime"] = pd.to_datetime(df["date"] + " " + df["time"], format="%Y.%m.%d %H:%M")
df = df.drop(columns=["date","time"]).sort_values("datetime").reset_index(drop=True)
df = create_features(df)

# HTF
df_htf_raw = df.resample("1h", on="datetime").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
df_htf = df_htf_raw.shift(1).dropna().reset_index()
df_htf = create_features(df_htf)

# BACKTEST STATE
balance = 1000
INITIAL_BALANCE = 1000
positions = []
trade_logs = []
wins = 0
losses = 0
trades = 0
rejection_reasons = {}

# Optimization: Run only on last 10,000 candles for quick feedback
TEST_COUNT = 20000
start_idx = len(df) - TEST_COUNT
if start_idx < 100: start_idx = 100

print(f"Starting Backtest on LAST {TEST_COUNT} candles...")

for i in range(start_idx, len(df)):
    # if i < 100: continue # Handled by start_idx
    
    window = df.iloc[:i+1]
    last = window.iloc[-1]
    window_htf = df_htf[df_htf["datetime"] < last["datetime"]]
    if len(window_htf) < 50: continue

    # 1. Update positions
    for pos in positions[:]:
        # Apply Trailing/BE
        pos["sl"] = apply_risk_management(pos, last["close"])

        hit_sl = False
        hit_tp = False

        if pos["type"] == "BUY":
            if last["low"] <= pos["sl"]: hit_sl = True
            elif last["high"] >= pos["tp"]: hit_tp = True
        else:
            if last["high"] >= pos["sl"]: hit_sl = True
            elif last["low"] <= pos["tp"]: hit_tp = True

        if hit_sl or hit_tp:
            exit_price = pos["sl"] if hit_sl else pos["tp"]
            p_diff = (exit_price - pos["entry"]) if pos["type"] == "BUY" else (pos["entry"] - exit_price)
            
            # 🔥 Corrected Profit Calculation (0.01 lot where 1 USD move = 1 USD profit)
            profit = p_diff 
            balance += profit
            
            result = "WIN" if profit > 0 else "LOSS"
            if result == "WIN": wins += 1
            else: losses += 1

            trade_logs.append({
                "entry_time": pos["entry_time"],
                "exit_time": last["datetime"],
                "type": pos["type"],
                "entry": pos["entry"],
                "exit": exit_price,
                "result": result,
                "profit": profit,
                "atr": pos["atr"],
                "rsi": pos["rsi"]
            })
            positions.remove(pos)

    # 2. Open Trades
    if len(positions) < MAX_POSITIONS:
        ai_signal, reason = get_signal(window, window_htf)
        
        if ai_signal == "NONE":
            summary_reason = reason
            if reason.startswith("Blocked:"):
                summary_reason = reason.split("(")[0].strip() if "(" in reason else reason
            rejection_reasons[summary_reason] = rejection_reasons.get(summary_reason, 0) + 1
            continue
        if ai_signal in ["BUY_SWAN", "SELL_SWAN"]:
            ai_signal = "BUY" if ai_signal == "BUY_SWAN" else "SELL"
            
        if ai_signal in ["BUY", "SELL"]:
            sl, tp = calculate_sl_tp(window, ai_signal, last["close"])
            if sl and tp:
                positions.append({
                    "type": ai_signal,
                    "entry": last["close"],
                    "sl": sl,
                    "tp": tp,
                    "entry_time": last["datetime"],
                    "atr": last["atr"],
                    "rsi": last["rsi"]
                })
                trades += 1

# Results
print("\n========== GOLD QUANT BACKTEST RESULTS (BALANCED) ==========")
print(f"Final Balance: {round(balance, 2)}")
print(f"Total Return: {round((balance-INITIAL_BALANCE)/INITIAL_BALANCE*100, 2)} %")
print(f"Trades: {trades}")
print(f"Wins: {wins} | Losses: {losses}")
print(f"Winrate: {round(wins/(wins+losses)*100, 2) if (wins+losses)>0 else 0} %")

print("\n📊 REJECTION REASONS ANALYSIS:")
sorted_reasons = sorted(rejection_reasons.items(), key=lambda x: x[1], reverse=True)
for reason, count in sorted_reasons[:10]:
    print(f"• {reason}: {count}")
print("=========================================================\n")

if trade_logs:
    pd.DataFrame(trade_logs).to_csv("trades_analysis.csv", index=False)
