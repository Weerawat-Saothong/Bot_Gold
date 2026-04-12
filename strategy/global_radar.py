import yfinance as yf
import logging
import math
import pandas as pd

logger = logging.getLogger(__name__)

def get_global_market_status():
    """ดึงข้อมูล DXY และ OIL เพื่อประเมินทิศทางตลาดโลก"""
    results = {
        "dxy_price": None, "dxy_change": 0, "dxy_vibe": "NEUTRAL",
        "oil_price": None, "oil_change": 0, "oil_vibe": "NEUTRAL"
    }
    
    try:
        # 1. Check DXY (Dollar Index)
        dxy_tickers = ["DX-Y.NYB", "UUP", "^DXY"]
        for t in dxy_tickers:
            try:
                ticker = yf.Ticker(t)
                hist = ticker.history(period="2d")
                if not hist.empty and len(hist) >= 2:
                    curr = hist['Close'].iloc[-1]
                    prev = hist['Close'].iloc[-2]
                    if not math.isnan(curr):
                        results["dxy_price"] = round(curr, 2)
                        results["dxy_change"] = ((curr - prev) / prev) * 100
                        if results["dxy_change"] > 0.15: results["dxy_vibe"] = "STRONG"
                        elif results["dxy_change"] < -0.15: results["dxy_vibe"] = "WEAK"
                        break
            except: continue
            
        # 2. Check Oil (WTI Crude)
        oil = yf.Ticker("CL=F")
        oil_hist = oil.history(period="2d")
        if not oil_hist.empty and len(oil_hist) >= 2:
            curr_oil = oil_hist['Close'].iloc[-1]
            prev_oil = oil_hist['Close'].iloc[-2]
            if not math.isnan(curr_oil):
                results["oil_price"] = round(curr_oil, 2)
                results["oil_change"] = ((curr_oil - prev_oil) / prev_oil) * 100
                if results["oil_change"] > 1.0: results["oil_vibe"] = "STRONG"
                elif results["oil_change"] < -1.0: results["oil_vibe"] = "WEAK"
                
    except Exception as e:
        logger.error(f"Global Radar Error: {e}")
        
    return results
