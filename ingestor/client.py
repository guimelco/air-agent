import requests
from typing import Optional
from datetime import datetime, timezone, timedelta

BASE_URL = "https://colmena.stguimel.com/api/monnet/mty_sureste_sima/timeseries?limit=20"

def fetch_latest(limit: int = 20) -> list[dict]:
    """
    Fetches the latest readings from the air quality station API.
    
    Args:
        limit: Number of most recent records to fetch.
    
    Returns:
        List of raw sensor readings in long format.
    """
    try:
        response = requests.get(BASE_URL, params={"limit": limit})
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[client] Error fetching data: {e}")
        return []

def fetch_last_hour(limit: int = 20) -> list[dict]:
    """
    Fetches recent readings from the last hour.
    Workaround: backend stores CST-1h labeled as UTC (13h behind real UTC).
    We compensate by shifting the comparison window accordingly.
    """
    raw = fetch_latest(limit=limit)
    
    if not raw:
        return []

    # Compensate for backend timezone bug: 13h offset
    BACKEND_OFFSET_HOURS = 13
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1) - timedelta(hours=BACKEND_OFFSET_HOURS)
    
    filtered = [
        r for r in raw
        if datetime.fromisoformat(r["time"].replace("Z", "+00:00")) >= one_hour_ago
    ]
    
    return filtered
    
def normalize(raw: list[dict]) -> dict:
    """
    Converts long-format sensor array into a single wide-format snapshot.
    Groups readings by timestamp and pivots sensor_id as keys.

    Args:
        raw: List of sensor readings from the API.

    Returns:
        Dict keyed by timestamp, each value is a flat dict of sensor readings.
    """
    grouped = {}
    for reading in raw:
        ts = reading["time"]
        if ts not in grouped:
            grouped[ts] = {"time": ts, "device_id": reading["device_id"]}
        grouped[ts][reading["sensor_id"]] = reading["value"]
    return grouped


if __name__ == "__main__":
    raw = fetch_latest(limit=5)
    normalized = normalize(raw)
    for ts, snapshot in normalized.items():
        print(snapshot)