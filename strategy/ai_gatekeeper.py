import logging
import json
import google.generativeai as genai
from config import AI_API_KEY, AI_MODEL_NAME, IS_ANALYSIS_MODE

logger = logging.getLogger(__name__)

class AIGatekeeper:
    def __init__(self):
        if AI_API_KEY and AI_API_KEY != "YOUR_API_KEY_HERE":
            genai.configure(api_key=AI_API_KEY)
            self.model = genai.GenerativeModel(AI_MODEL_NAME)
            self.active = True
            logger.info(f"AI Gatekeeper initialized with model: {AI_MODEL_NAME}")
        else:
            self.active = False
            logger.warning("AI Gatekeeper is disabled: No valid API Key found.")

    def generate_prompt(self, market_state, signal_data):
        """
        สร้าง Prompt เพื่อส่งให้ AI วิเคราะห์
        """
        prompt = f"""
        คุณคือผู้เชี่ยวชาญด้านการเทรดทองคำ (XAUUSD Quant Trader) ระดับโลก
        หน้าที่ของคุณคือวิเคราะห์ข้อมูลตลาดปัจจุบันและตัดสินใจว่าควร "ยืนยัน" (CONFIRM) หรือ "ปฏิเสธ" (REJECT) สัญญาณเทรดที่ตรวจพบจากบอทเทคนิค
        
        [ข้อมูลตลาดปัจจุบัน]
        - ราคาปัจจุบัน: {market_state['price']}
        - เทรนด์ระดับชั่วโมง (H1): {market_state['htf_trend']} (EMA50 vs EMA200)
        - เทรนด์ล่าสุด (M5): {market_state['ltf_trend']} (EMA50 vs EMA200)
        - RSI (M5): {market_state['rsi']}
        - ความผันผวน (ATR): {market_state['atr']}
        - โครงสร้างตลาด: {market_state['structure']}
        
        [สัญญาณที่ตรวจพบ]
        - ทิศทาง: {signal_data['direction']}
        - รูปแบบทางเทคนิค: {signal_data['pattern']}
        
        [กฎการตัดสินใจ]
        1. หากสวนเทรนด์หลัก (H1) และราคาอยู่ในโซนอันตราย ให้ REJECT
        2. หาก RSI ตึงเกินไป (Overbought/Oversold) โดยไม่มีแรงส่งเพียงพอ ให้ REJECT
        3. หากทุกอย่างสอดคล้องกัน ให้ CONFIRM ด้วยความมั่นใจสูง
        
        [คำสั่ง]
        ให้ตอบกลับในรูปแบบ JSON ที่ถูกต้องเท่านั้น (Strict JSON format):
        {{
            "decision": "CONFIRM" หรือ "REJECT",
            "confidence": 0-100,
            "reason": "อธิบายเหตุผลสั้นๆ เป็นภาษาไทย"
        }}
        """
        return prompt

    def validate_signal(self, market_state, signal_data):
        """
        ส่งข้อมูลให้ AI และรับผลการตัดสินใจจริง
        """
        if not self.active:
            return {"decision": "CONFIRM", "confidence": 100, "reason": "AI Disabled (Using Technical Only)"}

        prompt = self.generate_prompt(market_state, signal_data)
        
        try:
            response = self.model.generate_content(prompt)
            # พยายามดึง JSON ออกจากคำตอบของ AI
            text_response = response.text.strip()
            # ตัดเครื่องหมาย ```json ... ``` ออกถ้ามี
            if "```json" in text_response:
                text_response = text_response.split("```json")[1].split("```")[0].strip()
            elif "```" in text_response:
                text_response = text_response.split("```")[1].split("```")[0].strip()
            
            result = json.loads(text_response)
            logger.info(f"AI Response: {result['decision']} ({result['confidence']}%) - {result['reason']}")
            return result
        except Exception as e:
            logger.error(f"AI Gatekeeper Error: {e}")
            # กรณี Error ให้ปล่อยผ่านแบบ Technical ไปก่อนเพื่อความปลอดภัย
            return {"decision": "CONFIRM", "confidence": 50, "reason": "AI Error, following technical signal"}

# Global instance
gatekeeper = AIGatekeeper()
