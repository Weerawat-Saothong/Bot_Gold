import platform
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =========================
# AUTO DETECT PLATFORM
# =========================

if platform.system() == "Windows":
    BASE_PATH = "C:\\Program Files\\MetaTrader 5 - Joe\\MQL5\\Files\\"
    IS_ANALYSIS_MODE = False
else:
    BASE_PATH = "/Users/x10/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files/"
    IS_ANALYSIS_MODE = True

# =========================
# FILE PATHS
# =========================

PATH_M5 = BASE_PATH + "market_data_m5.csv"
PATH_H1 = BASE_PATH + "market_data_h1.csv"
PATH_SIGNAL = BASE_PATH + "signal.txt"
PATH_POSITION = BASE_PATH + "position.txt"
PATH_POSITIONS_JSON = BASE_PATH + "positions.json"

# =========================
# BOT SETTINGS
# =========================

MAX_POSITIONS = 3       # จำนวนไม้สูงสุด (แนะนำ 3 สำหรับ Balanced)
COOLDOWN_SECONDS = 15   # ระยะเวลารอระหว่างไม้

# =========================
# MONITORING & ALERTS
# =========================
BASE_LOT = 0.01                 # ล๊อตเริ่มต้นปกติ
RISK_PER_TRADE_USD = 10.0        # ยอมเสียสูงสุด $10 ต่อไม้ (ปรับได้ตามพอร์ต)

HIGH_CONFIDENCE_LOT = 0.02      # ล๊อตเมื่อ AI มั่นใจเกิน 90%

# =========================
# EA RISK LOGIC (Trailing & Breakeven)
# =========================
USE_TRAILING_STOP = False
USE_BREAKEVEN = False    

TRAILING_START = 30.0    
TRAILING_STEP = 5.0      
BREAKEVEN_START = 20.0   

# =========================
# SAFETY FILTERS
# =========================
STRICT_TREND_FILTER = True  # ห้ามสวนเทรนด์เมื่อ EMA ชันมากๆ
MAX_EMA_SLOPE = 0.2         # ปรับจาก 0.5 เป็น 0.2 (สมดุลขึ้น)
MAX_EMA_ATR_DISTANCE = 4.0   # ปรับจาก 8.0 เป็น 4.0 (ป้องกันปลายยอด)

# =========================
# SIGNAL FILTERS (Balanced Mode)
# =========================

# Time Filter (Broker Time)
TRADE_START_HOUR = 0
TRADE_END_HOUR = 23

# RSI Safe Zone (More Selective for Higher Winrate)
RSI_BUY_MIN = 40       
RSI_BUY_MAX = 70       
RSI_SELL_MIN = 30      
RSI_SELL_MAX = 60      

# Volatility Filter (Middle Ground)
MAX_ATR_LIMIT = 20.0    # เพิ่มจาก 15 เพื่อรองรับตลาดทองผันผวนสูง (ATR 10-15 ปกติในช่วง trend แรง)

# =========================
# BLACK SWAN (MOMENTUM) MODE
# =========================
ENABLE_BLACK_SWAN = True      
BLACK_SWAN_ATR_MIN = 10.0     # ลดจาก 12 เพื่อให้ trigger ง่ายขึ้น
BLACK_SWAN_RSI_SELL = 25      # เพิ่มจาก 13 (RSI ต่ำกว่า 13 แทบไม่มีทางเกิด)
BLACK_SWAN_RSI_BUY = 75        # ลดจาก 85 เพื่อให้ trigger ได้ง่ายขึ้น


# =========================
# AI SETTINGS
# =========================

MIN_SL_DISTANCE = 2.0
TRADE_COOLDOWN = 3
LOSS_COOLDOWN = 5

# =========================
# TRADING LIMITS
# =========================

MAX_TRADES_PER_DAY = 100
DAILY_RISK_PERCENT = 0.10

# =========================
# SIGNAL SETTINGS
# =========================

MIN_DISTANCE_FOR_SIGNAL = 0.1   # ลดจาก 0.5 เพื่อให้เข้าได้ใกล้ EMA มากขึ้น
ATR_VOLATILITY_MULTIPLIER = 1.0
ATR_MIN_VOLATILITY = 0.8        # ลดจาก 1.2 เพื่อให้เทรดได้ในตลาดปกติ
CANDLE_RANGE_THRESHOLD = 80     # เพิ่มจาก 30 เพื่อรองรับแท่งเทียนที่ใหญ่ขึ้นในทองคำ
MARKET_STRUCTURE_PERIOD = 5
LIQUIDITY_LOOKBACK = 14         # ปรับจาก 21 เพื่อให้หาจุด Sweep ได้เร็วขึ้น

# =========================
# NEWS FILTER SETTINGS
# =========================
USE_NEWS_FILTER = True
NEWS_WAIT_MINUTES = 30  # Stop trading 30 min before/after high-impact news
NEWS_CURRENCY = "USD"
NEWS_IMPACT = "high"

# =========================
# AI GATEKEEPER SETTINGS (Free Maximizer)
# =========================
USE_AI_GATEKEEPER = True
AI_CONFIDENCE_THRESHOLD = 70

# 🔄 Fallback Order: Qwen (ฟรี) → Gemini (ฟรี) → 70% (เงียบ)
AI_PRIMARY = "qwen"
AI_SECONDARY = "gemini"

# 🔴 Qwen Settings (ผ่าน OpenRouter - มีฟรีเครดิต)
QWEN_MODEL = "qwen/qwen-plus"  # หรือ "qwen/qwen-turbo" (ถูกกว่า)
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
QWEN_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

# 🟣 Gemini Settings (ฟรี 100%)
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_API_KEY = os.getenv("AI_API_KEY", "")

# ⚙️ Fallback Behavior
FALLBACK_TO_SECONDARY = True      # ถ้า Qwen หมด → ไป Gemini
FALLBACK_CONFIDENCE = 70          # ถ้าทั้งคู่หมด → ใช้ค่านี้
SILENT_FALLBACK = True            # ไม่ log เมื่อใช้ fallback สุดท้าย

# =========================
# OVEREXTENDED FILTER (PREVENT PEAK/BOTTOM ENTRY)
# =========================
MAX_EMA_ATR_DISTANCE = 5.0      # ถ้าห่างจาก EMA50 เกิน 5.0 เท่าของ ATR บอทจะหยุดเข้าไม้ (ป้องกันปลายไส้)
