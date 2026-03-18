import pandas as pd
import os
import logging
from config import PATH_M5, PATH_H1

logger = logging.getLogger(__name__)


def load_file(path):

    try:

        if not os.path.exists(path):
            logger.error(f"File not found: {path}")
            return None

        if os.path.getsize(path) == 0:
            logger.info(f"File empty: {path}")
            return None

        df = pd.read_csv(path, sep="\t", header=None)

        if df.empty:
            print("DataFrame empty:", path)
            return None

        if len(df.columns) == 6:
            df.columns = ["time","open","high","low","close","volume"]
        elif len(df.columns) == 5:
            df.columns = ["time","open","high","low","close"]
            df["volume"] = 1
        else:
            logger.error(f"Unexpected column count: {len(df.columns)}")
            return None

        df["time"] = pd.to_datetime(df["time"])

        df = df.sort_values("time")

        df = df.reset_index(drop=True)

        return df

    except Exception as e:
        logger.error(f"Market data read error: {e}")
        return None


def get_market_data():

    return load_file(PATH_M5)


def get_market_data_htf():

    return load_file(PATH_H1)
