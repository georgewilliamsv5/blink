import os


def _bool(v): return str(v).lower() in {"1", "true", "yes", "y", "on"}


def required(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


# Expose strongly-typed config that all modules import
PAIR = required("PAIR")
MODEL_NAME = required("MODEL_NAME")
MLFLOW_TRACKING_URI = required("MLFLOW_TRACKING_URI")
PG_DSN = required("PG_DSN")
REDIS_HOST = required("REDIS_HOST")


# Logging config
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "plain")  # plain | json
SERVICE_NAME = os.getenv("SERVICE_NAME", "app")
REQUEST_LOGS = _bool(os.getenv("REQUEST_LOGS", "true"))
