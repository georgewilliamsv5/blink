#!/usr/bin/env python
"""
One-off helper to verify the Redis CA download from GCS works with your current GCP credentials.

Usage:
  export REDIS_CA_GCS_URI=gs://your-bucket/redis-ca.pem
  export REDIS_CA_PATH=/tmp/redis-ca.pem   # optional; defaults to /tmp/redis-ca.pem
  gcloud auth application-default login     # or ensure Workload Identity on Cloud Shell
  python scripts/test_redis_ca.py
"""
import os
import sys
from src.main.redis_utils import ensure_ca_cert


def main() -> int:
    uri = os.getenv("REDIS_CA_GCS_URI")
    dest = os.getenv("REDIS_CA_PATH", "/tmp/redis-ca.pem")
    if not uri:
        print("REDIS_CA_GCS_URI is not set; export it to a gs:// path for the CA cert", file=sys.stderr)
        return 1
    try:
        path = ensure_ca_cert()
    except Exception as exc:  # pragma: no cover - ad hoc script
        print(
            f"Failed to download CA cert from {uri} -> {dest}: {exc}", file=sys.stderr)
        return 1
    print(f"Downloaded CA cert to {path}")
    if os.path.exists(path):
        print(f"File size: {os.path.getsize(path)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
