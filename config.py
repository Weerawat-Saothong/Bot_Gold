import platform
import os
from dotenv import load_dotenv

load_dotenv()

# =========================
# 🏗️ AUTO DETECT PLATFORM
# =========================
if platform.system() == "Windows":
    BASE_PATH = "C:\\Program Files\\MetaTrader 5 - Joe\\MQL5\\Files\\"
    IS_ANALYSIS_MODE = False
else:
    # Path สำหรับ Mac (Wine/Crossover) - กรุณาตรวจสอบให้ตรงกับเครื่องบอส
    BASE_PATH = "/Users/x10/Documents/gold/" # แก้ให้ตรงกับ Folder งานหลัก
    IS_ANALYSIS_MODE = True

# =========================
# 📂 FILE PATHS
# =========================
PATH_M5 = BASE_PATH + "market_data_m5.csv"
PATH_H1 = BASE_PATH + "market_data_h1.csv"
PATH_SIGNAL = BASE_PATH + "signal.txt"
PATH_POSITION = BASE_PATH + "position.txt"
PATH_POSITIONS_JSON = BASE_PATH + "positions.json"

# =========================
# 💰 TRADING & LOTS
# =========================
MAX_POSITIONS = 3           # จำนวนไม้สูงสุด
BASE_LOT = 0.02              # ล็อตเริ่มต้น
USE_DYNAMIC_LOT = True       # ใช้ระบบคำนวณล็อตตามความเชื่อมั่น AI
MIN_LOT = 0.01
MAX_LOT = 0.04               # ปรับเพิ่มเพดานให้นิดหน่อยสำหรับไม้เทพ
RISK_PER_TRADE_USD = 15.0    # ยอมเสียสูงสุด $15 ต่อไม้

# =========================
# 🛡️ PREDATORY RISK SETTINGS
# =========================
RR_RATIO = 2.0               # เป้าหมายกำไรขั้นต่ำ 1:2 (Institutional Standard)
ATR_SL_BUFFER = 0.8          # ระยะเผื่อ SL (0.8 ถึง 1.5 ATR กำลังดีสำหรับทอง)
MIN_SL_DISTANCE = 1.5        # ระยะ SL ขั้นต่ำ (ไม่ให้ใกล้จนโดนสะบัด)

# =========================
# 🛸 EA LOGIC (TRAILING/BE)
# =========================
USE_TRAILING_STOP = False
USE_BREAKEVEN = True         # แนะนำให้เปิดไว้สำหรับทอง
BREAKEVEN_START = 15.0       # เริ่มกันทุนที่กำไร +$15
BREAKEVEN_PROFIT = 5.0       # ล็อกกำไรไว้ที่ +$5

# =========================
# 🧠 AI GATEKEEPER (THE GUARD)
# =========================
USE_AI_GATEKEEPER = True
AI_CONFIDENCE_THRESHOLD = 50 # เพิ่มความเข้มงวดให้ถึง 50%
SUPPRESS_API_ERRORS = False

# [KEYS] - ดึงจาก Environment
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "") or os.getenv("AI_API_KEY", "")
QWEN_MODEL = "qwen/qwen-plus"
QWEN_FREE_MODEL = "qwen/qwen3.6-plus-preview:free"
QWEN_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
GEMINI_MODEL = "gemini-2.0-flash"

# AI Fallback Chain
AI_PRIMARY = "qwen"
AI_SECONDARY = "gemini"
FALLBACK_TO_SECONDARY = True
FALLBACK_CONFIDENCE = 60
SILENT_FALLBACK = True

# =========================
# 🦈 PREDATORY FILTERS (SMC)
# =========================
STRICT_TREND_FILTER = True
MAX_EMA_SLOPE = 0.3
MAX_EMA_ATR_DISTANCE = 4.5
LIQUIDITY_LOOKBACK = 20

# =========================
# ⏰ TIME & NEWS
# =========================
USE_NEWS_FILTER = True
NEWS_WAIT_MINUTES = 45
MAX_TRADES_PER_DAY = 50
TRADE_COOLDOWN = 1
LOSS_COOLDOWN = 30
COOLDOWN_SECONDS = 15
DAILY_RISK_PERCENT = 0.10

# =========================
# 🚨 MONITORING
# =========================
NOTIFY_LEVEL = "INFO"          # "INFO" (All), "TRADE" (Only trades), "ERROR" (Only errors)
NOTIFY_PROVIDER = "TELEGRAM" # "LINE_MESSAGING", "TELEGRAM", "DISABLED"
SKIP_NON_URGENT = False        # Set True to skip daily reports/online status to save quota

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

