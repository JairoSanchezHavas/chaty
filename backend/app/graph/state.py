from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class LeadDraft(TypedDict):
    name: str | None
    email: str | None
    interest: str | None
    complete: bool


class AppointmentDraft(TypedDict):
    doctor_name: str | None
    doctor_email: str | None
    specialty: str | None
    institution: str | None
    product_interest: str | None
    preferred_datetime_text: str | None   # texto original del usuario
    parsed_datetime: str | None            # ISO string tras parsear
    modality: str | None                   # "presencial" | "virtual"
    complete: bool


class GraphState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    tenant_id: str
    session_id: str
    intent: Literal["qa", "appointment", "lead", "smalltalk"] | None
    lead_draft: LeadDraft
    appointment_draft: AppointmentDraft
    retrieved_docs: list[str]
