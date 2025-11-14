
import os
import time
import pandas as pd
from sqlalchemy import text
from .storage import engine
from sklearn.ensemble import IsolationForest
import mlflow
import mlflow.sklearn
from .config import MODEL_NAME, MLFLOW_TRACKING_URI
from .logging_utils import get_logger


mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
mlflow.set_experiment("blink")

INGEST_MODE = os.getenv("INGEST_MODE")

log = get_logger("trainer")

MIN_ROWS_TO_TRAIN = 200


FEATURES = ["ret_1s", "ret_5s", "ret_30s", "ewma_30s", "vol_60s", "z_30s"]


def load_sample_df():
    with engine.begin() as conn:
        df = pd.read_sql_query(
            text("select ts, price from trades order by ts"), conn
        )
        df = df.set_index("ts").sort_index()
        df["ret_1s"] = df["price"].pct_change(1)
        df["ret_5s"] = df["price"].pct_change(5)
        df["ret_30s"] = df["price"].pct_change(30)
        df["ewma_30s"] = df["price"].ewm(span=30, adjust=False).mean()
        df["vol_60s"] = df["ret_1s"].rolling(60).std()
        df["z_30s"] = (df["price"] - df["price"].rolling(30).mean()) / \
            (df["price"].rolling(30).std() + 1e-9)
        X = df[FEATURES].dropna()
        return X


def load_training_df(hours=12):
    with engine.begin() as conn:
        df = pd.read_sql_query(
            text("select ts, price from trades where ts > now() - interval '%s hours' order by ts" % hours), conn
        )
        if len(df) < MIN_ROWS_TO_TRAIN:
            return None
        df = df.set_index("ts").sort_index()
        df["ret_1s"] = df["price"].pct_change(1)
        df["ret_5s"] = df["price"].pct_change(5)
        df["ret_30s"] = df["price"].pct_change(30)
        df["ewma_30s"] = df["price"].ewm(span=30, adjust=False).mean()
        df["vol_60s"] = df["ret_1s"].rolling(60).std()
        df["z_30s"] = (df["price"] - df["price"].rolling(30).mean()) / \
            (df["price"].rolling(30).std() + 1e-9)
        X = df[FEATURES].dropna()
        return X


def train_once():
    X = load_training_df() if INGEST_MODE == "live" else load_sample_df()
    if X is None or X.empty:
        print("[trainer] not enough data yet; waiting…")
        return False
    model = IsolationForest(
        n_estimators=MIN_ROWS_TO_TRAIN, contamination="auto", random_state=42)
    with mlflow.start_run():
        model.fit(X)
        mlflow.log_param("n_features", X.shape[1])
        mlflow.log_param("n_samples", X.shape[0])
        mlflow.log_metric("train_score_mean", float(
            model.score_samples(X).mean()))
        mlflow.sklearn.log_model(
            model, "model", registered_model_name=MODEL_NAME)
        print("[trainer] trained & logged model")
    return True


if __name__ == "__main__":
    log.info("trainer started", extra={"mode": INGEST_MODE})
    while True:
        ok = train_once()
        if ok:
            log.info("trainer shutting down)", extra={})
            break
        exit()  # purposely exit instead of sleep while testing GCP deployments
