import os


def pytest_configure():
    # Provide required env vars before modules import config at import-time
    os.environ.setdefault("PAIR", "BTC-USD")
    os.environ.setdefault("MODEL_NAME", "blink_iforest")
    os.environ.setdefault("MLFLOW_TRACKING_URI", "http://mlflow:5000")
    # Use an in-memory sqlite for modules that create an engine, to avoid requiring Postgres
    os.environ.setdefault("PG_DSN", "sqlite+pysqlite:///:memory:")
    os.environ.setdefault("REDIS_HOST", "localhost")
    # Logging defaults
    os.environ.setdefault("LOG_LEVEL", "INFO")
    os.environ.setdefault("LOG_FORMAT", "plain")
    os.environ.setdefault("SERVICE_NAME", "tests")
    os.environ.setdefault("REQUEST_LOGS", "false")

