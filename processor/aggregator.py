import pandas as pd
from datetime import datetime, timezone
import sys
sys.path.append('/home/ghost/air-agent/ingestor')

from client import fetch_last_hour
from metrics import compute_hourly_metrics, split_metrics


def run_pipeline() -> dict:
    """
    Orchestrates the full data pipeline:
    1. Fetch last hour readings from API
    2. Compute hourly metrics
    3. Split into environmental and device health metrics
    4. Return structured summary ready for the agent
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # Step 1: Fetch
    df = fetch_last_hour()
    if df.empty:
        return {"status": "error", "message": "No data fetched", "timestamp": timestamp}

    # Step 2: Compute metrics
    metrics = compute_hourly_metrics(df)

    # Step 3: Split
    env_metrics, device_metrics = split_metrics(metrics)

    # Step 4: Structure output for agent
    summary = {
        "status": "ok",
        "timestamp": timestamp,
        "samples_fetched": len(df),
        "unique_timestamps": df["time"].nunique(),
        "environmental": env_metrics.to_dict(orient="records"),
        "device_health": device_metrics.to_dict(orient="records")
    }

    return summary


if __name__ == "__main__":
    import json
    result = run_pipeline()
    print(json.dumps(result, indent=2, default=str))