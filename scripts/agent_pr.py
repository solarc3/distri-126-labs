import json
import re
import urllib.request


def ask_ollama(prompt):
    """Función auxiliar para hacer peticiones a Ollama."""
    try:
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
        with urllib.request.urlopen(req, timeout=45) as response:
            res = json.loads(response.read().decode())
            content = res.get('message', {}).get('content', '').strip()
            # Limpiar preámbulos molestos de la IA si aparecen
            if "Aquí tienes el resumen" in content:
                content = content.split(":", 1)[-1].strip()
            return content
    except Exception as e:
        print(f"Error consultando Ollama: {e}")
        return ""


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
    
    # 1. Heurística de seguridad (Búsqueda global)
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
            
    # 2. Análisis Iterativo del Diff por Archivos (Map-Reduce)
    
    # Separar el diff enorme en bloques por cada archivo modificado
    file_diffs = []
    current_file_diff = []
    
    for line in diff_text.split('\n'):
        if line.startswith('diff --git'):
            if current_file_diff:
                file_diffs.append('\n'.join(current_file_diff))
            current_file_diff = [line]
        else:
            current_file_diff.append(line)
            
    if current_file_diff:
        file_diffs.append('\n'.join(current_file_diff))

    # A. Fase Map: Generar un mini-resumen por cada archivo
    file_summaries = []
    for f_diff in file_diffs:
        # Extraer nombre del archivo para pasarlo al prompt
        match = re.search(r'diff --git a/.*? b/(.*)', f_diff)
        filename = match.group(1) if match else "archivo_desconocido"
        
        # Recortar el diff individual solo si es brutalmente largo (por ej. un JSON)
        # 1500 chars suele ser suficiente para entender el contexto de UN archivo.
        safe_f_diff = f_diff[:1500] 
        
        prompt = (
            f"El archivo '{filename}' fue modificado. "
            "Revisa los cambios (líneas con +) y escribe EXACTAMENTE 1 sola "
            "oración en español resumiendo qué se le hizo. Si son cambios estéticos "
            "o de linter, dilo. No des explicaciones, solo la oración.\n\n"
            f"{safe_f_diff}"
        )
        print(f"-> Analizando {filename}...")
        summary = ask_ollama(prompt)
        if summary:
            file_summaries.append(f"- {filename}: {summary}")
            
    # B. Fase Reduce: Consolidar todos los resúmenes en un párrafo final
    ai_summary = ""
    if file_summaries:
        consolidated_text = "\n".join(file_summaries)
        reduce_prompt = (
            "Eres un Technical Lead. Tienes el siguiente reporte de cambios "
            "hechos en distintos archivos durante un Pull Request:\n\n"
            f"{consolidated_text}\n\n"
            "Escribe un resumen global cohesivo y fluido en español de máximo "
            "3 oraciones explicando qué características, módulos o arreglos se "
            "implementaron en general en este Pull Request. No hagas una lista."
        )
        print("-> Consolidando resumen global...")
        final_summary = ask_ollama(reduce_prompt)
        
        if final_summary:
            ai_summary = final_summary
        else:
            # Fallback si el reduce falla
            ai_summary = "Se modificaron varios archivos, pero la IA no pudo consolidar el resumen global."
    else:
        ai_summary = (
            "(No se detectaron archivos válidos en el diff o la IA falló "
            "al generar el resumen iterativo)."
        )

    # 3. Construir la respuesta final
    header = "**[Agente Revisor de MR]** Análisis de impacto en Pull Request:\n\n"
    
    if is_critical:
        body = (
            "[IA Review] requiere revisión humana.\n\n"
            f"**Motivo de seguridad:** {critical_reason}\n\n"
            f"**Resumen global del PR (IA):** {ai_summary}"
        )
    else:
        body = (
            "[IA Review] mecánico y mergeable.\n\n"
            "**Motivo de seguridad:** Modificación estructural, logs, "\
            "tipos o tests simples que no alteran la semántica de red.\n\n"
            f"**Resumen global del PR (IA):** {ai_summary}"
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
