import os
from config import PATH_SIGNAL

def write_signal(signal, sl=None, tp=None, lot=None):

    path = PATH_SIGNAL

    os.makedirs(os.path.dirname(path), exist_ok=True)

   # ถ้าไม่มี signal
    if signal == "NONE":
        content = "NONE"

    else:
        # ส่ง signal พร้อม SL, TP และ Lot
        if lot is not None:
            content = f"{signal},{sl},{tp},{lot}"
        else:
            content = f"{signal},{sl},{tp}"

    with open(path, "w", encoding="ascii") as f:
        f.write(content)
