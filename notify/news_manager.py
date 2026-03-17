import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import logging
import os

logger = logging.getLogger(__name__)

# Forex Factory RSS Feed
NEWS_URL = "https://www.forexfactory.com/ff_calendar_thisweek.xml"

# Cache settings
CACHE_FILE = "news_cache.xml"
CACHE_DURATION_HOURS = 6

def fetch_news():
    """
    Fetch news from Forex Factory RSS feed.
    """
    try:
        # Check cache
        if os.path.exists(CACHE_FILE):
            mtime = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE), tz=timezone.utc)
            if datetime.now(timezone.utc) - mtime < timedelta(hours=CACHE_DURATION_HOURS):
                with open(CACHE_FILE, 'r') as f:
                    return f.read()

        logger.info("Fetching fresh news from Forex Factory...")
        response = requests.get(NEWS_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if response.status_code == 200:
            with open(CACHE_FILE, 'w') as f:
                f.write(response.text)
            return response.text
    except Exception as e:
        logger.error(f"Error fetching news: {e}")
    
    # Fallback to cache if exists
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            return f.read()
    return None

def get_high_impact_news(currency="USD", impact_level="High"):
    """
    Parse the news XML and return a list of high impact events with their timestamps.
    """
    news_data = fetch_news()
    if not news_data:
        return []

    events = []
    try:
        root = ET.fromstring(news_data)
        for item in root.findall('event'):
            source_currency = item.find('symbol').text
            impact = item.find('impact').text
            date = item.find('date').text # Format: MM-DD-YYYY
            time = item.find('time').text # Format: HH:MMam/pm

            if source_currency == currency and impact == impact_level:
                # Parse date and time
                try:
                    # Example: 03-17-2024 10:30pm
                    dt_str = f"{date} {time}"
                    # Note: Forex Factory RSS time is typically EST/EDT. 
                    # For simplicity, we assume the user's bot also runs in a compatible timezone or we convert.
                    # Usually, MT5 time is what matters most for trading.
                    dt = datetime.strptime(dt_str, "%m-%d-%Y %I:%M%p").replace(tzinfo=timezone(timedelta(hours=-5))) # EST approx
                    events.append({
                        "title": item.find('title').text,
                        "time": dt,
                        "impact": impact
                    })
                except Exception as e:
                    logger.warning(f"Error parsing event time: {e}")
    except Exception as e:
        logger.error(f"Error parsing news XML: {e}")

    return events

def is_news_active(currency="USD", buffer_minutes=30):
    """
    Returns True if there is a high impact news event within the buffer window.
    """
    events = get_high_impact_news(currency=currency)
    now = datetime.now(timezone.utc)

    for event in events:
        event_time = event["time"].astimezone(timezone.utc)
        diff = abs((now - event_time).total_seconds()) / 60
        if diff <= buffer_minutes:
            return True, event["title"]

    return False, None

if __name__ == "__main__":
    # Test
    active, title = is_news_active()
    print(f"News Active: {active}, Title: {title}")
