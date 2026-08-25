import json
import re
import urllib.request


def ask_ollama(system_prompt, user_prompt):
    """Función auxiliar para hacer peticiones a Ollama."""
    try:
        payload = json.dumps({
            "model": "llama3.2",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
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
    # 1. Separar el diff enorme en bloques por cada archivo modificado
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

    # 2. Fase Map: Generar un mini-resumen por cada archivo
    file_summaries = []
    for f_diff in file_diffs:
        match = re.search(r'diff --git a/.*? b/(.*)', f_diff)
        filename = match.group(1) if match else "archivo_desconocido"
        
        safe_f_diff = f_diff[:1500] 
        
        system_prompt = (
            "You are a code analyzer. Summarize the changes in 1 Spanish sentence."
        )
        user_prompt = (
            f"El archivo '{filename}' fue modificado. "
            "Revisa los cambios y escribe EXACTAMENTE 1 sola "
            "oración en español resumiendo qué se le hizo. Si son cambios "
            "estéticos o de linter, dilo. No des explicaciones.\n\n"
            f"{safe_f_diff}"
        )
        print(f"-> Analizando {filename}...")
        summary = ask_ollama(system_prompt, user_prompt)
        if summary:
            file_summaries.append(f"- {filename}: {summary}")
            
    # 3. Fase Reduce: Consolidar todos los resúmenes en un párrafo final
    ai_summary = ""
    if file_summaries:
        consolidated_text = "\n".join(file_summaries)
        reduce_system = (
            "You are a Technical Lead. Write a 3-sentence summary in Spanish "
            "of the provided PR changes. Do not use lists."
        )
        reduce_user = (
            "Tienes el siguiente reporte de cambios hechos en distintos archivos "
            "durante un Pull Request:\n\n"
            f"{consolidated_text}\n\n"
            "Escribe un resumen global cohesivo y fluido en español de máximo "
            "3 oraciones explicando qué características, módulos o arreglos se "
            "implementaron en general. No hagas una lista."
        )
        print("-> Consolidando resumen global...")
        final_summary = ask_ollama(reduce_system, reduce_user)
        
        if final_summary:
            ai_summary = final_summary
        else:
            ai_summary = (
                "Se modificaron varios archivos, pero la IA no pudo "
                "consolidar el resumen global."
            )
    else:
        ai_summary = (
            "(No se detectaron archivos válidos en el diff o la IA falló "
            "al generar el resumen iterativo)."
        )

    # 4. Fase de Clasificación (Decisión de la IA basada en el resumen)
    decision_system = (
        "You are a strict CI/CD classifier bot. Your ONLY job is to output a "
        "classification string in Spanish based on the "
        "provided PR summary. "
        "DO NOT explain the code. DO NOT say hello.\n\n"
        "If the summary mentions changes to networking, gossip, pubsub, sockets "
        "or threads, output EXACTLY this string and "
        "nothing else:\n"
        "[IA Review] requiere revisión humana. "
        "Justificación: [reason in spanish]\n\n"
        "If the summary mentions ONLY logs, docs, linters, or UI/Frontend, "
        "output EXACTLY this string and "
        "nothing else:\n"
        "[IA Review] mecánico y mergeable. "
        "Justificación: [reason in spanish]\n\n"
        "Example Output:\n"
        "[IA Review] requiere revisión humana. "
        "Justificación: Se detectaron "
        "cambios en el protocolo de propagación Gossip."
    )
    decision_user = f"Clasifica este Pull Request en base a este resumen general:\n\n{ai_summary}"
    
    print("-> Tomando decisión final...")
    raw_decision = ask_ollama(decision_system, decision_user)
    
    # Filtro de Seguridad Final
    if "[IA Review]" in raw_decision:
        final_decision = raw_decision
    else:
        final_decision = (
            "[IA Review] requiere revisión humana.\n"
            "Justificación: (El modelo "
            "LLM falló al seguir el formato estricto y devolvió texto no estructurado)."
        )

    # 5. Construir la respuesta final
    header = "**[Agente Revisor de MR]** Análisis de impacto en Pull Request:\n\n"
    body = (
        f"{final_decision}\n\n"
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
