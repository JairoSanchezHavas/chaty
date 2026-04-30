from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_session
from app.db.models import Lead

router = APIRouter()


@router.get("/leads")
async def list_leads(
    tenant_id: str = Query(..., description="ID del tenant"),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Lead).where(Lead.tenant_id == tenant_id).order_by(Lead.created_at.desc())
    )
    leads = result.scalars().all()
    return [
        {
            "id": lead.id,
            "name": lead.name,
            "email": lead.email,
            "interest": lead.interest,
            "session_id": lead.session_id,
            "created_at": lead.created_at.isoformat() if lead.created_at else None,
        }
        for lead in leads
    ]
