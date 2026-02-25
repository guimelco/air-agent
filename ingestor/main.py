import sys

sys.path.append('/home/ghost/air-agent/agent')
sys.path.append('/home/ghost/air-agent/processor')
sys.path.append('/home/ghost/air-agent/ingestor')
sys.path.append('/home/ghost/air-agent/notifier')

from agent import run_agent

if __name__ == "__main__":
    print("[scheduler] Running hourly air quality check...")
    try:
        response = run_agent("Ejecuta un reporte general de la estación de monitoreo.")
        preview = response[:100] if response else "No response"
        print("[scheduler] Done: " + preview)
    except Exception as e:
        print("[scheduler] Error: " + str(e))