import time
import pandas as pd
from sqlalchemy import text
import redis
from .storage import engine
from .config import REDIS_HOST


r = redis.Redis(host=REDIS_HOST, decode_responses=True)

MIN_FEATURES_ROWS = 90


FEATURE_KEYS = ["ret_1s", "ret_5s", "ret_30s", "ewma_30s", "vol_60s", "z_30s"]


def compute_features(df: pd.DataFrame):
    df = df.set_index("ts").sort_index()
    df["ret_1s"] = df["price"].pct_change(1)
    df["ret_5s"] = df["price"].pct_change(5)
    df["ret_30s"] = df["price"].pct_change(30)
    df["ewma_30s"] = df["price"].ewm(span=30, adjust=False).mean()
    df["vol_60s"] = df["ret_1s"].rolling(60).std()
    df["z_30s"] = (df["price"] - df["price"].rolling(30).mean()) / \
        (df["price"].rolling(30).std() + 1e-9)
    x = df.dropna().iloc[-1]
    return {k: x[k] for k in FEATURE_KEYS}


def materialize_once():
    with engine.begin() as conn:
        df = pd.read_sql_query(
            text("select ts, price from trades where ts > now() - interval '20 minutes' order by ts"), conn
        )
        if len(df) < MIN_FEATURES_ROWS:
            return False
        feats = compute_features(df)
        r.hset("latest_features", mapping={
               k: str(v) for k, v in feats.items()})
        r.expire("latest_features", 60)
        return True


if __name__ == "__main__":
    while True:
        ok = materialize_once()
        time.sleep(5 if ok else 2)
