from pathlib import Path

import yaml
from sqlalchemy import select

from app.config import settings
from app.db.engine import AsyncSessionLocal, init_db
from app.db.models import Tenant


async def seed() -> None:
    await init_db()
    async with AsyncSessionLocal() as session:
        tenants_dir: Path = settings.tenants_dir
        for tenant_path in tenants_dir.iterdir():
            config_file = tenant_path / "config.yaml"
            if not config_file.exists():
                continue
            with open(config_file, encoding="utf-8") as f:
                cfg = yaml.safe_load(f)

            tenant_id = cfg["id"]
            result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
            existing = result.scalar_one_or_none()
            if not existing:
                session.add(
                    Tenant(
                        id=tenant_id,
                        name=cfg["name"],
                        brand_color=cfg.get("brand_color", "#1A1A2E"),
                        brand_accent=cfg.get("brand_accent", "#E94560"),
                        greeting=cfg["greeting"],
                    )
                )
                print(f"[seed] Tenant '{tenant_id}' creado.")
            else:
                print(f"[seed] Tenant '{tenant_id}' ya existe.")
        await session.commit()
