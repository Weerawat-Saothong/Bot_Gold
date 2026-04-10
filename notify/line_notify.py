import requests
import os
import logging
import sys
import io
from dotenv import load_dotenv

# Fix Windows Encoding Error for Emojis
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Load environment variables
load_dotenv()

# Logger setup
logger = logging.getLogger(__name__)

def send_line(msg):
    """
    Unified notification engine. 
    Supports LINE Messaging API (Broadcast) and Telegram.
    """
    try:
        import config
        NOTIFY_PROVIDER = getattr(config, 'NOTIFY_PROVIDER', 'DISABLED')
        SKIP_NON_URGENT = getattr(config, 'SKIP_NON_URGENT', False)
        TELEGRAM_TOKEN = getattr(config, 'TELEGRAM_TOKEN', '')
        TELEGRAM_CHAT_ID = getattr(config, 'TELEGRAM_CHAT_ID', '')
        line_token = os.getenv("LINE_TOKEN")
    except ImportError as e:
        # Fallback if config not ready
        logger.error(f"Config import error: {e}")
        return

    # Skip non-essential messages if configured
    if SKIP_NON_URGENT and any(word in msg for word in ["[INFO]", "Status : ONLINE", "Market Closed"]):
        logger.info("Skipping non-urgent notification to save quota.")
        return

    if NOTIFY_PROVIDER == "DISABLED":
        return

    # --- 1. TELEGRAM (FREE & UNLIMITED) ---
    if NOTIFY_PROVIDER == "TELEGRAM":
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            logger.error("Telegram credentials missing in .env")
            return
        
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
        
        try:
            r = requests.post(url, json=data, timeout=10)
            if r.status_code == 200:
                print("✨ Notification sent successfully to Telegram!")
            else:
                logger.error(f"Telegram error: {r.status_code} {r.text}")
        except Exception as e:
            logger.error(f"Telegram exception: {e}")

    # --- 2. LINE MESSAGING API (BROADCAST) ---
    elif NOTIFY_PROVIDER == "LINE_MESSAGING":
        if not line_token:
            logger.error("LINE_TOKEN missing in .env")
            return

        url = "https://api.line.me/v2/bot/message/broadcast"
        headers = {
            "Authorization": f"Bearer {line_token}",
            "Content-Type": "application/json"
        }
        data = {
            "messages": [{"type": "text", "text": msg}]
        }

        try:
            r = requests.post(url, headers=headers, json=data, timeout=15)
            if r.status_code == 429:
                logger.warning("LINE Limit Reached! Switching to Telegram or upgrading plan recommended.")
            elif r.status_code != 200:
                logger.error(f"LINE error: {r.status_code} {r.text}")
        except Exception as e:
            logger.error(f"LINE exception: {e}")
