import sys
import os
import json
import time

from groq import Groq
from dotenv import load_dotenv
from telegram import send_message
from eval_logger import log_interaction

load_dotenv('/home/ghost/air-agent/.env')

sys.path.append('/home/ghost/air-agent/ingestor')
sys.path.append('/home/ghost/air-agent/processor')
sys.path.append('/home/ghost/air-agent/agent')
sys.path.append('/home/ghost/air-agent/notifier')

from tools import get_current_metrics, assess_aqi, assess_device_health, get_air_quality_report

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """
You are an air quality monitoring agent analyzing data from a low-cost sensor station.

When analyzing data:
- Report AQI levels clearly (Good, Moderate, Unhealthy) based on WHO guidelines
- Flag device health warnings immediately
- If anomalies are present, analyze what could explain the spread or variance:
  * High spread in PM sensors could indicate a passing pollution event
  * High variance in gases could indicate intermittent emission source
  * Correlate anomalies across sensors (e.g. PM + O3 spike together suggests traffic or fire)
- Be concise but analytical — explain the WHY not just the WHAT

When to use include_raw_metrics=True:
- User asks for detailed analysis
- Routine hourly check (always include for automated reports)

When to use include_raw_metrics=False:
- User asks for a quick summary only
"""
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_air_quality_report",
            "description": "Fetches current air quality metrics, calculates AQI, and evaluates device health. Returns a complete report of the station status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "include_raw_metrics": {
                        "type": "boolean",
                        "description": "Whether to include raw sensor metrics in the report. Default is true."
                    }
                },
                "required": []
            }
        }
    }
]

TOOL_MAP = {
    "get_air_quality_report": get_air_quality_report
}


def run_agent(user_message: str) -> str:
    start_time = time.time()
    tools_called = []
    error = None
    response_text = None

    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]

        while True:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=1024
            )

            message = response.choices[0].message
            finish_reason = response.choices[0].finish_reason

            if finish_reason == "stop":
                response_text = message.content or "No response generated"
                send_message(response_text)
                break

            if finish_reason == "tool_calls":
                messages.append({
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        } for tc in message.tool_calls
                    ]
                })

                for tool_call in message.tool_calls:
                    fn_name = tool_call.function.name
                    fn_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                    print(f"[agent] Calling tool: {fn_name} with args: {fn_args}")
                    tools_called.append({"tool": fn_name, "args": fn_args})

                    result = TOOL_MAP[fn_name](**fn_args)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result, default=str)
                    })

    except Exception as e:
        error = str(e)
        print(f"[agent] Error: {error}")

    finally:
        latency_ms = (time.time() - start_time) * 1000
        log_interaction(
            user_message=user_message,
            tools_called=tools_called,
            agent_response=response_text,
            latency_ms=latency_ms,
            error=error
        )

    return response_text
                
if __name__ == "__main__":
    response = run_agent("What is the current air quality status?")
    print(response)