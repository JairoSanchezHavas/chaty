from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_session
from app.db.models import Appointment

router = APIRouter()


@router.get("/appointments")
async def list_appointments(
    tenant_id: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Appointment)
        .where(Appointment.tenant_id == tenant_id)
        .order_by(Appointment.created_at.desc())
    )
    appts = result.scalars().all()
    return [
        {
            "id": a.id,
            "doctor_name": a.doctor_name,
            "doctor_email": a.doctor_email,
            "specialty": a.specialty,
            "institution": a.institution,
            "product_interest": a.product_interest,
            "scheduled_at": a.scheduled_at,
            "modality": a.modality,
            "status": a.status,
            "gcal_html_link": a.gcal_html_link,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in appts
    ]
