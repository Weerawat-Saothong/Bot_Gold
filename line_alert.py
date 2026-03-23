from notify.line_notify import send_line as sl

def send_line(message):
    """
    Backward compatibility for line_alert.py
    """
    sl(message)
