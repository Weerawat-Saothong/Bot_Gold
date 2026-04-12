import pandas as pd
import os
import logging
import platform
from config import PATH_M5, PATH_H1, SYMBOL

logger = logging.getLogger(__name__)

# Try to import MT5 for Windows internal usage
mt5 = None
if platform.system() == "Windows":
    try:
        import MetaTrader5 as mt5
    except ImportError:
        logger.warning("MetaTrader5 library not found. Falling back to CSV mode.")

def load_from_mt5(timeframe, bars=2000):
    """ดึงข้อมูลจาก MT5 โดยตรง (Windows Only)"""
    if mt5 is None: return None
    
    try:
        # Map Timeframes
        tf = mt5.TIMEFRAME_M5 if timeframe == "M5" else mt5.TIMEFRAME_H1
        
        rates = mt5.copy_rates_from_pos(SYMBOL, tf, 0, bars)
        if rates is None or len(rates) == 0:
            return None
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df = df[['time', 'open', 'high', 'low', 'close', 'tick_volume']]
        df.columns = ['time', 'open', 'high', 'low', 'close', 'volume']
        return df
    except Exception as e:
        logger.error(f"MT5 Direct link error: {e}")
        return None

def load_file_csv(path):
    """ดึงข้อมูลจากไฟล์ CSV (Fallback Mode)"""
    try:
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            return None

        df = pd.read_csv(path, sep="\t", header=None)
        if df.empty: return None

        if len(df.columns) == 6:
            df.columns = ["time","open","high","low","close","volume"]
        elif len(df.columns) == 5:
            df.columns = ["time","open","high","low","close"]
            df["volume"] = 1
        else: return None

        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time").reset_index(drop=True)
        return df
    except Exception as e:
        logger.debug(f"CSV read skip: {e}")
        return None

def get_market_data():
    """ลูกผสม: พยายามต่อตรงก่อน ถ้าไม่ได้ให้อ่านไฟล์"""
    # 1. พยายามต่อท่อตรง (MT5 Direct)
    df = load_from_mt5("M5")
    if df is not None: return df
    
    # 2. ถ้าต่อตรงไม่ได้ (เช่น อยู่บน Mac หรือ MT5 ปิด) ให้อ่านไฟล์ CSV
    return load_file_csv(PATH_M5)

def get_market_data_htf():
    """ลูกผสม HTF"""
    df = load_from_mt5("H1")
    if df is not None: return df
    
    return load_file_csv(PATH_H1)
