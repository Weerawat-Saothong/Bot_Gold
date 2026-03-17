import os
from config import PATH_POSITION

def read_position():

    file_path = PATH_POSITION

    if not os.path.exists(file_path):
        return "NONE"

    try:
        with open(file_path, "r") as f:
            pos = f.read().strip()

        if pos in ["BUY", "SELL"]:
            return pos

        return "NONE"

    except:
        return "NONE"