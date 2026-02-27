import sys
sys.path.append('/home/ghost/air-agent/ingestor')
sys.path.append('/home/ghost/air-agent/processor')

from aggregator import run_pipeline

# Sensor categories
PARTICLE_SENSORS = ["pm1", "pm25", "pm4", "pm10"]
ENVIRONMENTAL_SENSORS = ["temperature", "humidity"]
CHEMICAL_SENSORS = ["o3", "no2", "so2"]
DEVICE_SENSORS = ["battery_voltage", "battery_soc", "internal_temp", "failure_code"]


def _filter_metrics(metrics: list, sensors: list) -> list:
    """Filters metrics list by sensor category."""
    return [m for m in metrics if m["sensor_id"] in sensors]


def get_particle_sensors(data: dict) -> dict:
    """
    Returns synthesized metrics for particle sensors (pm1, pm25, pm4, pm10).
    Includes mean, min, max, variance and sample count.
    """
    return {
        "category": "particle",
        "sensors": _filter_metrics(data["environmental"], PARTICLE_SENSORS)
    }


def get_environmental_sensors(data: dict) -> dict:
    """
    Returns synthesized metrics for physical/environmental sensors (temperature, humidity).
    """
    return {
        "category": "environmental",
        "sensors": _filter_metrics(data["environmental"], ENVIRONMENTAL_SENSORS)
    }


def get_chemical_sensors(data: dict) -> dict:
    """
    Returns synthesized metrics for chemical/gas sensors (o3, no2, so2).
    """
    return {
        "category": "chemical",
        "sensors": _filter_metrics(data["environmental"], CHEMICAL_SENSORS)
    }


def get_device_status(data: dict) -> dict:
    """
    Returns device health snapshot (battery, failure code, internal temp).
    Values are not averaged — each uses the most meaningful aggregation.
    """
    return {
        "category": "device",
        "status": data["device_health"]
    }


MODULE_MAP = {
    "particle": get_particle_sensors,
    "environmental": get_environmental_sensors,
    "chemical": get_chemical_sensors,
    "device": get_device_status
}


def get_sensor_report(modules: list = None) -> dict:
    """
    Orchestrates sensor data retrieval by module.
    
    Args:
        modules: List of modules to include. Options: particle, environmental, chemical, device.
                 If None, returns all modules.
    
    Returns:
        Dict with requested sensor data, raw and synthesized, ready for agent interpretation.
    """
    if modules is None:
        modules = list(MODULE_MAP.keys())

    data = run_pipeline()

    if data["status"] == "error":
        return data

    report = {
        "status": "ok",
        "timestamp": data["timestamp"],
        "samples_fetched": data["samples_fetched"],
        "unique_timestamps": data["unique_timestamps"],
        "modules": {}
    }

    for module in modules:
        if module in MODULE_MAP:
            report["modules"][module] = MODULE_MAP[module](data)

    return report

def get_historical_context(hour: int, day_of_week: str) -> dict:
    """
    Tool: Retrieves historical events for the same hour and day of week.
    Used to identify recurring patterns.
    """
    import sys
    sys.path.append('/home/ghost/air-agent/db')
    from database import get_similar_events, get_baseline
    
    events = get_similar_events(hour=hour, day_of_week=day_of_week)
    
    particle_sensors = ["pm25", "pm10"]
    baselines = {}
    for sensor in particle_sensors:
        baseline = get_baseline(day_of_week=day_of_week, hour=hour, sensor_id=sensor)
        if baseline:
            baselines[sensor] = baseline
    
    return {
        "similar_events": events,
        "baselines": baselines,
        "events_found": len(events)
    }

def save_relevant_event(
    trigger: str,
    pattern_match: str,
    agent_notes: str,
    pm25_mean: float = None,
    pm25_max: float = None,
    pm10_mean: float = None,
    pm10_max: float = None,
    temperature: float = None,
    humidity: float = None
) -> dict:
    """
    Guarda un evento relevante en la base de datos.
    El agente decide cuándo llamar esta tool basándose en su análisis.
    """
    import sys
    sys.path.append('/home/ghost/air-agent/db')
    from database import save_event
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    event_id = save_event(
        timestamp=now.isoformat(),
        day_of_week=now.strftime("%A"),
        hour=now.hour,
        trigger=trigger,
        pm25_mean=pm25_mean,
        pm25_max=pm25_max,
        pm10_mean=pm10_mean,
        pm10_max=pm10_max,
        temperature=temperature,
        humidity=humidity,
        pattern_match=pattern_match,
        agent_notes=agent_notes
    )

    return {"status": "ok", "event_id": event_id}
    
# Tool definitions for the agent
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_sensor_report",
            "description": "Fetches synthesized sensor data from the monitoring station by module. Returns raw statistical metrics (mean, min, max, variance, samples) for agent interpretation. Does not include pre-computed indices or assessments — those are determined by the agent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "modules": {
                        "type": "array",
                        "description": "List of sensor modules to include. Options: 'particle' (pm1, pm25, pm4, pm10), 'environmental' (temperature, humidity), 'chemical' (o3, no2, so2), 'device' (battery, failure code, internal temp). If not specified, returns all modules.",
                        "items": {"type": "string"}
                    }
                },
                "required": []
            }
        }
    }
]