import sys
sys.path.append('/home/ghost/air-agent/ingestor')
sys.path.append('/home/ghost/air-agent/processor')

from aggregator import run_pipeline


def get_current_metrics() -> dict:
    """
    Tool: Returns the latest hourly metrics from the air quality station.
    Includes environmental sensors and device health snapshot.
    """
    return run_pipeline()


def assess_aqi(env_metrics: list[dict]) -> dict:
    """
    Tool: Calculates Air Quality Index based on PM2.5 and PM10 mean values.
    Uses WHO guidelines as reference.

    WHO thresholds (24h mean, ug/m3):
    PM2.5: Good <15, Moderate 15-35, Unhealthy >35
    PM10:  Good <45, Moderate 45-100, Unhealthy >100
    """
    result = {}

    for sensor in env_metrics:
        sid = sensor["sensor_id"]
        mean = sensor["mean"]

        if sid == "pm25":
            if mean < 15:
                result["pm25_aqi"] = {"value": mean, "level": "Good"}
            elif mean < 35:
                result["pm25_aqi"] = {"value": mean, "level": "Moderate"}
            else:
                result["pm25_aqi"] = {"value": mean, "level": "Unhealthy"}

        elif sid == "pm10":
            if mean < 45:
                result["pm10_aqi"] = {"value": mean, "level": "Good"}
            elif mean < 100:
                result["pm10_aqi"] = {"value": mean, "level": "Moderate"}
            else:
                result["pm10_aqi"] = {"value": mean, "level": "Unhealthy"}

    return result


def assess_device_health(device_health: dict) -> dict:
    """
    Tool: Evaluates device health based on battery voltage and failure code snapshot.
    Battery voltage range: 3.5V (min) to 4.2V (max).
    """
    health = {"status": "ok", "warnings": []}

    failure_code = device_health.get("failure_code", 0)
    battery_voltage = device_health.get("battery_voltage", 4.2)
    internal_temp = device_health.get("internal_temp", 0)

    if failure_code > 0:
        health["status"] = "warning"
        health["warnings"].append(f"Device reporting failure code: {failure_code}")

    if battery_voltage < 3.6:
        health["status"] = "warning"
        health["warnings"].append(f"Low battery voltage: {battery_voltage}V")

    if battery_voltage < 3.5:
        health["status"] = "critical"
        health["warnings"].append(f"Critical battery voltage: {battery_voltage}V")

    if internal_temp > 60:
        health["status"] = "warning"
        health["warnings"].append(f"High internal temperature: {internal_temp}°C")

    return health

def get_air_quality_report(include_raw_metrics: bool = True) -> dict:
    if isinstance(include_raw_metrics, str):
        include_raw_metrics = include_raw_metrics.lower() == "true"

    data = get_current_metrics()
    if data["status"] == "error":
        return data

    aqi = assess_aqi(data["environmental"])
    health = assess_device_health(data["device_health"])

    report = {
        "timestamp": data["timestamp"],
        "aqi": aqi,
        "device_health": health,
        "samples_fetched": data["samples_fetched"]
    }

    if include_raw_metrics:
        # Include full metrics with variance, min, max for anomaly analysis
        report["environmental_metrics"] = data["environmental"]
        
        # Flag sensors with high variance or significant min/max spread
        anomalies = []
        for sensor in data["environmental"]:
            spread = sensor["max"] - sensor["min"]
            variance = sensor["variance"]
            mean = sensor["mean"]
            
            if mean > 0 and spread / mean > 0.5:
                anomalies.append({
                    "sensor": sensor["sensor_id"],
                    "mean": mean,
                    "min": sensor["min"],
                    "max": sensor["max"],
                    "variance": variance,
                    "spread_pct": round(spread / mean * 100, 1),
                    "flag": "high_spread"
                })
            elif variance > mean * 0.3 and mean > 0:
                anomalies.append({
                    "sensor": sensor["sensor_id"],
                    "mean": mean,
                    "variance": variance,
                    "flag": "high_variance"
                })

        report["anomalies"] = anomalies

    return report
    
# Tool definitions for the agent (Anthropic tool use format)
TOOLS = [
    {
        "name": "get_current_metrics",
        "description": "Fetches the latest hourly metrics from the air quality station including PM1, PM2.5, PM4, PM10, temperature, humidity, O3, NO2, SO2, and device health sensors.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "assess_aqi",
        "description": "Calculates Air Quality Index based on PM2.5 and PM10 values using WHO guidelines. Returns level: Good, Moderate, or Unhealthy.",
        "input_schema": {
            "type": "object",
            "properties": {
                "env_metrics": {
                    "type": "array",
                    "description": "List of environmental sensor metrics from get_current_metrics"
                }
            },
            "required": ["env_metrics"]
        }
    },
    {
        "name": "assess_device_health",
        "description": "Evaluates the physical condition of the monitoring station based on battery level, failure codes, and internal temperature.",
        "input_schema": {
            "type": "object",
            "properties": {
                "device_health": {
                    "type": "object",
                    "description": "Device health snapshot from get_current_metrics"
                }
            },
            "required": ["device_health"]
        }
    }
]