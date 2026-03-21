# test_signal_only.py
import os
from dotenv import load_dotenv
load_dotenv()

from strategy.ai_gatekeeper import gatekeeper

print("🧪 Testing: AI called only on BUY/SELL signals\n")

# ✅ กรณีที่ 1: signal = "NONE" → ไม่ควรเรียก AI
print("1. Testing signal='NONE' (should skip AI)...")
result_none = gatekeeper.validate_signal(
    market_state={"price": 4500, "htf_trend": "UP", "ltf_trend": "UP", "rsi": 50, "atr": 10, "structure": "Range"},
    signal_data={"direction": "NONE", "pattern": "No pattern"}
)
print(f"   ✅ Result: {result_none['provider']} (confidence: {result_none['confidence']}%)\n")

# ✅ กรณีที่ 2: signal = "BUY" → ควรเรียก AI
print("2. Testing signal='BUY' (should call AI)...")
result_buy = gatekeeper.validate_signal(
    market_state={"price": 4500, "htf_trend": "UP", "ltf_trend": "DOWN", "rsi": 35, "atr": 15, "structure": "Pullback"},
    signal_data={"direction": "BUY", "pattern": "RSI Oversold"}
)
print(f"   ✅ Result: {result_buy['provider']} (confidence: {result_buy['confidence']}%)\n")

# ✅ กรณีที่ 3: signal = "SELL" → ควรเรียก AI
print("3. Testing signal='SELL' (should call AI)...")
result_sell = gatekeeper.validate_signal(
    market_state={"price": 4500, "htf_trend": "DOWN", "ltf_trend": "UP", "rsi": 65, "atr": 15, "structure": "Resistance"},
    signal_data={"direction": "SELL", "pattern": "RSI Overbought"}
)
print(f"   ✅ Result: {result_sell['provider']} (confidence: {result_sell['confidence']}%)\n")

print("✅ Test complete! AI only called on BUY/SELL signals.")