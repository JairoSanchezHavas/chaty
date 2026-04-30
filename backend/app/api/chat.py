from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.db.engine import AsyncSessionLocal
from app.db.models import Tenant
from app.graph.builder import get_graph

router = APIRouter()


class ChatRequest(BaseModel):
    tenant_id: str
    session_id: str
    message: str


async def _tenant_exists(tenant_id: str) -> bool:
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
        return result.scalar_one_or_none() is not None


@router.post("/chat")
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Mensaje vacío")

    if not await _tenant_exists(req.tenant_id):
        raise HTTPException(status_code=404, detail=f"Tenant '{req.tenant_id}' no encontrado")

    graph = await get_graph()
    config = {"configurable": {"thread_id": f"{req.tenant_id}:{req.session_id}"}}

    # Solo pasar los campos que cambian por turno.
    # LangGraph carga appointment_draft, lead_draft, intent y retrieved_docs desde el checkpoint.
    input_state = {
        "messages": [HumanMessage(content=req.message)],
        "tenant_id": req.tenant_id,
        "session_id": req.session_id,
    }

    # Nodos que generan la respuesta visible al usuario (nombres del grafo, no de la función)
    _STREAMING_NODES = {"answer", "appointment_collector", "lead_collector"}

    async def event_generator():
        try:
            async for event in graph.astream_events(input_state, config=config, version="v2"):
                kind = event["event"]
                node = event.get("metadata", {}).get("langgraph_node", "")

                if kind == "on_chat_model_stream" and node in _STREAMING_NODES:
                    chunk = event["data"].get("chunk")
                    if chunk and chunk.content:
                        yield {"event": "token", "data": chunk.content}

            yield {"event": "done", "data": ""}
        except Exception as e:
            yield {"event": "error", "data": str(e)}

    return EventSourceResponse(event_generator())
