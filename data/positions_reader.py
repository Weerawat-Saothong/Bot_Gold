import json
import os
from config import PATH_POSITIONS_JSON

PATH = PATH_POSITIONS_JSON

def get_positions():

    try:

        if not os.path.exists(PATH):
            return []

        with open(PATH) as f:
            data = json.load(f)

        return data

    except Exception as e:

        print("Positions error:", e)

        return []
