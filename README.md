Blink — Realtime BTC-USD anomaly detector
=========================================

Blink ingests live trades from Coinbase, computes rolling price features, trains an IsolationForest model tracked in MLflow, and serves a small FastAPI app with a dashboard and Prometheus metrics.

DISCLAIMER: Blink is a practice project for learning. Take code from here at your own discretion and be aware of risks.


Overview
--------
- Ingestor: Streams Coinbase “matches” into Postgres (`trades` table).
- Features: Builds rolling features from recent prices and caches the latest vector in Redis.
- Trainer: Periodically trains an IsolationForest and logs the model to MLflow (Registry supported).
- API: Serves `/score`, `/demo`, `/metrics`, loading the model from MLflow.

Architecture at a glance
------------------------
- Postgres stores raw trades.
- Redis stores the latest features.
- MLflow tracks runs and models (artifacts stored on local volume in dev).
- FastAPI exposes scoring and a simple Plotly dashboard.


Quickstart (Docker Compose)
---------------------------
Prerequisites: Docker and Docker Compose (v2) installed.

1) Start the stack

   ```sh
   docker compose --env-file compose-dev.env up --build
   ```

   Services:
   - Postgres: localhost:5432
   - Redis: localhost:6379
   - MLflow UI: http://localhost:5000
   - API: http://localhost:8080

2) Open the app
   - Health: http://localhost:8080/healthz
   - Demo dashboard: http://localhost:8080/demo
   - Prometheus metrics: http://localhost:8080/metrics

Notes
-----
- Warming up: The system needs live trades to accumulate. The dashboard may show “Warming up…” until there are enough trades and a model is available.
- Environment: `docker-compose.yml` wires defaults from `env/template-dev.env`.
- MLflow registry: Models and runs are stored under `./mlruns` (mounted for `mlflow`, `api`, and `trainer`).


Configuration
-------------
Required environment variables (see `env/template-dev.env`):

- `PAIR` — Coinbase product id (e.g., `BTC-USD`).
- `MODEL_NAME` — MLflow registered model name (e.g., `blink_iforest`).
- `MLFLOW_TRACKING_URI` — MLflow server URL (dev: `http://mlflow:5000`).
- `PG_DSN` — SQLAlchemy DSN for Postgres (dev points to the compose service).
- `REDIS_HOST` — Redis host (dev: `redis`).


Endpoints
---------
- `GET /healthz` — Basic readiness.
- `GET /score` — Returns `{ ready, anomaly, score_raw, model, features }`.
- `GET /demo` — Plotly dashboard (polls `/demo/data`).
- `GET /demo/data` — Last 5 minutes of prices + current anomaly and score.
- `GET /metrics` — Prometheus metrics (prediction count and latency histograms).

Example:

```sh
curl -s http://localhost:8080/score | jq
```


Local development (with uv)
---------------------------
Run services directly using uv (fast Python package manager). One process per terminal.

1) Install uv (once):

   ```sh
   # See: https://docs.astral.sh/uv/
   curl -LsSf https://astral.sh/uv/install.sh | sh
   # or on macOS: brew install astral-sh/uv/uv
   ```

2) Sync dependencies (creates/updates `.venv` from `pyproject.toml` + `uv.lock`):

   ```sh
   uv sync --frozen
   ```


3) Ensure infrastructure is available:
   - Postgres, Redis, and MLflow must be running. Easiest is to use `docker compose up postgres redis mlflow` in a separate terminal, or run your own instances and set `PG_DSN`, `REDIS_HOST`, `MLFLOW_TRACKING_URI` accordingly.

4) Start processes (each in its own terminal):

   ```sh
   # API
   uv run uvicorn src.main.service:app --host 0.0.0.0 --port 8080

   # Ingestor (Coinbase websocket -> Postgres)
   uv run python -m src.main.ingestor

   # Features (computes and caches latest features in Redis)
   uv run python -m src.main.features

   # Trainer (hourly model training -> MLflow)
   uv run python -m src.main.train
   ```


How it decides readiness
------------------------
- Features service requires enough recent trades (≥ ~90 rows) to compute a reasonable vector. Until then, `/score` returns `{"ready": false, "reason": "no_features"}`.
- Trainer requires more history (≥ ~200 rows) to train and log a model. Before that, `/score` may return `{"ready": false, "reason": "no_model"}`.
- The API tries to load from the MLflow Registry (`models:/{MODEL_NAME}/Production`). If not available, it falls back to the latest run in the `blink` experiment.


Troubleshooting
---------------
“No features” from /score
- Cause: Not enough recent trades or features service not running.
- Fixes:
  - Ensure `ingestor` and `features` are healthy.
  - Wait a few minutes for trades to accumulate (Coinbase stream).
  - Check Redis for `latest_features` hash exists

“No model” from /score
- Cause: Trainer has not logged a model yet or MLflow is unreachable.
- Fixes:
  - Ensure `trainer` and `mlflow` are running.
  - Open MLflow UI at http://localhost:5000 and confirm a recent run and a registered model named `MODEL_NAME`.
  - The API will fall back to the latest run if the Registry/Production stage is not set.

Database connection errors
- Cause: Postgres not ready or wrong `PG_DSN`.
- Fixes:
  - With Docker Compose, wait for Postgres healthcheck to pass.

Redis connection errors
- Cause: Redis not running or wrong host.
- Fixes:
  - Ensure `redis` service is up; in dev the host is `redis` inside containers, `localhost:6379` from your host.

MLflow/Artifacts issues
- Cause: MLflow server not reachable, or `./mlruns` volume not mounted.
- Fixes:
  - Use the compose file as-is so `./mlruns` is shared across `mlflow`, `api`, and `trainer`.
  - Confirm `MLFLOW_TRACKING_URI=http://mlflow:5000` inside containers.

Coinbase websocket blocked or slow
- Cause: Network egress restrictions or Coinbase downtime.
- Fixes:
  - Retry later or run with a mock ingestor that inserts synthetic trades (not included, but is on roadmap)

Verbose logs
- Set `LOG_LEVEL=DEBUG` and `LOG_FORMAT=json` for structured logs.


Production notes
----------------
- Use `env/template-prod.env` as a starting point; set `sslmode=require` for Postgres and point `MLFLOW_TRACKING_URI` to your MLflow endpoint.
- Protect the API, set resource limits, and run behind a reverse proxy (nginx suggested)
- Prefer model loading via Registry with stage `Production` to control rollouts.


Project layout
--------------
- `src/main/ingestor.py` — Coinbase WS → Postgres trades.
- `src/main/features.py` — Rolling features → Redis `latest_features`.
- `src/main/train.py` — Train/log IsolationForest → MLflow.
- `src/main/service.py` — FastAPI app, scoring, dashboard, metrics.
- `src/main/storage.py` — SQLAlchemy engine and schema creation.
- `env/` — Dev/Prod env templates.
- `web/` — Dashboard assets.
- `docker-compose.yml` — Dev stack for local run.
- `Dockerfile` — Image used by services.


Road map (TODOs for future practice)
--------------
- Add proper github actions for deploying to staging/production
- Add mock data in case the coinbase websocket is down
- Consider a lightweight job to persist features to Postgres for reproducibility of training, or compute features in trainer to avoid drift (currently duplicated logic but consistent).
- Add more unit tests for each service
- Address the Memory overcommit issue on redis startup
