"""
Google Calendar integration via Service Account.

Setup:
1. Google Cloud Console → Enable Calendar API
2. Create Service Account → download JSON credentials
3. Share the rep's calendar with the SA email (Make changes to events)
4. Set GOOGLE_SA_CREDENTIALS_PATH and REP_CALENDAR_ID in .env
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import dateparser
from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.config import settings

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _get_service():
    creds = service_account.Credentials.from_service_account_file(
        str(settings.google_sa_credentials_path),
        scopes=SCOPES,
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


@dataclass
class AppointmentSlot:
    start: datetime
    end: datetime


def parse_datetime(text: str, tz_name: str | None = None) -> datetime | None:
    """Convierte texto en español a datetime. Ej: 'el martes a las 4pm', '27 de mayo 10:00'."""
    tz = ZoneInfo(tz_name or settings.timezone)
    parsed = dateparser.parse(
        text,
        languages=["es"],
        settings={
            "PREFER_DATES_FROM": "future",
            "RETURN_AS_TIMEZONE_AWARE": True,
            "TIMEZONE": str(tz),
        },
    )
    return parsed


def _is_business_hours(dt: datetime) -> bool:
    """Valida que el slot sea lun-vie 9:00-17:30."""
    tz = ZoneInfo(settings.timezone)
    local = dt.astimezone(tz)
    if local.weekday() >= 5:  # sábado=5, domingo=6
        return False
    if local.hour < 9 or local.hour >= 18:
        return False
    return True


def check_availability(start: datetime, duration_minutes: int = 30) -> bool:
    """Verifica si el slot está libre en el calendario del representante."""
    end = start + timedelta(minutes=duration_minutes)
    service = _get_service()
    body = {
        "timeMin": start.isoformat(),
        "timeMax": end.isoformat(),
        "items": [{"id": settings.rep_calendar_id}],
    }
    result = service.freebusy().query(body=body).execute()
    busy = result.get("calendars", {}).get(settings.rep_calendar_id, {}).get("busy", [])
    return len(busy) == 0


def suggest_alternatives(requested: datetime, count: int = 2) -> list[datetime]:
    """Sugiere slots alternativos cercanos al solicitado (siguientes 3 días laborables)."""
    alternatives = []
    candidate = requested + timedelta(hours=1)
    max_attempts = 48
    attempt = 0

    while len(alternatives) < count and attempt < max_attempts:
        if _is_business_hours(candidate) and check_availability(candidate):
            alternatives.append(candidate)
        candidate += timedelta(hours=1)
        attempt += 1

    return alternatives


def create_event(
    doctor_name: str,
    doctor_email: str,
    doctor_specialty: str,
    institution: str,
    product_interest: str,
    start: datetime,
    duration_minutes: int = 30,
    modality: str = "presencial",
    notes: str = "",
) -> dict:
    """
    Crea un evento en Google Calendar y devuelve el evento creado con su htmlLink.
    """
    end = start + timedelta(minutes=duration_minutes)
    tz = ZoneInfo(settings.timezone)

    summary = f"Visita médica: {doctor_name} — {doctor_specialty}"
    description = (
        f"Visita de representante médico Pharmagen Laboratorios\n\n"
        f"👨‍⚕️ Médico: {doctor_name}\n"
        f"🏥 Institución: {institution}\n"
        f"🔬 Especialidad: {doctor_specialty}\n"
        f"💊 Productos de interés: {product_interest}\n"
        f"📍 Modalidad: {modality.capitalize()}\n"
        f"👤 Representante: {settings.rep_name}\n"
        f"\n{notes}"
    )

    attendees = [{"email": doctor_email}]
    if settings.rep_email:
        attendees.append({"email": settings.rep_email})

    event_body = {
        "summary": summary,
        "description": description,
        "start": {
            "dateTime": start.astimezone(tz).isoformat(),
            "timeZone": settings.timezone,
        },
        "end": {
            "dateTime": end.astimezone(tz).isoformat(),
            "timeZone": settings.timezone,
        },
        "attendees": attendees,
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 24 * 60},
                {"method": "popup", "minutes": 30},
            ],
        },
        "conferenceData": None,
    }

    service = _get_service()
    created = (
        service.events()
        .insert(
            calendarId=settings.rep_calendar_id,
            body=event_body,
            sendUpdates="all",  # envía invitación por email
        )
        .execute()
    )

    return {
        "event_id": created["id"],
        "html_link": created.get("htmlLink", ""),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "summary": summary,
    }


def format_datetime_es(dt: datetime) -> str:
    """Formatea un datetime en español amigable. Ej: 'martes 6 de mayo, 4:00 PM'."""
    DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    MESES = [
        "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
    ]
    tz = ZoneInfo(settings.timezone)
    local = dt.astimezone(tz)
    dia_semana = DIAS[local.weekday()]
    hora = local.strftime("%I:%M %p").lstrip("0")
    return f"{dia_semana} {local.day} de {MESES[local.month]}, {hora}"
