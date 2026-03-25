# strategy/ai_gatekeeper.py
import logging
import os
import requests
import re
from config import *

logger = logging.getLogger(__name__)

def clean_text(text: str) -> str:
    """ทำความสะอาดข้อความจาก AI - ลบตัวอักษรที่ Windows Console ไม่รองรับ"""
    if not text:
        return ""
    return text.encode('ascii', errors='replace').decode('ascii')


class AIGatekeeper:
    def __init__(self):
        self.qwen_key = QWEN_API_KEY if QWEN_API_KEY else None
        self.qwen_endpoint = QWEN_ENDPOINT if QWEN_ENDPOINT else None
        self.qwen_model = QWEN_MODEL if QWEN_MODEL else "qwen/qwen-plus"
        self.gemini_key = GEMINI_API_KEY if GEMINI_API_KEY else None
        self.gemini_model = GEMINI_MODEL if GEMINI_MODEL else "gemini-2.0-flash"
        if not self.qwen_key:
            logger.warning("[WARN] QWEN_API_KEY not set - Qwen will be skipped")
        if not self.gemini_key:
            logger.warning("[WARN] GEMINI_API_KEY not set - Gemini will be skipped")
        
    def validate_signal(self, market_state, signal_data) -> dict:
        if signal_data.get('direction') not in ["BUY", "SELL"]:
            return {
                "decision": "CONFIRM", 
                "confidence": 100, 
                "reason": "Not a trade signal",
                "provider": "skipped",
                "suggested_sl": None,
                "suggested_tp": None
            }
        if self.qwen_key:
            try:
                logger.debug("[BOT] Trying Qwen AI...")
                return self._call_qwen(market_state, signal_data)
            except QuotaExceededError:
                logger.debug("[WARN] Qwen quota exceeded, trying Gemini...")
            except Exception as e:
                logger.debug(f"[WARN] Qwen error: {type(e).__name__}, trying Gemini...")
        if self.gemini_key and FALLBACK_TO_SECONDARY:
            try:
                logger.debug("[BOT] Trying Gemini AI...")
                return self._call_gemini(market_state, signal_data)
            except QuotaExceededError:
                logger.debug("[WARN] Gemini quota exceeded, using fallback...")
            except Exception as e:
                logger.debug(f"[WARN] Gemini error: {type(e).__name__}, using fallback...")
        return self._fallback_silent()
    
    def _fallback_silent(self) -> dict:
        return {
            "decision": "CONFIRM",
            "confidence": FALLBACK_CONFIDENCE,
            "reason": "Technical analysis only",
            "provider": "fallback_silent",
            "suggested_sl": None,
            "suggested_tp": None
        }
    
    def _build_prompt(self, market_state, signal_data) -> str:
        return f"""You are a GOLD (XAU/USD) trading expert. Analyze this signal and suggest optimal SL/TP levels:

=== Market Data ===
• Price: {market_state.get('price')}
• HTF Trend: {market_state.get('htf_trend')}
• LTF Trend: {market_state.get('ltf_trend')}
• RSI: {market_state.get('rsi')}
• ATR: {market_state.get('atr')}
• Structure: {market_state.get('structure')}
• Swing Low: {market_state.get('swing_low')}
• Swing High: {market_state.get('swing_high')}
• EMA50: {market_state.get('ema50')}

=== Signal ===
• Direction: {signal_data.get('direction')}
• Pattern: {signal_data.get('pattern')}

=== Question ===
1. Should we enter this trade?
2. If CONFIRM, suggest the best Stop Loss and Take Profit levels based on the market structure.

=== RULES FOR SL/TP ===
• For BUY: SL must be BELOW the price, TP must be ABOVE the price.
• For SELL: SL must be ABOVE the price, TP must be BELOW the price.
• SL should be placed near a confirmed swing level with some ATR buffer.
• TP should aim for at least 1.5x the risk (distance from entry to SL).
• Use round numbers where possible.

=== IMPORTANT ===
 You MUST respond in ENGLISH ONLY
 Use EXACTLY this format (5 lines):

CONFIRM
Confidence: 85
Reason: RSI oversold with strong uptrend
SL: 3010.50
TP: 3035.00

OR

REJECT
Confidence: 45
Reason: RSI overbought, weak momentum
SL: 0
TP: 0

=== Response ===
"""
    
    def _call_qwen(self, market_state, signal_data) -> dict:
        prompt = self._build_prompt(market_state, signal_data)
        headers = {
            "Authorization": f"Bearer {self.qwen_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/bot-gold",
        }
        payload = {
            "model": self.qwen_model,
            "messages": [
                {"role": "system", "content": "You are a gold trading analyst. Respond concisely with trade decisions and SL/TP levels."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 200
        }
        response = requests.post(self.qwen_endpoint, headers=headers, json=payload, timeout=30)
        if response.status_code == 429:
            raise QuotaExceededError("Qwen quota exceeded")
        elif response.status_code == 401:
            raise Exception("Qwen API Key invalid")
        elif response.status_code != 200:
            raise Exception(f"Qwen API error: {response.status_code} - {response.text}")
        content = response.json()["choices"][0]["message"]["content"].strip()
        return self._parse_response(content, provider="qwen")
    
    def _call_gemini(self, market_state, signal_data) -> dict:
        import google.generativeai as genai
        prompt = self._build_prompt(market_state, signal_data)
        try:
            genai.configure(api_key=self.gemini_key)
            model = genai.GenerativeModel(self.gemini_model)
            response = model.generate_content(prompt)
            content = response.text.strip()
            return self._parse_response(content, provider="gemini")
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "quota" in error_str or "resource exhausted" in error_str:
                raise QuotaExceededError(f"Gemini quota exceeded: {e}")
            raise
    
    def _parse_response(self, text, provider) -> dict:
        """แยกข้อความจาก AI เป็น structured data (รวม SL/TP)"""
        
        # ทำความสะอาดข้อความก่อน parse
        text = clean_text(text)
        
        logger.debug(f"AI Raw Response: {text}")
        
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        decision, confidence, reason = "REJECT", 50, ""
        suggested_sl = None
        suggested_tp = None
        
        for line in lines:
            line_upper = line.upper()
            
            # หา CONFIRM/REJECT
            if "CONFIRM" in line_upper:
                decision = "CONFIRM"
            elif "REJECT" in line_upper:
                decision = "REJECT"
            
            # หา Confidence (รองรับหลายรูปแบบ)
            match = re.search(r'[Cc]onfidence[:\s]*(\d+)', line)
            if match:
                confidence = min(100, max(0, int(match.group(1))))
            
            # หา SL (รองรับหลายรูปแบบ: "SL: 3010.50", "Stop Loss: 3010.50")
            sl_match = re.search(r'(?:SL|Stop\s*Loss)[:\s]*([\d]+\.?\d*)', line, re.IGNORECASE)
            if sl_match:
                val = float(sl_match.group(1))
                if val > 0:  # ไม่เอา SL: 0
                    suggested_sl = val
            
            # หา TP (รองรับหลายรูปแบบ: "TP: 3035.00", "Take Profit: 3035.00")
            tp_match = re.search(r'(?:TP|Take\s*Profit)[:\s]*([\d]+\.?\d*)', line, re.IGNORECASE)
            if tp_match:
                val = float(tp_match.group(1))
                if val > 0:  # ไม่เอา TP: 0
                    suggested_tp = val
            
            # หา Reason (รองรับหลายรูปแบบ)
            if "reason" in line.lower():
                parts = line.split(':', 1)
                if len(parts) > 1:
                    reason = parts[1].strip()
                else:
                    reason = line
        
        # ถ้า reason ยังว่าง -> ใช้ข้อความทั้งหมดที่ไม่ใช่ decision/confidence/sl/tp
        if not reason:
            reason = ' '.join([l for l in lines if 'confidence' not in l.lower() 
                            and 'confirm' not in l.lower() 
                            and 'reject' not in l.lower()
                            and not re.match(r'(?:SL|TP|Stop|Take)', l, re.IGNORECASE)])
        
        logger.debug(f"Parsed: decision={decision}, confidence={confidence}, reason={reason}, sl={suggested_sl}, tp={suggested_tp}")
        
        # ถ้า REJECT -> ไม่ส่ง SL/TP
        if decision == "REJECT":
            suggested_sl = None
            suggested_tp = None
        
        return {
            "decision": decision,
            "confidence": confidence,
            "reason": reason if reason else "No reason provided",
            "provider": provider,
            "suggested_sl": suggested_sl,
            "suggested_tp": suggested_tp
        }

class QuotaExceededError(Exception):
    pass

gatekeeper = AIGatekeeper()