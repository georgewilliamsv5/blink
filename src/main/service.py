import os
import time
import mlflow
import numpy as np
import redis
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from mlflow.tracking import MlflowClient
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from .config import MODEL_NAME, REDIS_HOST, MLFLOW_TRACKING_URI, REQUEST_LOGS
from .features import FEATURE_KEYS
from .logging_utils import get_logger, setup_logging
from .storage import engine
from .redis_utils import ensure_ca_cert


log = get_logger("api")
FEATURES = FEATURE_KEYS
REDIS_PORT = 6378

mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
INGEST_MODE = os.getenv("INGEST_MODE", "False") in ("1", "true", "True")


app = FastAPI()
app.mount("/static", StaticFiles(directory="web"), name="static")
templates = Jinja2Templates(directory="web/templates")

cert_path = ensure_ca_cert()

r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    ssl=True,
    ssl_cert_reqs="required",
    ssl_ca_certs=cert_path,
    decode_responses=True,
)
PRED_COUNT = Counter("blink_predictions_total", "Total predictions served")
LATENCY = Histogram("blink_predict_latency_seconds", "Prediction latency")
_model = None


def load_model():
    global _model
    if _model is not None:
        return _model
    try:
        _model = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}/Production")
        log.info("model loaded via registry", extra={"model": MODEL_NAME})
        return _model
    except Exception:
        log.warning("registry load failed; falling back to latest run")
        client = MlflowClient()
        experiment = client.get_experiment_by_name("blink")
        if experiment is None:
            log.error("Experiment 'blink' not found in MLflow")
            return None
        runs = client.search_runs(
            experiment_ids=[experiment.experiment_id],
            order_by=["attributes.start_time DESC"], max_results=1,
        )
        if not runs:
            log.error("No runs found for experiment 'blink'")
            return None
        run_id = runs[0].info.run_id
        _model = mlflow.pyfunc.load_model(f"runs:/{run_id}/model")
        log.info("model loaded via runs URI", extra={"run_id": run_id})
        return _model


@app.on_event("startup")
async def _startup():
    setup_logging()
    log.info("api startup")
if REQUEST_LOGS:
    @app.middleware("http")
    async def add_request_logging(request: Request, call_next):
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
            return response
        finally:
            dt = (time.perf_counter() - t0) * 1000
            log.info("http_request", extra={"path": request.url.path, "ms": round(dt, 2), "status": getattr(
                request, 'state', None) and getattr(getattr(request, 'state', None), 'status_code', None)})


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/score")
@LATENCY.time()
def score():
    PRED_COUNT.inc()
    feats = r.hgetall("latest_features") if INGEST_MODE == "live" else r.hgetall(
        "sampler_features")
    if not feats:
        log.warning("no_features")
        return {"ready": False, "reason": "no_features"}
    x = np.array([[float(feats[k]) for k in FEATURES]])  # type: ignore
    model = load_model()
    if model is None:
        return {"ready": False, "reason": "no_model"}
    y = model.predict(x)[0]
    res = {
        "ready": True,
        "anomaly": bool(y == -1),
        "score_raw": float(y),
        "model": f"{MODEL_NAME}@Production"
    }
    log.info("scored", extra={
        "anomaly": res["anomaly"], "score": res["score_raw"]})
    return {**res, "features": {k: float(feats[k]) for k in FEATURES}}


@app.get("/demo", response_class=HTMLResponse)
async def demo(request: Request):
    """Render the dashboard shell; data is fetched via /demo/data polling."""
    if templates is None:
        return HTMLResponse("<h3>Dashboard disabled: web/ not found in image.</h3>", status_code=200)
    return templates.TemplateResponse("demo.html", {"request": request, "model_name": MODEL_NAME})


@app.get("/demo/data", response_class=JSONResponse)
async def demo_data():
    """Return last 5 minutes of prices and the current anomaly flag."""
    # Get recent prices from Postgres
    with engine.begin() as conn:
        rows = conn.execute(text(
            """
            select extract(epoch from ts) as ts, price
            from trades
            where ts > now() - interval '5 minutes'
            order by ts asc
            """
        )).fetchall()
    times = [float(r.ts) for r in rows]
    prices = [float(r.price) for r in rows]

    # Current anomaly from latest features
    feats = r.hgetall("latest_features")
    anomaly = None
    score = None
    if feats:
        x = np.array([[float(feats[k]) for k in FEATURES]])  # type: ignore

        model = load_model()
        if model is not None:
            y = model.predict(x)[0]
            anomaly = bool(y == -1)
            score = float(y)
    return {"times": times, "prices": prices, "anomaly": anomaly, "score": score}
