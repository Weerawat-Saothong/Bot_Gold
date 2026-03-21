# strategy/ai_gatekeeper.py
import logging
import os
import requests
import re
from config import *

logger = logging.getLogger(__name__)

class AIGatekeeper:
    def __init__(self):
        self.qwen_key = QWEN_API_KEY if QWEN_API_KEY else None
        self.qwen_endpoint = QWEN_ENDPOINT if QWEN_ENDPOINT else None
        self.qwen_model = QWEN_MODEL if QWEN_MODEL else "qwen/qwen-plus"
        self.gemini_key = GEMINI_API_KEY if GEMINI_API_KEY else None
        self.gemini_model = GEMINI_MODEL if GEMINI_MODEL else "gemini-2.0-flash"
        if not self.qwen_key:
            logger.warning("⚠️ QWEN_API_KEY not set - Qwen will be skipped")
        if not self.gemini_key:
            logger.warning("⚠️ GEMINI_API_KEY not set - Gemini will be skipped")
        
    def validate_signal(self, market_state, signal_data) -> dict:
        if signal_data.get('direction') not in ["BUY", "SELL"]:
            return {
                "decision": "CONFIRM", 
                "confidence": 100, 
                "reason": "Not a trade signal",
                "provider": "skipped"
            }
        if self.qwen_key:
            try:
                logger.debug("🤖 Trying Qwen AI...")
                return self._call_qwen(market_state, signal_data)
            except QuotaExceededError:
                logger.debug("⚠️ Qwen quota exceeded, trying Gemini...")
            except Exception as e:
                logger.debug(f"⚠️ Qwen error: {type(e).__name__}, trying Gemini...")
        if self.gemini_key and FALLBACK_TO_SECONDARY:
            try:
                logger.debug("🤖 Trying Gemini AI...")
                return self._call_gemini(market_state, signal_data)
            except QuotaExceededError:
                logger.debug("⚠️ Gemini quota exceeded, using fallback...")
            except Exception as e:
                logger.debug(f"⚠️ Gemini error: {type(e).__name__}, using fallback...")
        return self._fallback_silent()
    
    def _fallback_silent(self) -> dict:
        return {
            "decision": "CONFIRM",
            "confidence": FALLBACK_CONFIDENCE,
            "reason": "Technical analysis only",
            "provider": "fallback_silent"
        }
    
    def _build_prompt(self, market_state, signal_data) -> str:
        return f"""คุณเป็นผู้เชี่ยวชาญการเทรดทองคำ (XAU/USD) โปรดวิเคราะห์สัญญาณต่อไปนี้:

=== ข้อมูลตลาด ===
• ราคา: {market_state.get('price')}
• แนวโน้มใหญ่ (HTF): {market_state.get('htf_trend')}
• แนวโน้มเล็ก (LTF): {market_state.get('ltf_trend')}
• RSI: {market_state.get('rsi')}
• ATR: {market_state.get('atr')}
• โครงสร้าง: {market_state.get('structure')}

=== สัญญาณ ===
• ทิศทาง: {signal_data.get('direction')}
• รูปแบบ: {signal_data.get('pattern')}

=== คำถาม ===
ควรเข้าเทรดตามสัญญาณนี้หรือไม่?

=== รูปแบบคำตอบ ===
ตอบแค่ 3 บรรทัด:
1. CONFIRM หรือ REJECT
2. Confidence: 0-100
3. Reason: เหตุผลสั้นๆ 1 ประโยค
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
                {"role": "system", "content": "คุณเป็นผู้ช่วยวิเคราะห์การเทรดทองคำ ตอบสั้นๆ ตรงประเด็น"},
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
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        decision, confidence, reason = "REJECT", 50, ""
        for line in lines:
            if "CONFIRM" in line.upper():
                decision = "CONFIRM"
            elif "REJECT" in line.upper():
                decision = "REJECT"
            match = re.search(r'[Cc]onfidence[:\s]*(\d+)', line)
            if match:
                confidence = min(100, max(0, int(match.group(1))))
            if "reason" in line.lower() or "เพราะ" in line.lower():
                reason = line.split(':', 1)[-1].strip() if ':' in line else line
        return {
            "decision": decision,
            "confidence": confidence,
            "reason": reason,
            "provider": provider
        }

class QuotaExceededError(Exception):
    pass

gatekeeper = AIGatekeeper()