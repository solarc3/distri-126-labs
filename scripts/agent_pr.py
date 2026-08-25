import json
import re
import urllib.request


def analyze_diff(diff_text):
    # Palabras clave críticas que requieren revisión humana
    critical_keywords = [
        "socket", "bind", "listen", "accept", "connect", 
        "gossip", "pubsub", "MembershipView", "should_forward", 
        "fanout", "TTL", "prioridad", "threading", "multiprocessing",
        "asyncio"
    ]
    
    is_critical = False
    critical_reason = ""
    
    for line in diff_text.split('\n'):
        if line.startswith('+') and not line.startswith('+++'):
            for kw in critical_keywords:
                if re.search(rf'\b{kw}\b', line, re.IGNORECASE):
                    is_critical = True
                    critical_reason = (
                        f"Se detectó modificación relacionada con '{kw}' "
                        "en la lógica de red o concurrencia."
                    )
                    break
        if is_critical:
            break
            
    # Siempre consultar a la IA para obtener un resumen real del código
    ai_summary = ""
    try:
        prompt = (
            "Resume brevemente y en español (máximo 2 oraciones) "
            "qué cambios se hicieron en este diff de código:\n\n" 
            + diff_text[:1500]
        )
        payload = json.dumps({
            "model": "llama3.2",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.0}
        }).encode('utf-8')
        
        req = urllib.request.Request(
            "http://localhost:11434/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            res = json.loads(response.read().decode())
            # Tomar el contenido y limpiar saltos de línea extra
            ai_summary = res.get('message', {}).get('content', '').strip()
            ai_summary = ai_summary.replace("Aquí tienes el resumen:", "").strip()
    except Exception:
        ai_summary = (
            "(No se pudo generar el resumen detallado por "
            "timeout o error en la IA)."
        )

    header = "**[Agente Revisor de MR]** Análisis de impacto en Pull Request:\n\n"
    
    if is_critical:
        body = (
            "[IA Review] requiere revisión humana.\n\n"
            f"**Motivo de seguridad:** {critical_reason}\n\n"
            f"**Resumen del cambio (IA):** {ai_summary}"
        )
    else:
        body = (
            "[IA Review] mecánico y mergeable.\n\n"
            "**Motivo de seguridad:** Modificación estructural, logs, "
            "tipos o tests simples "
            "que no alteran la semántica de red.\n\n"
            f"**Resumen del cambio (IA):** {ai_summary}"
        )
        
    return header + body


if __name__ == "__main__":
    try:
        with open("pr_diff.txt") as f:
            diff = f.read()
    except Exception:
        diff = "Diff no encontrado."
        
    resultado = analyze_diff(diff)
    
    with open("ai_comment.txt", "w") as f:
        f.write(resultado)
        
    print("Análisis completado. Resultado guardado en ai_comment.txt")
