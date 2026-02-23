import sys
import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv('/home/ghost/air-agent/.env')

sys.path.append('/home/ghost/air-agent/ingestor')
sys.path.append('/home/ghost/air-agent/processor')
sys.path.append('/home/ghost/air-agent/agent')

from tools import get_current_metrics, assess_aqi, assess_device_health, get_air_quality_report

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """
You are an air quality monitoring agent. Your job is to analyze data from a low-cost 
air quality sensor station and provide clear, accurate assessments.

You have access to tools to fetch current metrics, assess air quality index, 
and evaluate device health. Always use the tools to get real data before responding.

When analyzing data:
- Report AQI levels clearly (Good, Moderate, Unhealthy)
- Flag any device health warnings immediately
- Be concise and factual
- If values seem anomalous, mention it
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
    """
    Runs the air quality agent with tool use loop.
    Returns the final text response.
    """
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
        messages.append(message)

        # No tool calls, return final response
        if not message.tool_calls:
            return message.content

        # Process tool calls
        for tool_call in message.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
            print(f"[agent] Calling tool: {fn_name} with args: {fn_args}")

            result = TOOL_MAP[fn_name](**fn_args)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, default=str)
            })


if __name__ == "__main__":
    response = run_agent("What is the current air quality status?")
    print(response)