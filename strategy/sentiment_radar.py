"""
🛰️ Sentiment Radar Module
ดึงข้อมูลว่า "รายใหญ่กำลังเล่นทางไหน" จากแหล่งฟรี 2 แหล่ง:
1. OANDA Order Book (ต้องการ API Key ฟรี จาก OANDA)
2. Myfxbook Community Outlook (ฟรี ไม่ต้องสมัคร)
3. Internal Price Action Sentiment (Fallback - ไม่ต้อง API เลย)
"""

import os
import requests
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Optional: ใส่ OANDA_API_KEY และ OANDA_ACCOUNT_ID ใน .env ถ้ามีบัญชีฟรี
OANDA_API_KEY    = os.getenv("OANDA_API_KEY", "")
OANDA_ACCOUNT_TYPE = os.getenv("OANDA_ACCOUNT_TYPE", "practice")  # "practice" หรือ "live"

def _get_oanda_sentiment():
    """ดึง Sentiment จาก OANDA Order Book (ต้องการ API Key)"""
    if not OANDA_API_KEY:
        return None
    try:
        base = "https://api-fxpractice.oanda.com" if OANDA_ACCOUNT_TYPE == "practice" else "https://api-fxtrade.oanda.com"
        url = f"{base}/v3/instruments/XAU_USD/orderBook"
        headers = {"Authorization": f"Bearer {OANDA_API_KEY}", "Content-Type": "application/json"}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code != 200: return None
        
        buckets = resp.json().get("orderBook", {}).get("buckets", [])
        long_pct = sum(float(b.get("longCountPercent", 0)) for b in buckets)
        short_pct = sum(float(b.get("shortCountPercent", 0)) for b in buckets)
        
        total = long_pct + short_pct
        if total == 0: return None
        
        bull_ratio = long_pct / total
        return {
            "source": "OANDA",
            "long_pct":  round(long_pct, 1),
            "short_pct": round(short_pct, 1),
            "bias": "BULLISH" if bull_ratio > 0.55 else ("BEARISH" if bull_ratio < 0.45 else "NEUTRAL"),
            "contrarian_bias": "SELL" if bull_ratio > 0.65 else ("BUY" if bull_ratio < 0.35 else "NEUTRAL")
        }
    except Exception as e:
        logger.debug(f"OANDA Sentiment error: {e}")
        return None

def _get_myfxbook_sentiment():
    """ดึง Sentiment จาก Myfxbook Community Outlook (ไม่ต้อง Key)"""
    try:
        url = "https://www.myfxbook.com/api/get-community-outlook.json"
        params = {"session": ""}  # Public endpoint ไม่ต้อง session สำหรับบางคู่
        resp = requests.get(url, params=params, timeout=8)
        if resp.status_code != 200: return None
        
        data = resp.json()
        if data.get("error"): return None
        
        # หา XAU/USD
        for sym in data.get("symbols", []):
            if "XAU" in sym.get("name", "").upper() or "GOLD" in sym.get("name", "").upper():
                long_pct  = float(sym.get("longsPercentage", 50))
                short_pct = float(sym.get("shortsPercentage", 50))
                bull_ratio = long_pct / 100
                return {
                    "source": "Myfxbook",
                    "long_pct":  round(long_pct, 1),
                    "short_pct": round(short_pct, 1),
                    "bias": "BULLISH" if bull_ratio > 0.55 else ("BEARISH" if bull_ratio < 0.45 else "NEUTRAL"),
                    # Contrarian: ถ้าคนส่วนมาก LONG อยู่ รายใหญ่มักจะขาย (และในทางกลับกัน)
                    "contrarian_bias": "SELL" if bull_ratio > 0.65 else ("BUY" if bull_ratio < 0.35 else "NEUTRAL")
                }
    except Exception as e:
        logger.debug(f"Myfxbook Sentiment error: {e}")
    return None

def _get_internal_sentiment(df):
    """คำนวณ Sentiment จาก Price Action ภายใน (ไม่ต้อง Internet)"""
    if df is None or len(df) < 20:
        return {"source": "Internal", "bias": "NEUTRAL", "contrarian_bias": "NEUTRAL", "long_pct": 50, "short_pct": 50}
    
    last = df.iloc[-1]
    # วัดว่าตลาดอยู่ในโซนไหนของ 20 แท่งล่าสุด
    high20 = df["high"].iloc[-20:].max()
    low20  = df["low"].iloc[-20:].min()
    rng    = high20 - low20
    
    if rng == 0:
        return {"source": "Internal", "bias": "NEUTRAL", "contrarian_bias": "NEUTRAL", "long_pct": 50, "short_pct": 50}
    
    pos_pct = (last["close"] - low20) / rng  # 0.0 (ล่างสุด) ถึง 1.0 (บนสุด)
    long_pct = round(pos_pct * 100, 1)
    short_pct = round((1 - pos_pct) * 100, 1)
    
    # ถ้าราคาอยู่สูงมาก → ค้างอยู่ที่ดอย → รายย่อย LONG กันเยอะ → Contrarian: SELL
    bias = "BULLISH" if pos_pct > 0.6 else ("BEARISH" if pos_pct < 0.4 else "NEUTRAL")
    contrarian = "SELL" if pos_pct > 0.75 else ("BUY" if pos_pct < 0.25 else "NEUTRAL")
    
    return {
        "source": "Internal (Price Action)",
        "long_pct": long_pct,
        "short_pct": short_pct,
        "bias": bias,
        "contrarian_bias": contrarian
    }

def get_market_sentiment(df=None):
    """
    Main Sentiment Aggregator
    พยายาม OANDA → Myfxbook → Internal (ตามลำดับ)
    Returns: dict with keys: source, long_pct, short_pct, bias, contrarian_bias, summary
    """
    # 1. ลอง OANDA ก่อน (ดีที่สุด แต่ต้องมี key)
    result = _get_oanda_sentiment()
    
    # 2. ลอง Myfxbook (ดีมาก ไม่ต้อง key)
    if result is None:
        result = _get_myfxbook_sentiment()
    
    # 3. ใช้ Internal ถ้าอินเตอร์เน็ตล่มหรือ API ไม่ตอบ
    if result is None:
        result = _get_internal_sentiment(df)
    
    # สร้างสรุปสั้นๆ สำหรับส่งให้ AI ดู
    contrarian = result.get("contrarian_bias", "NEUTRAL")
    src = result.get("source", "N/A")
    long_p = result.get("long_pct", 50)
    short_p = result.get("short_pct", 50)
    
    result["summary"] = f"Retail: {long_p}% Long / {short_p}% Short → Smart Money likely: {contrarian} [{src}]"
    
    logger.debug(f"[Sentiment] {result['summary']}")
    return result
