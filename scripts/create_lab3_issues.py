import urllib.request
import json
import os
import sys

def create_issue(title, body, labels, token):
    url = "https://api.github.com/repos/solarc3/distri-126-labs/issues"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    data = {"title": title, "body": body, "labels": labels}
    req = urllib.request.Request(url, json.dumps(data).encode("utf-8"), headers)
    
    try:
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode())
            print(f"Creado Issue #{res['number']}: {title}")
    except Exception as e:
        print(f"Error creando '{title}': {e}")

if __name__ == "__main__":
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("Error: Debes setear la variable de entorno GITHUB_TOKEN o GH_TOKEN")
        sys.exit(1)
        
    issues = [
        {
            "title": "[Lab 3] Capa de Red y Gossip: Membresía y Tolerancia a Fallos",
            "body": "Implementar el protocolo de membresía gossip para el descubrimiento de pares, mantenimiento de vista parcial y detección de fallos por timeout. Definir y justificar el fanout de membresía.",
            "labels": ["gossip", "lab3", "enhancement"]
        },
        {
            "title": "[Lab 3] Capa Pub/Sub: Ruteo y should_forward",
            "body": "Implementar la lógica de subscripciones a tópicos geográficos (comunas). Desarrollar la función explícita `should_forward` considerando TTL y prioridad. Evitar flooding ciego.",
            "labels": ["pubsub", "lab3", "enhancement"]
        },
        {
            "title": "[Lab 3] Capa de Datos: Generadores y Replay de Series",
            "body": "Implementar la ingesta y caché del Dominio B (Aire) mediante archivos reales de Open-Meteo/SINCA. Desarrollar los generadores estocásticos (Poisson) para Dominio A y los simuladores de percepción ciudadana para ambos dominios usando fórmulas del informe.",
            "labels": ["datos", "lab3", "enhancement"]
        },
        {
            "title": "[Lab 3] Capa Analítica: Métricas y Frontend",
            "body": "Implementar la lógica que calcule las métricas de convergencia y la divergencia (percepción vs realidad). Desarrollar el frontend mínimo para visualizar el estado agregado por tópico y canal, consumiendo desde el shared FS.",
            "labels": ["analítica", "lab3", "enhancement"]
        },
        {
            "title": "[Lab 3] Infraestructura: CI/CD, Compose y Slurm",
            "body": "Configurar y asegurar tests unitarios (rojo bloquea merge), pipelines en GitHub Actions, andamiaje de Compose multi-perfil (delitos/aire), y los scripts de Slurm y FS compartido para la ejecución real en DIINF.",
            "labels": ["infraestructura", "lab3", "enhancement"]
        }
    ]

    print("Creando issues obligatorios para Lab 3...")
    for i in issues:
        create_issue(i["title"], i["body"], i["labels"], token)
    print("¡Listo!")
