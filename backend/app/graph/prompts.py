from pathlib import Path

import yaml

from app.config import settings

_cache: dict[str, dict] = {}


def load_tenant_config(tenant_id: str) -> dict:
    if tenant_id not in _cache:
        config_path: Path = settings.tenant_dir(tenant_id) / "config.yaml"
        with open(config_path, encoding="utf-8") as f:
            _cache[tenant_id] = yaml.safe_load(f)
    return _cache[tenant_id]


def build_system_prompt(tenant_id: str, retrieved_docs: list[str]) -> str:
    cfg = load_tenant_config(tenant_id)
    base_prompt: str = cfg.get("system_prompt", "Eres un asistente virtual útil.")

    if retrieved_docs:
        context_block = "\n\n---\n".join(retrieved_docs)
        return (
            f"{base_prompt}\n\n"
            "## CONTEXTO DEL PORTAFOLIO (información oficial de productos — úsala íntegramente):\n\n"
            f"{context_block}\n\n"
            "## INSTRUCCIONES DE RESPUESTA OBLIGATORIAS:\n"
            "1. Responde con mínimo 3 párrafos completos cuando te pregunten sobre un producto.\n"
            "2. Cubre: mecanismo de acción, indicaciones principales y posología básica.\n"
            "3. Si el contexto contiene una línea ![...](url) para el producto mencionado, "
            "INCLÚYELA TAL CUAL al inicio de tu respuesta (antes del texto).\n"
            "4. Finaliza siempre con: 'Para mayor detalle, consulte la ficha técnica completa.'\n"
            "5. NO respondas con una sola oración. Una respuesta incompleta es inaceptable."
        )
    return base_prompt


import re as _re

def extract_images_from_docs(docs: list[str], response_text: str) -> str:
    """Inyecta imágenes del contexto RAG en la respuesta si el modelo las omitió."""
    if "![" in response_text:
        return response_text  # ya tiene imágenes, no tocar

    for doc in docs:
        for match in _re.finditer(r"!\[[^\]]*\]\([^)]+\)", doc):
            img_md = match.group(0)
            # Extraer nombre del producto del alt text para verificar relevancia
            alt = _re.search(r"!\[([^\]]*)\]", img_md)
            if alt:
                product_hint = alt.group(1).split()[0].lower()
                if product_hint in response_text.lower():
                    return f"{img_md}\n\n{response_text}"
    return response_text


ROUTER_PROMPT = """Analiza el siguiente mensaje del médico y clasifica la intención.

Mensaje: "{message}"

Historial reciente:
{history}

Contexto:
- Captura de cita en curso: {appointment_in_progress}
- Captura de lead en curso: {lead_in_progress}

Responde con una sola palabra:
- "qa" → pregunta clínica/farmacológica sobre productos, indicaciones, dosis, efectos adversos, interacciones, estudios
- "appointment" → el médico quiere agendar una visita presencial o virtual con el representante, o ya hay una cita en curso
- "lead" → el médico quiere recibir información por email, muestras médicas, o dejar sus datos sin agendar visita
- "smalltalk" → saludo, despedida, agradecimiento, pregunta general no clínica

Si hay una cita en curso y no es claramente otro intent, fuerza "appointment".
Responde ÚNICAMENTE con una de las cuatro palabras, sin puntuación ni explicación."""


APPOINTMENT_COLLECTOR_PROMPT = """Eres el asistente de agenda de Pharmagen Laboratorios. Tu tarea es recopilar los datos necesarios para agendar una visita del representante médico con el Doctor/a.

Datos recopilados hasta ahora:
- Nombre del médico: {doctor_name}
- Email: {doctor_email}
- Especialidad: {specialty}
- Institución/Consultorio: {institution}
- Producto(s) de interés: {product_interest}
- Fecha/hora preferida: {preferred_datetime}
- Modalidad (presencial/virtual): {modality}

Historial de la conversación:
{history}

Reglas:
1. Solicita de forma natural los campos que faltan (valor "None" o vacío), uno o dos a la vez
2. Si ya tienes nombre y falta email, pide el email profesional
3. Cuando preguntes por fecha/hora, sé flexible: acepta "el martes", "próxima semana", "27 de mayo a las 3pm", etc.
4. Si todos los datos están completos, confirma el resumen de la cita y agradece
5. Trata al médico con respeto: "Doctor/Doctora", tono profesional y cálido
6. Responde SOLO con el mensaje para el médico, sin metadata ni JSON

Representante que se asignará: {rep_name}"""


LEAD_COLLECTOR_PROMPT = """Eres el asistente de Pharmagen Laboratorios recopilando datos de contacto del médico.

Datos recopilados:
- Nombre: {name}
- Email: {email}
- Interés (producto/información solicitada): {interest}

Historial:
{history}

Reglas:
1. Pide los campos faltantes de forma natural y profesional
2. Cuando tengas los 3 datos, confirma y menciona que un representante se pondrá en contacto en máx. 24 horas
3. Siempre en tono formal: "Doctor/Doctora"
4. Responde SOLO con el mensaje para el médico."""
