import json
import asyncio
import websockets
from datetime import datetime
from sqlalchemy import text
from .storage import engine, ensure_schema
from .config import PAIR
from .logging_utils import get_logger, setup_logging

log = get_logger("ingestor")


WS_URL = "wss://ws-feed.exchange.coinbase.com"


SUB_MSG = {
    "type": "subscribe",
    "channels": [{"name": "matches", "product_ids": [PAIR]}],
}


async def write_trade(ts_iso: str, price: str, size: str):
    ts = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
    with engine.begin() as conn:
        try:
            conn.execute(text(
                "insert into trades(ts, price, size) values (:ts, :p, :s) on conflict do nothing"
            ), {"ts": ts, "p": float(price), "s": float(size)})
            log.info(f"wrote trade ts={ts} price={price} size={size}")
        except Exception as e:
            log.error(f"failed to write trade: {e}")


async def run():
    ensure_schema()
    while True:
        try:
            log.info("connecting to websocket")
            async with websockets.connect(WS_URL, ping_interval=20, ping_timeout=20) as ws:
                await ws.send(json.dumps(SUB_MSG))
                async for raw in ws:
                    m = json.loads(raw)
                    if m.get("type") == "match" and m.get("product_id") == PAIR:
                        await write_trade(m["time"], m["price"], m["size"])
                        log.debug(f"received trade: {m}")
        except Exception as e:
            print("[ingestor] reconnecting after error:", e)
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(run())
