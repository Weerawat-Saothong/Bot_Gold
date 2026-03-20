import logging
import json
import re
import google.generativeai as genai
from config import AI_API_KEY, AI_MODEL_NAME, IS_ANALYSIS_MODE, AI_CONFIDENCE_THRESHOLD

logger = logging.getLogger(__name__)

class AIGatekeeper:
    def __init__(self):
        if AI_API_KEY and AI_API_KEY != "YOUR_API_KEY_HERE":
            genai.configure(api_key=AI_API_KEY)
            self.model = genai.GenerativeModel(
                model_name=AI_MODEL_NAME,
                generation_config={"response_mime_type": "application/json"}
            )
            self.active = True
            logger.info(f"AI Gatekeeper initialized with model: {AI_MODEL_NAME} (JSON Mode Enabled)")
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
        ตอบกลับเป็น JSON OBJECT เท่านั้น ห้ามเขียนเนื้อหาอื่นนอกเหนือจาก JSON:
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
            return {"decision": "CONFIRM", "confidence": 70, "reason": "AI Disabled"}

        prompt = self.generate_prompt(market_state, signal_data)
        
        try:
            response = self.model.generate_content(prompt)
            text_response = response.text.strip()
            
            # Robust JSON cleaning using regex
            # Find the first '{' and the last '}'
            match = re.search(r'\{.*\}', text_response, re.DOTALL)
            if match:
                json_str = match.group(0)
            else:
                json_str = text_response

            result = json.loads(json_str)
            
            # Validate essential keys
            if 'decision' not in result or 'confidence' not in result:
                raise ValueError("Missing essential keys in AI JSON response")

            logger.info(f"AI Decision: {result['decision']} ({result['confidence']}%) - {result.get('reason', 'N/A')}")
            return result
            
        except Exception as e:
            logger.error(f"AI Gatekeeper Error (Quota/Parsing): {e}")
            if 'text_response' in locals():
                logger.error(f"Raw AI Response: {text_response}")
            
            # Fallback: ปล่อยผ่านด้วยความมั่นใจ 70 (ตามที่ผู้ใช้กำหนด สำหรับช่วง AI ติดโควตา)
            return {
                "decision": "CONFIRM", 
                "confidence": 70, 
                "reason": f"AI Error/Quota ({str(e)[:30]}), Following Technical"
            }

# Global instance
gatekeeper = AIGatekeeper()

