from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import appointments, chat, leads, widget
from app.config import settings
from app.db.seed import seed
from app.graph.builder import close_graph, init_graph
from app.rag.ingest import ingest_tenant


@asynccontextmanager
async def lifespan(app: FastAPI):
    await seed()

    tenants_dir: Path = settings.tenants_dir
    for tenant_path in tenants_dir.iterdir():
        if (tenant_path / "config.yaml").exists():
            ingest_tenant(tenant_path.name)

    await init_graph()
    yield
    await close_graph()


app = FastAPI(title="Chaty — Pharmagen API", version="0.2.0", lifespan=lifespan)

origins = ["*"] if settings.cors_origins == "*" else settings.cors_origins.split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(chat.router, prefix="/api")
app.include_router(leads.router, prefix="/api")
app.include_router(appointments.router, prefix="/api")
app.include_router(widget.router, prefix="/api")

_base = Path(__file__).parent.parent.parent  # raíz del repo
widget_dir = _base / "widget"
demo_dir = _base / "demo"

if widget_dir.exists():
    app.mount("/widget", StaticFiles(directory=str(widget_dir)), name="widget_static")

if demo_dir.exists():
    app.mount("/demo", StaticFiles(directory=str(demo_dir), html=True), name="demo_static")

# Servir imágenes de tenants — /tenants/<id>/images/<archivo>
# Usar ruta absoluta derivada de la ubicación de este archivo (backend/app/tenants)
tenants_static_dir = Path(__file__).parent / "tenants"
if tenants_static_dir.exists():
    app.mount("/tenants", StaticFiles(directory=str(tenants_static_dir)), name="tenants_static")


@app.get("/widget.js")
async def serve_widget_js():
    path = _base / "widget" / "widget.js"
    return FileResponse(str(path), media_type="application/javascript")


@app.get("/health")
async def health():
    return {"status": "ok", "gcal_enabled": settings.gcal_enabled}
