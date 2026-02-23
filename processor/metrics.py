import pandas as pd


SENSORS = ["pm1", "pm25", "pm4", "pm10", "temperature", "humidity", "o3", "no2", "so2"]
DEVICE_SENSORS = ["battery_voltage", "battery_soc", "internal_temp", "failure_code"]


def compute_hourly_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Takes long-format DataFrame and computes hourly metrics per sensor.
    Returns a DataFrame with mean, min, max, variance and sample count per sensor.
    """
    if df.empty:
        return pd.DataFrame()

    metrics = (
        df.groupby("sensor_id")["value"]
        .agg(
            mean="mean",
            min="min",
            max="max",
            variance="var",
            samples="count"
        )
        .round(4)
        .reset_index()
    )

    return metrics


def split_metrics(metrics: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Splits metrics into environmental sensors and device health sensors.
    """
    env = metrics[metrics["sensor_id"].isin(SENSORS)]
    device = metrics[metrics["sensor_id"].isin(DEVICE_SENSORS)]
    return env, device


if __name__ == "__main__":
    import sys
    sys.path.append('/home/ghost/air-agent/ingestor')
    from client import fetch_last_hour

    df = fetch_last_hour()
    metrics = compute_hourly_metrics(df)
    env, device = split_metrics(metrics)

    print("=== Environmental Sensors ===")
    print(env.to_string(index=False))
    print("\n=== Device Health ===")
    print(device.to_string(index=False))