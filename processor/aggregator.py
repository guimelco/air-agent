import pandas as pd
from datetime import datetime, timezone
import sys
sys.path.append('/home/ghost/air-agent/ingestor')

from client import fetch_last_hour
from metrics import compute_hourly_metrics, get_device_snapshot

def run_pipeline() -> dict:
    timestamp = datetime.now(timezone.utc).isoformat()

    df = fetch_last_hour()
    if df.empty:
        return {"status": "error", "message": "No data fetched", "timestamp": timestamp}

    # Environmental metrics
    env_df = df[~df["sensor_id"].isin(["battery_voltage", "battery_soc", "internal_temp", "failure_code"])]
    env_metrics = compute_hourly_metrics(env_df)

    # Device health snapshot
    device_snapshot = get_device_snapshot(df)

    summary = {
        "status": "ok",
        "timestamp": timestamp,
        "samples_fetched": len(df),
        "unique_timestamps": df["time"].nunique(),
        "environmental": env_metrics.to_dict(orient="records"),
        "device_health": device_snapshot
    }

    return summary


if __name__ == "__main__":
    import json
    result = run_pipeline()
    print(json.dumps(result, indent=2, default=str))