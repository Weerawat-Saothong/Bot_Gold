from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from data.positions_reader import get_positions

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

account_data = {
    "balance": 10000,
    "equity": 10000,
    "pnl": 0,
    "drawdown": 0
}

positions = []
trades = []
equity_curve = []

signal_data = {
    "direction": "HOLD",
    "score": 0,
    "mode": "NONE"
}


@app.get("/")
def root():
    return {"message": "Gold Quant Bot API Running"}


@app.get("/account")
def get_account():
    return account_data


@app.get("/positions")
def positions():

    try:
        return get_positions()

    except Exception as e:
        return {"error": str(e)}
        
@app.get("/trades")
def get_trades():
    return trades


@app.get("/equity")
def get_equity():
    return equity_curve


@app.get("/signal")
def get_signal():
    return signal_data


@app.post("/update_signal")
def update_signal(data: dict):

    global signal_data
    signal_data = data

    return {"status": "ok"}
