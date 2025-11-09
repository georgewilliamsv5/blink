from datetime import datetime, timedelta

import math
import pandas as pd


def _make_linear_prices(n: int, start: float = 100.0, step: float = 0.1):
    t0 = datetime.utcnow() - timedelta(seconds=n)
    rows = []
    for i in range(n):
        ts = t0 + timedelta(seconds=i)
        price = start + step * i
        rows.append({"ts": ts, "price": price})
    return pd.DataFrame(rows)


def test_compute_features_basic():
    # Import here so env is already set from conftest
    from src.main.features import compute_features, FEATURE_KEYS

    df = _make_linear_prices(120, start=100.0, step=0.1)
    feats = compute_features(df)

    # Keys present
    assert set(feats.keys()) == set(FEATURE_KEYS)

    # Sanity checks on numeric values
    for v in feats.values():
        assert v is not None and not (isinstance(
            v, float) and (math.isnan(v) or math.isinf(v)))

    # On a smooth linear increase of 0.1 per second around price~112,
    # 1s pct return should be close to 0.1 / 112 ~= 0.0009
    approx_ret_1s = 0.1 / (100.0 + 0.1 * 119)
    assert abs(feats["ret_1s"] - approx_ret_1s) < 5e-4

    # Vol over constant 1s returns is near 0
    assert abs(feats["vol_60s"]) < 5e-4
