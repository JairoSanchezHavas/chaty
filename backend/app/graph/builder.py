from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from app.config import settings
from app.graph.nodes import (
    answer_node,
    appointment_collector_node,
    book_appointment_node,
    lead_collector_node,
    retrieve_node,
    router_node,
    save_lead_node,
)
from app.graph.state import GraphState


def _route_after_router(state: GraphState) -> str:
    intent = state.get("intent", "smalltalk")
    if intent == "qa":
        return "retrieve"
    if intent == "appointment":
        return "appointment_collector"
    if intent == "lead":
        return "lead_collector"
    return "answer"


def _route_after_appointment(state: GraphState) -> str:
    draft = state.get("appointment_draft") or {}
    if draft.get("complete"):
        return "book_appointment"
    return END


def _route_after_lead(state: GraphState) -> str:
    draft = state.get("lead_draft") or {}
    if draft.get("complete"):
        return "save_lead"
    return END


def build_graph(checkpointer: AsyncSqliteSaver):
    graph = StateGraph(GraphState)

    graph.add_node("router", router_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("answer", answer_node)
    graph.add_node("appointment_collector", appointment_collector_node)
    graph.add_node("book_appointment", book_appointment_node)
    graph.add_node("lead_collector", lead_collector_node)
    graph.add_node("save_lead", save_lead_node)

    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router", _route_after_router,
        ["retrieve", "appointment_collector", "lead_collector", "answer"]
    )
    graph.add_edge("retrieve", "answer")
    graph.add_edge("answer", END)
    graph.add_conditional_edges(
        "appointment_collector", _route_after_appointment,
        ["book_appointment", END]
    )
    graph.add_edge("book_appointment", END)
    graph.add_conditional_edges(
        "lead_collector", _route_after_lead,
        ["save_lead", END]
    )
    graph.add_edge("save_lead", END)

    return graph.compile(checkpointer=checkpointer)


_compiled_graph = None
_conn = None


async def init_graph() -> None:
    global _compiled_graph, _conn
    import aiosqlite
    _conn = await aiosqlite.connect(settings.checkpoints_path)
    saver = AsyncSqliteSaver(_conn)
    await saver.setup()
    _compiled_graph = build_graph(saver)


async def get_graph():
    if _compiled_graph is None:
        await init_graph()
    return _compiled_graph


async def close_graph() -> None:
    global _conn
    if _conn:
        await _conn.close()
        _conn = None
