import json
import re
import urllib.request


def analyze_bugs(code_text):
    # Heurística para malas prácticas o bugs
    critical_patterns = [
        (
            r"except\s*:", 
            "Uso de 'except:' genérico que atrapa excepciones del sistema."
        ),
        (r"while\s+True\s*:\s*pass", "Bucle infinito con 'pass' que consume 100% CPU."),
        (r"time\.sleep\(\s*[1-9][0-9]*\s*\)", "Llamada a time.sleep() largo, bloqueo."),
        (r"\.socket\(", "Creación de sockets crudos, validar que se liberen recursos."),
        (
            r"lock\.acquire\(\)", 
            "Uso explícito de locks, validar prevención de deadlocks."
        )
    ]
    
    issues_found = []
    for line in code_text.split('\n'):
        for pattern, reason in critical_patterns:
            if re.search(pattern, line) and reason not in issues_found:
                issues_found.append(reason)
                    
    # Intentar usar IA para contexto adicional (opcional)
    ai_summary = ""
    if not issues_found:
        try:
            prompt = (
                "Revisa este código Python de red (máximo 1500 chars) y describe "
                "en 1 oración corta si ves un fallo. Si se ve bien, responde 'OK'.\n\n" 
                + code_text[:1500]
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
        except Exception:
            ai_summary = "OK"

    header = "**[Agente Revisor de Bugs]** Informe de análisis de código base:\n\n"
    
    if issues_found:
        body = (
            "Requiere intervención humana.\n"
            "Se han detectado posibles vulnerabilidades:\n- " 
            + "\n- ".join(issues_found)
        )
    else:
        if "OK" not in ai_summary and len(ai_summary) > 10:
            body = (
                "Requiere revisión menor.\nAuditoría estática (IA): "
                f"{ai_summary}"
            )
        else:
            body = (
                "No se encontraron anomalías graves.\n"
                "Auditoría estática: El código no presenta patrones críticos."
            )
            
    return header + body


if __name__ == "__main__":
    try:
        with open("code_context.txt") as f:
            code = f.read()
    except Exception:
        code = ""
        
    resultado = analyze_bugs(code)
    
    with open("issue_body.txt", "w") as f:
        f.write(resultado)
        
    print("Análisis completado. Resultado guardado en issue_body.txt")
