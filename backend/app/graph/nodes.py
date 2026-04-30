"""
Nodos del grafo LangGraph para el agente representante médico Pharmagen.
"""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import settings
from app.graph.prompts import (
    APPOINTMENT_COLLECTOR_PROMPT,
    LEAD_COLLECTOR_PROMPT,
    ROUTER_PROMPT,
    build_system_prompt,
    extract_images_from_docs,
    load_tenant_config,
)
from app.graph.state import AppointmentDraft, GraphState, LeadDraft
from app.rag.retriever import similarity_search


_llm_cache: dict[float, BaseChatModel] = {}


def _get_llm(temperature: float = 0.7) -> BaseChatModel:
    if temperature not in _llm_cache:
        if settings.llm_backend == "vertex":
            from langchain_google_vertexai import ChatVertexAI
            _llm_cache[temperature] = ChatVertexAI(
                model_name=settings.vertex_chat_model,
                project=settings.google_cloud_project,
                location=settings.google_cloud_location,
                temperature=temperature,
                streaming=True,
            )
        else:
            _llm_cache[temperature] = ChatGoogleGenerativeAI(
                model=settings.gemini_chat_model,
                google_api_key=settings.gemini_api_key,
                temperature=temperature,
                streaming=True,
            )
    return _llm_cache[temperature]


def _history_text(messages: list, last_n: int = 6) -> str:
    recent = messages[-last_n:] if len(messages) > last_n else messages
    lines = []
    for m in recent:
        role = "Doctor/a" if isinstance(m, HumanMessage) else "Representante"
        lines.append(f"{role}: {m.content}")
    return "\n".join(lines)


def _last_user_message(messages: list) -> str:
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return m.content
    return ""


_SMALLTALK_RE = re.compile(
    r"^(hola|buenos?\s+d[ií]as?|buenas?\s+(tardes?|noches?)|gracias|de\s+nada|hasta\s+luego|adios|adiós|bye|ok|okay|perfecto|entendido|claro|s[íi])[\s.,!¡¿?]*$",
    re.IGNORECASE,
)
_APPT_KEYWORDS = ("agendar", "agenda", "cita", "visita", "reunión", "reunion", "visitarme", "vernos", "encuentro", "ver al representante")


def _fast_classify(msg: str, appt_in_progress: bool, lead_in_progress: bool) -> str | None:
    """Returns intent immediately for obvious cases, None when LLM is needed."""
    if appt_in_progress:
        return "appointment"
    if lead_in_progress:
        return "lead"
    if _SMALLTALK_RE.match(msg.strip()):
        return "smalltalk"
    lower = msg.lower()
    if any(k in lower for k in _APPT_KEYWORDS):
        return "appointment"
    return None


# ── router ───────────────────────────────────────────────────────────────────

async def router_node(state: GraphState) -> dict[str, Any]:
    messages = state["messages"]
    if not messages:
        return {"intent": "smalltalk"}

    last_msg = _last_user_message(messages)
    lead_draft = state.get("lead_draft") or {}
    appt_draft = state.get("appointment_draft") or {}

    lead_in_progress = (
        not lead_draft.get("complete", False)
        and any(lead_draft.get(k) is not None for k in ("name", "email", "interest"))
    )
    appt_in_progress = (
        not appt_draft.get("complete", False)
        and any(appt_draft.get(k) is not None for k in ("doctor_name", "doctor_email", "specialty"))
    )

    intent = _fast_classify(last_msg, appt_in_progress, lead_in_progress)
    if intent:
        print(f"\n[ROUTER] msg='{last_msg[:60]}' | fast_path='{intent}'")
        return {"intent": intent}

    prompt = ROUTER_PROMPT.format(
        message=last_msg,
        history=_history_text(messages[:-1]),
        appointment_in_progress=str(appt_in_progress),
        lead_in_progress=str(lead_in_progress),
    )

    llm = _get_llm(temperature=0.0)
    response = await llm.ainvoke(prompt)
    raw = response.content.strip().lower()

    if raw in ("qa", "appointment", "lead", "smalltalk"):
        intent = raw
    else:
        intent = "smalltalk"

    print(f"\n[ROUTER] msg='{last_msg[:60]}' | llm_raw='{raw}' | intent_final='{intent}'")
    return {"intent": intent}


# ── retrieve ─────────────────────────────────────────────────────────────────

def retrieve_node(state: GraphState) -> dict[str, Any]:
    query = _last_user_message(state["messages"])
    docs = similarity_search(state["tenant_id"], query, k=4)
    print(f"[RETRIEVE] query='{query[:60]}' | docs encontrados={len(docs)}")
    for i, d in enumerate(docs):
        print(f"  doc[{i}]: {d[:80].replace(chr(10),' ')!r}")
    return {"retrieved_docs": docs}


# ── answer ────────────────────────────────────────────────────────────────────

async def answer_node(state: GraphState) -> dict[str, Any]:
    retrieved_docs = state.get("retrieved_docs", [])
    cfg = load_tenant_config(state["tenant_id"])
    base_system = cfg.get("system_prompt", "Eres un asistente médico de Pharmagen.")

    messages = list(state["messages"])

    # Inyectar contexto RAG directamente en el último HumanMessage
    # (patrón más confiable con Gemini que ponerlo en el system prompt)
    if retrieved_docs and messages:
        context_block = "\n\n---\n".join(retrieved_docs)
        last_human_idx = next(
            (i for i in reversed(range(len(messages))) if isinstance(messages[i], HumanMessage)),
            None,
        )
        if last_human_idx is not None:
            original_q = messages[last_human_idx].content
            augmented = (
                "A continuación encontrarás información oficial de productos Pharmagen. "
                "Úsala para responder la consulta del médico de forma COMPLETA (mínimo 3 párrafos). "
                "Si hay imágenes ![Nombre](url) en el contexto, inclúyelas en tu respuesta.\n\n"
                f"=== INFORMACIÓN DEL PORTAFOLIO ===\n{context_block}\n"
                f"=== FIN DEL CONTEXTO ===\n\n"
                f"Consulta del médico: {original_q}"
            )
            messages = (
                messages[:last_human_idx]
                + [HumanMessage(content=augmented)]
                + messages[last_human_idx + 1 :]
            )

    print(f"[ANSWER] retrieved_docs={len(retrieved_docs)} | mensajes_totales={len(messages)}")
    messages_to_send = [SystemMessage(content=base_system)] + messages
    llm = _get_llm(temperature=0.7)
    response = await llm.ainvoke(messages_to_send)
    final_text = extract_images_from_docs(retrieved_docs, response.content)
    print(f"[ANSWER] respuesta LLM ({len(response.content)} chars): {response.content[:120]!r}")
    return {"messages": [AIMessage(content=final_text)], "retrieved_docs": []}


# ── appointment_collector ─────────────────────────────────────────────────────

async def appointment_collector_node(state: GraphState) -> dict[str, Any]:
    messages = state["messages"]
    draft: AppointmentDraft = state.get("appointment_draft") or {
        "doctor_name": None, "doctor_email": None, "specialty": None,
        "institution": None, "product_interest": None,
        "preferred_datetime_text": None, "parsed_datetime": None,
        "modality": None, "complete": False,
    }
    updated = dict(draft)
    last_msg = _last_user_message(messages)

    # Extracción progresiva de campos del último mensaje
    if not updated.get("doctor_name"):
        # Si el mensaje es corto y no es email ni fecha, asumir que es el nombre
        if len(last_msg.split()) <= 5 and "@" not in last_msg and not re.search(r"\d{1,2}[:/]\d{2}", last_msg):
            updated["doctor_name"] = last_msg.strip().title()
    elif not updated.get("doctor_email"):
        email_match = re.search(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}", last_msg)
        if email_match:
            updated["doctor_email"] = email_match.group(0)
    elif not updated.get("specialty"):
        updated["specialty"] = last_msg.strip()
    elif not updated.get("institution"):
        updated["institution"] = last_msg.strip()
    elif not updated.get("product_interest"):
        updated["product_interest"] = last_msg.strip()
    elif not updated.get("preferred_datetime_text"):
        updated["preferred_datetime_text"] = last_msg.strip()
        # Intentar parsear la fecha
        from app.integrations.gcal import parse_datetime
        parsed = parse_datetime(last_msg)
        if parsed:
            updated["parsed_datetime"] = parsed.isoformat()
    elif not updated.get("modality"):
        lower = last_msg.lower()
        if any(w in lower for w in ("virtual", "videollamada", "zoom", "teams", "online", "en línea")):
            updated["modality"] = "virtual"
        else:
            updated["modality"] = "presencial"

    # Verificar si el draft está completo
    required = ("doctor_name", "doctor_email", "specialty", "institution", "product_interest", "preferred_datetime_text")
    if all(updated.get(k) for k in required):
        updated["complete"] = True
        if not updated.get("modality"):
            updated["modality"] = "presencial"

    cfg = load_tenant_config(state["tenant_id"])
    prompt = APPOINTMENT_COLLECTOR_PROMPT.format(
        doctor_name=updated.get("doctor_name") or "pendiente",
        doctor_email=updated.get("doctor_email") or "pendiente",
        specialty=updated.get("specialty") or "pendiente",
        institution=updated.get("institution") or "pendiente",
        product_interest=updated.get("product_interest") or "pendiente",
        preferred_datetime=updated.get("preferred_datetime_text") or "pendiente",
        modality=updated.get("modality") or "pendiente",
        history=_history_text(messages),
        rep_name=settings.rep_name,
    )

    llm = _get_llm()
    response = await llm.ainvoke(prompt)
    return {"messages": [AIMessage(content=response.content)], "appointment_draft": updated}


# ── book_appointment ──────────────────────────────────────────────────────────

async def book_appointment_node(state: GraphState) -> dict[str, Any]:
    draft = state["appointment_draft"]

    if not settings.gcal_enabled:
        # GCal no configurado — confirmar sin crear evento real
        msg = (
            f"✅ **Cita registrada exitosamente**\n\n"
            f"Doctor/a: {draft.get('doctor_name')}\n"
            f"Especialidad: {draft.get('specialty')}\n"
            f"Institución: {draft.get('institution')}\n"
            f"Fecha/hora solicitada: {draft.get('preferred_datetime_text')}\n"
            f"Productos de interés: {draft.get('product_interest')}\n"
            f"Modalidad: {draft.get('modality', 'presencial').capitalize()}\n\n"
            f"**{settings.rep_name}** se pondrá en contacto para confirmar los detalles. "
            f"Recibirá una invitación de calendario a {draft.get('doctor_email')} en breve."
        )
        await _save_appointment_db(state, draft, event_id="", html_link="")
        return {"messages": [AIMessage(content=msg)], "appointment_draft": {**draft, "complete": True}}

    # GCal habilitado — verificar disponibilidad y crear evento
    from app.integrations.gcal import (
        check_availability,
        create_event,
        format_datetime_es,
        parse_datetime,
        suggest_alternatives,
    )
    from datetime import datetime

    parsed_dt = None
    if draft.get("parsed_datetime"):
        try:
            parsed_dt = datetime.fromisoformat(draft["parsed_datetime"])
        except Exception:
            pass

    if not parsed_dt and draft.get("preferred_datetime_text"):
        parsed_dt = parse_datetime(draft["preferred_datetime_text"])

    if not parsed_dt:
        msg = (
            "Disculpe, Doctor/a, no pude interpretar la fecha y hora que mencionó. "
            "¿Podría indicarme la fecha y hora en formato como 'lunes 12 de mayo a las 4:00 PM'?"
        )
        updated = dict(draft)
        updated["preferred_datetime_text"] = None
        updated["parsed_datetime"] = None
        updated["complete"] = False
        return {"messages": [AIMessage(content=msg)], "appointment_draft": updated}

    # Verificar disponibilidad
    is_free = check_availability(parsed_dt)
    if not is_free:
        alternatives = suggest_alternatives(parsed_dt, count=2)
        if alternatives:
            alts_text = "\n".join(f"  • {format_datetime_es(a)}" for a in alternatives)
            msg = (
                f"Lamentablemente, el horario solicitado ({format_datetime_es(parsed_dt)}) "
                f"no está disponible para {settings.rep_name}.\n\n"
                f"Le propongo las siguientes alternativas:\n{alts_text}\n\n"
                "¿Alguna de estas opciones le resulta conveniente, Doctor/a?"
            )
        else:
            msg = (
                f"El horario solicitado no está disponible. "
                "¿Podría indicarme otra fecha y hora de su preferencia?"
            )
        updated = dict(draft)
        updated["preferred_datetime_text"] = None
        updated["parsed_datetime"] = None
        updated["complete"] = False
        return {"messages": [AIMessage(content=msg)], "appointment_draft": updated}

    # Crear evento
    try:
        event = create_event(
            doctor_name=draft.get("doctor_name", ""),
            doctor_email=draft.get("doctor_email", ""),
            doctor_specialty=draft.get("specialty", ""),
            institution=draft.get("institution", ""),
            product_interest=draft.get("product_interest", ""),
            start=parsed_dt,
            modality=draft.get("modality", "presencial"),
        )
        await _save_appointment_db(state, draft, event["event_id"], event["html_link"])

        msg = (
            f"✅ **Visita agendada exitosamente**\n\n"
            f"📅 Fecha: {format_datetime_es(parsed_dt)}\n"
            f"👤 Representante: {settings.rep_name}\n"
            f"📍 Modalidad: {draft.get('modality', 'presencial').capitalize()}\n"
            f"💊 Productos: {draft.get('product_interest')}\n\n"
            f"Se ha enviado una invitación de calendario a **{draft.get('doctor_email')}**. "
            f"[Ver evento en calendario]({event['html_link']})\n\n"
            "¿Hay algo más en lo que pueda orientarle, Doctor/a?"
        )
    except Exception as e:
        msg = (
            f"La cita quedó registrada en nuestro sistema, sin embargo hubo un problema "
            f"al crear el evento de calendario. {settings.rep_name} le confirmará por email. "
            f"(Referencia técnica: {str(e)[:80]})"
        )
        await _save_appointment_db(state, draft, "", "")

    return {"messages": [AIMessage(content=msg)]}


async def _save_appointment_db(state: GraphState, draft: dict, event_id: str, html_link: str) -> None:
    from app.db.engine import AsyncSessionLocal
    from app.db.models import Appointment
    async with AsyncSessionLocal() as session:
        appt = Appointment(
            tenant_id=state["tenant_id"],
            session_id=state["session_id"],
            doctor_name=draft.get("doctor_name", ""),
            doctor_email=draft.get("doctor_email", ""),
            specialty=draft.get("specialty", ""),
            institution=draft.get("institution", ""),
            product_interest=draft.get("product_interest", ""),
            scheduled_at=draft.get("parsed_datetime") or draft.get("preferred_datetime_text", ""),
            modality=draft.get("modality", "presencial"),
            gcal_event_id=event_id,
            gcal_html_link=html_link,
        )
        session.add(appt)
        await session.commit()


# ── lead_collector ────────────────────────────────────────────────────────────

async def lead_collector_node(state: GraphState) -> dict[str, Any]:
    messages = state["messages"]
    lead_draft: LeadDraft = state.get("lead_draft") or {
        "name": None, "email": None, "interest": None, "complete": False
    }
    updated = dict(lead_draft)
    last_msg = _last_user_message(messages)

    if not updated.get("name"):
        if len(last_msg.split()) <= 5 and "@" not in last_msg:
            updated["name"] = last_msg.strip().title()
    elif not updated.get("email"):
        email_match = re.search(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}", last_msg)
        if email_match:
            updated["email"] = email_match.group(0)
    elif not updated.get("interest"):
        updated["interest"] = last_msg.strip()

    if all(updated.get(k) for k in ("name", "email", "interest")):
        updated["complete"] = True

    prompt = LEAD_COLLECTOR_PROMPT.format(
        name=updated.get("name") or "pendiente",
        email=updated.get("email") or "pendiente",
        interest=updated.get("interest") or "pendiente",
        history=_history_text(messages),
    )
    llm = _get_llm()
    response = await llm.ainvoke(prompt)
    return {"messages": [AIMessage(content=response.content)], "lead_draft": updated}


# ── save_lead ─────────────────────────────────────────────────────────────────

async def save_lead_node(state: GraphState) -> dict[str, Any]:
    from app.db.engine import AsyncSessionLocal
    from app.db.models import Lead
    draft = state["lead_draft"]
    async with AsyncSessionLocal() as session:
        session.add(Lead(
            tenant_id=state["tenant_id"],
            session_id=state["session_id"],
            name=draft.get("name", ""),
            email=draft.get("email", ""),
            interest=draft.get("interest", ""),
        ))
        await session.commit()
    return {}
