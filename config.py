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

TRAILING_START = 25.0    # แก้จาก 5.0 เป็น 25.0 ($25)
TRAILING_STEP = 5.0      # แก้จาก 1.0 เป็น 5.0 ($5)
BREAKEVEN_START = 15.0   # แก้จาก 3.0 เป็น 15.0 ($15)

# =========================
# SAFETY FILTERS
# =========================
STRICT_TREND_FILTER = True  # ห้ามสวนเทรนด์เมื่อ EMA ชันมากๆ
MAX_EMA_SLOPE = 0.1         # แก้จาก 1.0 เป็น 0.1 (เข้มงวดขึ้น 10 เท่า)
MAX_EMA_ATR_DISTANCE = 5.0   # ระยะห่าง EMA สูงสุด (ATR)

# =========================
# SIGNAL FILTERS (Balanced Mode)
# =========================

# Time Filter (Broker Time)
TRADE_START_HOUR = 0
TRADE_END_HOUR = 23

# RSI Safe Zone (Middle Ground - More Aggressive)
RSI_BUY_MIN = 30       
RSI_BUY_MAX = 90       
RSI_SELL_MIN = 10      
RSI_SELL_MAX = 70      

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

MIN_DISTANCE_FOR_SIGNAL = 0.5
ATR_VOLATILITY_MULTIPLIER = 1.05
ATR_MIN_VOLATILITY = 1.2
CANDLE_RANGE_THRESHOLD = 30
MARKET_STRUCTURE_PERIOD = 5
LIQUIDITY_LOOKBACK = 21

# =========================
# NEWS FILTER SETTINGS
# =========================
USE_NEWS_FILTER = True
NEWS_WAIT_MINUTES = 30  # Stop trading 30 min before/after high-impact news
NEWS_CURRENCY = "USD"
NEWS_IMPACT = "high"

# =========================
# AI GATEKEEPER SETTINGS
# =========================
USE_AI_GATEKEEPER = True
AI_CONFIDENCE_THRESHOLD = 70
AI_MODEL_NAME = "gemini-2.0-flash"
AI_API_KEY = os.getenv("AI_API_KEY", "YOUR_API_KEY_HERE")

# =========================
# OVEREXTENDED FILTER (PREVENT PEAK/BOTTOM ENTRY)
# =========================
MAX_EMA_ATR_DISTANCE = 5.0      # ถ้าห่างจาก EMA50 เกิน 5.0 เท่าของ ATR บอทจะหยุดเข้าไม้ (ป้องกันปลายไส้)
