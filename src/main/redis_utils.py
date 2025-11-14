import os
from google.cloud import storage


def ensure_ca_cert():
    uri = os.getenv("REDIS_CA_GCS_URI")
    dest = os.getenv("REDIS_CA_PATH", "/tmp/redis-ca.pem")
    if not uri or os.path.exists(dest):
        return dest
    bucket, blob = uri.replace("gs://", "").split("/", 1)
    storage.Client().bucket(bucket).blob(blob).download_to_filename(dest)
    return dest
