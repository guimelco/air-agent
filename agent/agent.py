import sys
import os
import json
import time

from groq import Groq
from dotenv import load_dotenv
from telegram import send_message
from eval_logger import log_interaction
from openai import OpenAI

load_dotenv('/home/ghost/air-agent/.env')

sys.path.append('/home/ghost/air-agent/ingestor')
sys.path.append('/home/ghost/air-agent/processor')
sys.path.append('/home/ghost/air-agent/agent')
sys.path.append('/home/ghost/air-agent/notifier')
sys.path.append('/home/ghost/air-agent/db')

from tools import get_sensor_report, get_historical_context, save_relevant_event, TOOLS


client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

SYSTEM_PROMPT = """
Eres un agente inteligente de monitoreo para estaciones de sensores. Tu trabajo es analizar 
datos de sensores y proporcionar evaluaciones claras, estructuradas y perspicaces usando las herramientas.

ESTRUCTURA DEL REPORTE - organiza siempre tu respuesta en secciones:

1. MATERIAL PARTICULADO
   - Genera un reporte en base a la informacion obtenida de la herramienta "get_sensor_report".
   - Reporta y almacena eventos relevantes, analizando los ya existentes antes en "get_historical_context".
       - Criterios para considerar un evento: de "get_sensor_report", valor maximo > 2*mean y/o mean > 50ug/m3
       
2. CONDICIONES AMBIENTALES (temperature, humidity)
   - Genera un reporte en base a la informacion obtenida de la herramienta "get_sensor_report".


USO DE HERRAMIENTAS:

1. get_sensor_report, herramienta que te retorna metricas del analisis de la ultima hora.
    - Tu debes interpretar la informacion en base a las etiquetas.
2. save_relevant_event, herramienta que sirve para registrar informacion de un evento relevante.
    - Tu debes proporcionar la informacion disponible de "get_sensor_report"
3. get_historical_context, herramienta que te permite ver los eventos anteriores para comparar eventos nuevos.
    - Esto te permite identificar patrones repetidos y analizar tendencias

Formato de respuesta: texto plano, sin asteriscos, sin markdown, sin bullets con *.
Usa números para las secciones y guiones simples para listas.

"""
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_sensor_report",
            "description": "Obtiene datos sintetizados de los sensores de la estación por módulo. Retorna métricas estadísticas crudas (mean, min, max, variance, samples) para interpretación del agente. No incluye índices pre-calculados.",
            "parameters": {
                "type": "object",
                "properties": {
                    "modules": {
                        "type": "array",
                        "description": "Lista de módulos a incluir. Opciones: 'particle' (pm1, pm25, pm4, pm10), 'environmental' (temperature, humidity), 'chemical' (o3, no2, so2), 'device' (batería, código de falla, temp interna). Si no se especifica, retorna todos.",
                        "items": {
                            "type": "string",
                            "enum": ["particle", "environmental", "chemical", "device"]
                        }
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_historical_context",
            "description": "Consulta eventos históricos relevantes para la misma hora y día de semana. Úsala después de get_sensor_report para identificar si el evento actual es un patrón recurrente o algo atípico.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hour": {
                    "type": "integer",
                    "description": "Hora del día en formato 24h (0-23)"
                    },
                    "day_of_week": {
                    "type": "string",
                    "description": "Día de la semana en inglés: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday"
                    }
                },
                "required": ["hour", "day_of_week"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_relevant_event",
            "description": "Guarda un evento relevante en la base de datos histórica. Llama esta tool cuando detectes valores atípicos, picos significativos, patrones inusuales o cualquier condición que merezca registro para análisis futuro.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trigger": {
                        "type": "string",
                        "description": "Causa del evento. Ej: pm25_spike, pm10_mean_high, temperature_anomaly, correlacion_pm_gases"
                    },
                    "pattern_match": {
                        "type": "string",
                        "description": "Clasificación temporal. Opciones: morning_peak, evening_peak, nocturnal, daytime, weekend, atypical"
                    },
                    "agent_notes": {
                        "type": "string",
                        "description": "Interpretación del agente sobre el evento — qué detectó y por qué es relevante"
                    },
                    "pm25_mean": {"type": "number"},
                    "pm25_max": {"type": "number"},
                    "pm10_mean": {"type": "number"},
                    "pm10_max": {"type": "number"},
                    "temperature": {"type": "number"},
                    "humidity": {"type": "number"}
                },
                "required": ["trigger", "pattern_match", "agent_notes"]
            }
        }
    }
]

TOOL_MAP = {
    "get_sensor_report": get_sensor_report,
    "get_historical_context": get_historical_context,
    "save_relevant_event": save_relevant_event
}

def run_agent(user_message: str) -> str:
    start_time = time.time()
    tools_called = []
    tool_results = []
    error = None
    response_text = None

    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]

        while True:
            response = client.chat.completions.create(
                model="arcee-ai/trinity-large-preview:free",
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
                    tool_results.append({
                        "tool": fn_name,
                        "result": result
                    })

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
            tool_results=tool_results,
            agent_response=response_text,
            latency_ms=latency_ms,
            error=error
        )

    return response_text