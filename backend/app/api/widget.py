from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.db.engine import AsyncSessionLocal
from app.db.models import Tenant

router = APIRouter()


@router.get("/widget/config/{tenant_id}")
async def widget_config(tenant_id: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    return {
        "tenant_id": tenant.id,
        "name": tenant.name,
        "greeting": tenant.greeting,
        "brand_color": tenant.brand_color,
        "brand_accent": tenant.brand_accent,
    }
