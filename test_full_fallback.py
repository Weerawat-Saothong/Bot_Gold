# test_full_fallback.py
import os
from dotenv import load_dotenv
load_dotenv()

from strategy.ai_gatekeeper import gatekeeper

print("🧪 Testing Full Fallback System")
print("   Qwen → Gemini → 70% Silent\n")

result = gatekeeper.validate_signal(
    market_state={
        "price": 4500.00,
        "htf_trend": "UP",
        "ltf_trend": "DOWN",
        "rsi": 35.5,
        "atr": 15.2,
        "structure": "Pullback"
    },
    signal_data={
        "direction": "BUY",
        "pattern": "RSI Oversold + EMA Support"
    }
)

print(f"[OK] Decision: {result['decision']}")
print(f"[OK] Confidence: {result['confidence']}%")
print(f"[OK] Provider: {result['provider']}")
print(f"[LOG] Reason: {result['reason']}")