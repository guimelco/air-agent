import json
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv('/home/ghost/air-agent/.env')

LOG_FILE = '/home/ghost/air-agent/logs/eval_log.jsonl'


def log_interaction(
    user_message: str,
    tools_called: list,
    agent_response: str,
    latency_ms: float,
    error: str = None
) -> None:
    """
    Logs each agent interaction for evaluation purposes.
    Uses JSONL format (one JSON object per line) for easy querying.
    
    Eval criteria tracked:
    - tool_called_correctly: did the agent call the expected tool?
    - response_generated: did the agent produce a non-null response?
    - latency_ms: how long did the full interaction take?
    - error: was there any error during execution?
    """
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_message": user_message,
        "tools_called": tools_called,
        "response_generated": agent_response is not None,
        "response_preview": agent_response[:200] if agent_response else None,
        "latency_ms": round(latency_ms, 2),
        "error": error,
        "eval_scores": {
            "tool_called_correctly": None,  # to be filled manually or by LLM judge
            "response_grounded": None,       # does response match actual sensor data?
            "hallucination_detected": None   # did agent invent data?
        }
    }

    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    with open(LOG_FILE, 'a') as f:
        f.write(json.dumps(record, default=str) + '\n')

    print(f"[eval_logger] Interaction logged at {record['timestamp']}")


def read_logs(last_n: int = 10) -> list:
    """
    Reads the last N interactions from the eval log.
    """
    if not os.path.exists(LOG_FILE):
        return []

    with open(LOG_FILE, 'r') as f:
        lines = f.readlines()

    return [json.loads(line) for line in lines[-last_n:]]