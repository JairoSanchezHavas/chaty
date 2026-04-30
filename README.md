# Chaty — Chatbot Widget Embebible

Plataforma multi-tenant de chatbots conversacionales con RAG. Demo activo: **Pharmagen Laboratorios** (representante médico virtual).

Stack: **LangGraph · FastAPI · Gemini · ChromaDB · SQLite · Widget JS vanilla**

---

## Requisitos previos

- Python 3.11 o superior
- Una de las dos opciones de autenticación con Google:
  - **Google AI Studio** (más fácil): API Key gratuita en [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
  - **Vertex AI**: proyecto GCP + `gcloud auth application-default login` (ver [`docs/autenticacion.md`](docs/autenticacion.md))
- *(Opcional)* Cuenta de servicio de Google Cloud para Google Calendar

---

## Instalación

### 1. Clonar el repo y crear entorno virtual

```bash
git clone <repo-url>
cd chaty

# Crear entorno virtual dentro de backend/
python -m venv backend/venv

# Activar — macOS/Linux
source backend/venv/bin/activate

# Activar — Windows (PowerShell)
backend\venv\Scripts\Activate.ps1

# Activar — Windows (CMD)
backend\venv\Scripts\activate.bat
```

### 2. Instalar dependencias

```bash
cd backend
pip install -r requirements.txt
```

### 3. Configurar variables de entorno

```bash
cp .env.example .env
```

Edita `backend/.env` con tus valores. Elige uno de los dos backends:

**Opción A — Google AI Studio (default, más fácil):**
```env
LLM_BACKEND=gemini
GEMINI_API_KEY=AIza...          # aistudio.google.com/apikey
GEMINI_CHAT_MODEL=gemini-2.5-flash
GEMINI_EMBED_MODEL=gemini-embedding-001
```

**Opción B — Vertex AI con ADC:**
```env
LLM_BACKEND=vertex
GOOGLE_CLOUD_PROJECT=mi-proyecto-gcp
GOOGLE_CLOUD_LOCATION=us-central1
VERTEX_CHAT_MODEL=gemini-2.5-flash
VERTEX_EMBED_MODEL=text-embedding-004
# Luego: gcloud auth application-default login
```

Para instrucciones detalladas de Vertex AI (ADC, service accounts, troubleshooting) ver [`docs/autenticacion.md`](docs/autenticacion.md).

### 4. (Opcional) Configurar Google Calendar

1. En [Google Cloud Console](https://console.cloud.google.com), crea un proyecto y habilita la **Google Calendar API**.
2. Crea una **cuenta de servicio** → descarga el JSON de credenciales.
3. Guarda el JSON en `backend/secrets/gcal-sa.json`.
4. En Google Calendar, comparte tu calendario con el email de la cuenta de servicio dándole permisos de **edición**.
5. Copia el **Calendar ID** (en Configuración del calendario → Integrar calendario) y ponlo en `REP_CALENDAR_ID`.

Si omites este paso, las citas se guardan en SQLite y el bot confirma sin link de calendario.

---

## Arrancar el servidor

```bash
# Asegúrate de tener el venv activo y estar en backend/
uvicorn app.main:app --reload --port 8000
```

En el primer arranque:
- Se crean los tenants en SQLite (`pharmagen`, `tcl`)
- Se indexa la knowledge base de cada tenant en ChromaDB (23 chunks para pharmagen)

---

## Probar el widget

Abre en el navegador (requiere el servidor corriendo — **no** abrir el HTML directamente como archivo):

```
http://localhost:8000/demo/pharmagen.html
```

La burbuja del chat aparece en la esquina inferior derecha.

### Ejemplos de conversación

**Q&A clínica (RAG):**
- "¿Cuál es el mecanismo de acción de Bronchease?"
- "¿Qué dosis de Cardilex se usa en prevención cardiovascular primaria?"
- "¿Glucovital XR tiene estudios en pacientes con insuficiencia renal?"

**Agendamiento:**
- "Quiero agendar una visita con el representante"
- "Me gustaría que viniera a mi consultorio la próxima semana"

**Lead:**
- "Quiero recibir información sobre Neurofine por email"
- "¿Me pueden enviar muestras médicas de Bronchease?"

---

## Endpoints API

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/api/chat` | Enviar mensaje (SSE token streaming) |
| `GET` | `/api/widget/config/{tenant_id}` | Branding del widget |
| `GET` | `/api/leads?tenant_id=pharmagen` | Leads capturados |
| `GET` | `/api/appointments?tenant_id=pharmagen` | Citas agendadas |
| `GET` | `/widget.js` | Bundle del widget embebible |
| `GET` | `/demo/pharmagen.html` | Página demo Pharmagen |
| `GET` | `/health` | Health check + estado de GCal |

### Ejemplo — ver leads capturados

```bash
curl http://localhost:8000/api/leads?tenant_id=pharmagen
```

---

## Embeber en cualquier sitio web

```html
<script src="http://localhost:8000/widget.js" data-tenant="pharmagen"></script>
```

En producción reemplaza `http://localhost:8000` con la URL de tu servidor.

---

## Estructura del proyecto

```
chaty/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI + lifespan (seed + ingest + graph)
│   │   ├── config.py             # Settings con pydantic-settings
│   │   ├── api/
│   │   │   ├── chat.py           # POST /api/chat — SSE streaming
│   │   │   ├── leads.py          # GET /api/leads
│   │   │   ├── appointments.py   # GET /api/appointments
│   │   │   └── widget.py         # GET /api/widget/config/{id}
│   │   ├── db/
│   │   │   ├── engine.py         # SQLAlchemy async + aiosqlite
│   │   │   ├── models.py         # Tenant, Lead, Appointment
│   │   │   └── seed.py           # Crea tenants al arrancar
│   │   ├── rag/
│   │   │   ├── store.py          # ChromaDB PersistentClient
│   │   │   ├── ingest.py         # Chunking markdown → embeddings Gemini → Chroma
│   │   │   └── retriever.py      # similarity_search(tenant_id, query, k=4)
│   │   ├── graph/
│   │   │   ├── state.py          # GraphState, AppointmentDraft, LeadDraft
│   │   │   ├── nodes.py          # router, retrieve, answer, collectors, book/save
│   │   │   ├── builder.py        # StateGraph + SqliteSaver checkpointer
│   │   │   └── prompts.py        # System prompts y templates
│   │   ├── integrations/
│   │   │   └── gcal.py           # Google Calendar: parse, check, create event
│   │   └── tenants/
│   │       └── pharmagen/
│   │           ├── config.yaml   # name, greeting, brand_color, system_prompt
│   │           ├── knowledge/    # .md indexados en ChromaDB
│   │           └── images/       # Imágenes de productos (servidas en /tenants/)
│   ├── secrets/
│   │   └── gcal-sa.json          # (gitignored) Service account Google Calendar
│   ├── data/                     # (gitignored) chaty.db, chroma/, checkpoints.db
│   ├── requirements.txt
│   └── .env.example
├── widget/
│   └── widget.js                 # IIFE — shadow DOM, SSE streaming, markdown render
├── demo/
│   └── pharmagen.html            # Página demo del portal médico
└── docs/
    ├── mvp.md                    # Producto: características, modelo de datos, limitaciones
    ├── flujos.md                 # Flujos conversacionales con diagramas Mermaid
    └── autenticacion.md          # Google AI Studio vs Vertex AI (ADC, service accounts)
```

---

## Agregar un nuevo tenant

1. Crea la carpeta `backend/app/tenants/{id}/`
2. Agrega `config.yaml`:
```yaml
name: "Nombre del Asistente"
greeting: "Hola, ¿en qué puedo ayudarte?"
brand_color: "#1A1A2E"
brand_accent: "#E94560"
system_prompt: "Eres un asistente virtual de..."
```
3. Agrega archivos `.md` en `knowledge/` con el contenido a indexar
4. Inserta el tenant en la base de datos (o agrega a `seed.py`)
5. Reinicia el servidor — la ingesta ocurre automáticamente al arrancar

---

## Roadmap post-MVP

- [ ] Postgres + pgvector (cambiar driver SQLAlchemy + retriever)
- [ ] Redis para estado caliente de sesión
- [ ] Langfuse para observabilidad (trazas y costos por tenant)
- [ ] WhatsApp vía 360dialog (nuevo endpoint `/webhook/wa` que reutiliza el grafo)
- [ ] Chatwoot para handoff a agente humano
- [ ] Auth en endpoints de administración
