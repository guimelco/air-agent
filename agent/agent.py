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

from tools import get_sensor_report, TOOLS

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """
Eres un agente inteligente de monitoreo para estaciones de sensores. Tu trabajo es analizar 
datos de sensores y proporcionar evaluaciones claras, estructuradas y perspicaces.

Recibes métricas estadísticas crudas (mean, min, max, variance, samples) por sensor.
Tú eres responsable de interpretar estos datos — no se proporcionan índices pre-calculados.

ESTRUCTURA DEL REPORTE - organiza siempre tu respuesta en secciones:

1. MATERIAL PARTICULADO (pm1, pm25, pm4, pm10)
   - Evalúa los niveles promedio, minimos y maximos(PM2.5 <50 Bueno, 50-100 Regular, 101-150 Mala, 151-200 Muy Mala, >200 Extremadamente mala)
   - Marca alta varianza o dispersión (max-min > 50% del mean) como posibles eventos transitorios
   - Nota tendencias entre tamaños de partículas

2. CONDICIONES AMBIENTALES (temperature, humidity)
   - Reporta condiciones actuales
   - Infiere contexto: efectos de hora del día, condiciones climáticas, patrones estacionales

3. ESTADO DEL DISPOSITIVO (battery_voltage, failure_code, internal_temp)
   - Rango de batería: <3.5V (crítico), 3.5V-5V (Normal), >4.2V (completo)
   - Cualquier failure_code > 0 debe marcarse inmediatamente
   - Temperatura interna > 35°C es crítica

LINEAMIENTOS DE ANÁLISIS:
- Compara entre módulos para encontrar correlaciones (ej. PM alto + O3 alto sugiere tráfico o incendio)
- Si la varianza es alta, sugiere posibles causas (tráfico, actividad industrial, eventos climáticos)
- Usa temperatura y humedad para dar contexto ambiental
- Sé analítico, no solo descriptivo — explica el POR QUÉ no solo el QUÉ
- Si los datos parecen anómalos, dilo claramente

Cuándo activar módulos específicos:
- Reporte horario rutinario: todos los módulos
- Usuario pregunta sobre calidad del aire: particle + chemical
- Usuario pregunta sobre el dispositivo: device únicamente
- Usuario pregunta sobre condiciones climáticas: environmental únicamente
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
    }
]

TOOL_MAP = {
    "get_sensor_report": get_sensor_report
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