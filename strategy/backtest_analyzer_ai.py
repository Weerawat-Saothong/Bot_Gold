import pandas as pd
import os
import logging
import json
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()
AI_API_KEY = os.getenv("AI_API_KEY")
AI_MODEL_NAME = os.getenv("AI_MODEL_NAME", "gemini-2.0-flash")

if AI_API_KEY:
    genai.configure(api_key=AI_API_KEY)

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BacktestAIAnalyzer:
    def __init__(self, csv_path="trades_analysis.csv"):
        self.csv_path = csv_path
        self.active_ai = AI_API_KEY is not None
        if self.active_ai:
            self.model = genai.GenerativeModel(AI_MODEL_NAME)
        
    def load_data(self):
        if not os.path.exists(self.csv_path):
            logger.error(f"File {self.csv_path} not found.")
            return None
        return pd.read_csv(self.csv_path)

    def analyze_losses(self, df):
        """
        วิเคราะห์ไม้ที่ขาดทุนมากที่สุด 5 อันดับแรก
        """
        losses = df[df['result'] == 'LOSS'].sort_values('profit').head(5)
        
        analysis_prompts = []
        for _, row in losses.iterrows():
            prompt = f"""
            [Trade Loss Analysis]
            - Time: {row['entry_time']}
            - Type: {row['type']}
            - Entry: {row['entry']}
            - Exit: {row['exit']}
            - PnL: {row['profit']}
            - RSI: {row['rsi']:.2f}
            - ATR: {row['atr']:.2f}
            
            คำถาม: ทำไมไม้ถึงแพ้? และเราควรเพิ่ม Filter อะไรเพื่อเลี่ยงไม้นี้ในอนาคต?
            """
            analysis_prompts.append(prompt)
        
        return analysis_prompts

    def generate_report(self):
        df = self.load_data()
        if df is None: return
        
        total_trades = len(df)
        wins = len(df[df['result'] == 'WIN'])
        losses = len(df[df['result'] == 'LOSS'])
        total_pnl = df['profit'].sum()
        winrate = (wins / total_trades) * 100 if total_trades > 0 else 0
        
        print("\n" + "="*50)
        print("🤖 AI BACKTEST PERFORMANCE REPORT")
        print("="*50)
        print(f"Total Trades : {total_trades}")
        print(f"Win Rate     : {winrate:.2f}%")
        print(f"Total PnL    : {total_pnl:.2f}")
        print("-"*50)
        
        print("\n🔍 AI DEEP DIVE: LOSS ANALYSIS")
        prompts = self.analyze_losses(df)
        
        for i, prompt in enumerate(prompts):
            print(f"\n[Case {i+1}]")
            # print(prompt.strip()) # Hide prompt for cleaner output
            
            if self.active_ai:
                import time
                try:
                    # Rate limit for free tier
                    if i > 0:
                        print("... Waiting for API quota reset (20s) ...")
                        time.sleep(20)
                    
                    response = self.model.generate_content(prompt)
                    print(f">> AI Analysis: {response.text.strip()}")
                except Exception as e:
                    print(f">> AI Error: {e}")
            else:
                print(">> AI Feedback (Offline): Please configure AI_API_KEY in .env to get live analysis.")
        
        print("\n" + "="*50)
        print("💡 STRATEGY SUGGESTION")
        print("- เพิ่ม Volume Filter เพื่อเลี่ยงช่วงตลาดซึม")
        print("- ปรับค่า RSI Sell Max ให้เข้มงวดขึ้นเมื่อ ATR ต่ำกว่า 2.0")
        print("="*50 + "\n")

if __name__ == "__main__":
    analyzer = BacktestAIAnalyzer()
    analyzer.generate_report()
