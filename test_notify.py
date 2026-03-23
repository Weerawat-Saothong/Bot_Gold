import sys
import os

# Add parent directory to sys.path so we can import notify.line_notify
sys.path.append(os.path.abspath(os.curdir))

from notify.line_notify import send_line

msg = "🔔 TEST: Telegram notification is working!"
print(f"Sending message: {msg}")
send_line(msg)
