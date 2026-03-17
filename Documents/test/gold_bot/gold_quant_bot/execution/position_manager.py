import time

last_trade_time = 0
cooldown = 1800   # 30 นาที

def position_control(current_position):

    global last_trade_time

    now = time.time()

    if current_position != "NONE":
        return False

    if now - last_trade_time < cooldown:
        print("Trade cooldown active")
        return False

    last_trade_time = now

    return True