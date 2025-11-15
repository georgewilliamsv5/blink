import os
import time
import pandas as pd
from datetime import timezone
from sqlalchemy import text
from .storage import engine, ensure_schema
from .logging_utils import get_logger


log = get_logger("sampler")


SRC_PATH = os.getenv("SAMPLE_SOURCE", "data/sample_trades.csv")
# PACING = os.getenv("SAMPLE_PACING", "fixed_ms=100")
# TODO enable pacing later (probably never) 11/12/2025
SIZE_DEFAULT = float(os.getenv("SIZE_DEFAULT", "0.001"))
TS_COL = os.getenv("TS_COLUMN")
PRICE_COL = os.getenv("PRICE_COLUMN")
SIZE_COL = os.getenv("SIZE_COLUMN")
TIME_IS_UNIX = os.getenv("TIME_IS_UNIX", "False").lower() in [
    "1", "true", "yes"]


def _read_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if TIME_IS_UNIX:
        ts = pd.to_datetime(df[TS_COL], unit="s", utc=True)
    else:
        ts = pd.to_datetime(df[TS_COL], utc=True, errors="coerce")
    price = pd.to_numeric(df[PRICE_COL], errors="coerce")
    size = pd.to_numeric(
        df[SIZE_COL], errors="coerce") if SIZE_COL else pd.Series([None]*len(df))
    size = size.fillna(SIZE_DEFAULT)
    out = pd.DataFrame({"ts": ts, "price": price, "size": size}
                       ).dropna().sort_values("ts")
    return out


def stream(df: pd.DataFrame):
    ensure_schema()
    inserted = 0
    for _, row in df.iterrows():
        ts = row["ts"]
        px = float(row["price"])
        sz = float(row["size"])
        with engine.begin() as conn:
            conn.execute(text(
                "insert into trades(ts, price, size) values (:ts, :p, :s) on conflict do nothing"
            ), {"ts": ts.to_pydatetime().astimezone(timezone.utc), "p": px, "s": sz})
        inserted += 1
        if inserted % 500 == 0:
            log.info("streamed", extra={
                     "rows": inserted, "last": ts.isoformat()})
    log.info("stream complete", extra={"total_rows": inserted})


def main():
    if not os.path.exists(SRC_PATH):
        raise FileNotFoundError(f"SAMPLE_SOURCE not found: {SRC_PATH}")
    # log.info("reading", extra={"path": SRC_PATH, "pacing": PACING})
    log.info("beginning read", extra={"path": SRC_PATH})
    df = _read_csv(SRC_PATH)
    log.info("ready", extra={"rows": int(len(df)), "start": df["ts"].iloc[0].isoformat(
    ), "end": df["ts"].iloc[-1].isoformat()})
    stream(df)


if __name__ == "__main__":
    log.info("sampler starting")
    log.info(TIME_IS_UNIX)
    log.info(TS_COL)
    log.info(PRICE_COL)
    log.info(SIZE_COL)
    main()
