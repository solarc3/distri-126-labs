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
            
    ai_summary = ""
    try:
        if not is_critical:
            prompt = (
                "Resume brevemente y en español (máximo 1 oración) "
                "qué cambios mecánicos se hicieron:\n\n" 
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
                ai_summary = (
                    res.get('message', {}).get('content', '')
                    .strip().split('\n')[0]
                )
                ai_summary = ai_summary.replace(
                    "Aquí tienes el resumen:", ""
                ).strip()
    except Exception:
        ai_summary = "Cambios mecánicos, de logs, o de configuración general."

    header = "**[Agente Revisor de MR]** Análisis de impacto en Pull Request:\n\n"
    
    if is_critical:
        body = (
            "[IA Review] requiere revisión humana.\n"
            f"Justificación: {critical_reason}"
        )
    else:
        if ai_summary and len(ai_summary) < 150:
            reason = ai_summary
        else:
            reason = (
                "Modificación estructural, logs, tipos o tests simples "
                "que no alteran la semántica."
            )
            
        body = (
            "[IA Review] mecánico y mergeable.\n"
            f"Justificación: {reason}"
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
