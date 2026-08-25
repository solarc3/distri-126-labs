def analyze_docs(docs_text):
    # Palabras clave obligatorias
    required_keywords = [
        ("slurm", "Falta documentación sobre el despliegue en Slurm (sbatch/srun)."),
        ("docker", "Falta documentación sobre Docker o Compose."),
        ("gossip", "No se explica la arquitectura de descubrimiento (Gossip)."),
        ("pubsub", "No se explica la arquitectura de publicación/suscripción (PubSub).")
    ]
    
    docs_lower = docs_text.lower()
    missing_docs = []
    
    for kw, reason in required_keywords:
        if kw not in docs_lower:
            missing_docs.append(reason)
            
    header = "**[Agente Documentador]** Revisión de estado de documentación:\n\n"
    
    if missing_docs:
        body = (
            "Requiere intervención humana:\n- " 
            + "\n- ".join(missing_docs)
        )
    else:
        body = (
            "La documentación parece estar completa y "
            "cumple los requisitos básicos (Slurm, Docker, framework descritos)."
        )
        
    return header + body


if __name__ == "__main__":
    try:
        with open("docs_context.txt") as f:
            docs = f.read()
    except Exception:
        docs = ""
        
    resultado = analyze_docs(docs)
    
    with open("issue_body.txt", "w") as f:
        f.write(resultado)
        
    print("Análisis completado. Resultado guardado en issue_body.txt")
