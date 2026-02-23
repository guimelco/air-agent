import requests
import pandas as pd
from datetime import datetime, timezone, timedelta

BASE_URL = "https://colmena.stguimel.com/api/monnet/mty_sureste_sima/timeseries"

SENSORS_COUNT = 13
SAMPLES_PER_HOUR = 15
BACKEND_OFFSET_HOURS = 13  # workaround: backend stores CST-1h labeled as UTC


def fetch_latest(limit: int = SENSORS_COUNT * SAMPLES_PER_HOUR) -> pd.DataFrame:
    """
    Fetches the latest readings from the API and returns a long-format DataFrame.
    """
    try:
        response = requests.get(BASE_URL, params={"limit": limit})
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data)
        df["time"] = pd.to_datetime(df["time"], utc=True)
        return df
    except requests.exceptions.RequestException as e:
        print(f"[client] Error fetching data: {e}")
        return pd.DataFrame()


def fetch_last_hour(limit: int = SENSORS_COUNT * SAMPLES_PER_HOUR) -> pd.DataFrame:
    """
    Fetches readings and filters only those from the last hour.
    Applies backend timezone offset workaround.
    """
    df = fetch_latest(limit=limit)

    if df.empty:
        return df

    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1) - timedelta(hours=BACKEND_OFFSET_HOURS)
    return df[df["time"] >= one_hour_ago]


def pivot_wide(df: pd.DataFrame) -> pd.DataFrame:
    """
    Converts long-format DataFrame to wide-format.
    Each row is a timestamp, each column is a sensor.
    """
    if df.empty:
        return df

    return df.pivot_table(index=["time", "device_id"], columns="sensor_id", values="value").reset_index()


if __name__ == "__main__":
    df = fetch_last_hour()
    print(f"Lecturas última hora: {len(df)}")
    print(pivot_wide(df))