import platform

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
# EA RISK LOGIC (Trailing & Breakeven)
# =========================
USE_TRAILING_STOP = False  # 🔥 ปิดไว้ก่อนเพราะทำให้กำไรลดลง (เปลี่ยนเป็น True เพื่อเปิด)
USE_BREAKEVEN = False      # 🔥 ปิดไว้ก่อน

TRAILING_START = 5.0    
TRAILING_STEP = 1.0     
BREAKEVEN_START = 3.0   

# =========================
# SIGNAL FILTERS (Balanced Mode)
# =========================

# Time Filter (Broker Time)
TRADE_START_HOUR = 10
TRADE_END_HOUR = 21

# RSI Safe Zone (Optimized for more entries)
RSI_BUY_MIN = 40       
RSI_BUY_MAX = 80       
RSI_SELL_MIN = 20      
RSI_SELL_MAX = 60      

# Volatility Filter
MAX_ATR_LIMIT = 10.0   

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
AI_API_KEY = "AIzaSyCr_6PgLDrjHqxWnAEoezGkcIGx1XwPIXw"
