# Chaty MVP — Documentación del Producto

> Versión `0.2.0` · Stack: LangGraph 0.2 · FastAPI 0.115 · Gemini 2.5 Flash · ChromaDB 0.5 · SQLite

---

## ¿Qué es Chaty?

Chaty es una plataforma de chatbots conversacionales embebibles, diseñada para que agencias de marketing puedan desplegarlo en sitios web de clientes sin depender de herramientas tercerizadas.

El MVP implementa un **representante médico virtual** para Pharmagen Laboratorios: responde preguntas clínicas sobre el portafolio de productos con información oficial, agenda visitas con el representante real, y captura datos de contacto de médicos interesados.

La arquitectura es **multi-tenant desde el inicio**: un solo backend sirve múltiples clientes, cada uno con su propia base de conocimiento, configuración visual y datos aislados.

---

## Stack técnico

| Capa | Tecnología | Versión mínima |
|------|-----------|---------------|
| Orquestación conversacional | LangGraph | 0.2.50 |
| API backend | FastAPI + uvicorn | 0.115 |
| Streaming | sse-starlette (SSE) | 2.1 |
| LLM | Gemini 2.5 Flash (AI Studio o Vertex AI) | — |
| Embeddings | `gemini-embedding-001` / `text-embedding-004` | — |
| Vector store | ChromaDB (embedded, persistente) | 0.5.20 |
| Base de datos | SQLite + SQLAlchemy async (aiosqlite) | — |
| Memoria conversacional | LangGraph SqliteSaver (checkpoints) | — |
| Calendario | Google Calendar API (service account) | — |
| Widget frontend | Vanilla JS, shadow DOM, sin build step | — |
| Configuración | pydantic-settings + `.env` | 2.4 |

---

## Características implementadas

### 1. Agente conversacional con 4 intenciones

El núcleo es un grafo LangGraph que clasifica cada mensaje en una de cuatro intenciones y ejecuta el nodo correspondiente:

| Intención | Descripción | Nodo(s) ejecutados |
|-----------|-------------|-------------------|
| `qa` | Pregunta clínica o farmacológica | `retrieve` → `answer` |
| `appointment` | Agendamiento de visita con el representante | `appointment_collector` → `book_appointment` |
| `lead` | Solicitud de información por email o muestras | `lead_collector` → `save_lead` |
| `smalltalk` | Saludo, despedida, agradecimiento | `answer` (sin RAG) |

El router tiene un **fast-path por expresiones regulares** que clasifica sin llamar al LLM en ~60% de los turnos típicos (saludos obvios, keywords de cita), reduciendo la latencia de esos turnos a ~50ms.

### 2. Q&A con RAG (Retrieval-Augmented Generation)

- La knowledge base de cada tenant se chunka por secciones markdown (`## heading`) al arrancar el servidor
- Cada chunk se embebe con Gemini y se indexa en ChromaDB bajo la colección `kb_{tenant_id}`
- En cada pregunta clínica: se embebe la query, se recuperan los top-4 chunks más similares (distancia coseno), y se inyectan directamente en el `HumanMessage` del LLM
- El contexto RAG va en el mensaje del usuario (no en el system prompt) — patrón más confiable con Gemini
- Si el contexto contiene imágenes `![Nombre](url)`, el modelo las incluye en la respuesta y el widget las renderiza como `<img>`

**Knowledge base actual de Pharmagen:**

| Archivo | Contenido | Chunks |
|---------|-----------|--------|
| `productos.md` | Cardilex, Glucovital XR, Bronchease, Neurofine — mecanismo, indicaciones, evidencia clínica | ~10 |
| `posologia.md` | Dosis, ajustes por población, interacciones | ~6 |
| `indicaciones.md` | Criterios de prescripción por patología | ~4 |
| `faq.md` | Preguntas frecuentes de médicos | ~3 |
| **Total** | | **23 chunks** |

### 3. Agendamiento de citas (flujo multi-turno)

El `appointment_collector_node` recopila 6 campos de forma conversacional, uno o dos por turno:

1. Nombre del médico
2. Email profesional (validado con regex)
3. Especialidad
4. Institución o consultorio
5. Producto(s) de interés
6. Fecha y hora preferida (texto libre: "el martes a las 4pm", "27 de mayo")

La fecha se parsea con `dateparser` con soporte de español. Al completarse el draft, el grafo rutea a `book_appointment_node` que:

- **Con Google Calendar configurado:** verifica disponibilidad real del representante, crea el evento con ambos como asistentes (el médico recibe invitación por email), y devuelve el link del evento
- **Sin Google Calendar:** confirma la cita y la guarda en SQLite — el representante hace el seguimiento manual

El draft persiste en el checkpoint de SQLite entre turnos. Si el médico interrumpe y regresa (misma sesión), retoma donde quedó.

### 4. Captura de leads

Flujo de 3 campos: nombre, email e interés. Al completarse, el registro se inserta en la tabla `leads` con `tenant_id` y `session_id`. Accesible vía `GET /api/leads?tenant_id=pharmagen`.

### 5. Streaming de tokens en tiempo real

El endpoint `POST /api/chat` devuelve `text/event-stream` (SSE). El backend usa `graph.astream_events(version="v2")` y emite un evento `token` por cada chunk del LLM:

```
event: token
data: Por

event: token
data:  supuesto

event: token
data: , Doctor...

event: done
data:
```

El primer token llega en menos de 1 segundo. El widget acumula los chunks y actualiza la burbuja en tiempo real.

### 6. Widget embebible (shadow DOM)

Un único archivo `widget.js` servido desde el backend. Se incrusta con:

```html
<script src="https://tu-servidor/widget.js" data-tenant="pharmagen"></script>
```

Características del widget:

- **Shadow DOM**: CSS completamente aislado, sin colisiones con los estilos del sitio cliente
- **Burbuja flotante** en la esquina inferior derecha, configurable por `brand_color`
- **Renderizado de markdown**: negrita, cursiva, listas, links, imágenes de producto (`![alt](url)` → `<img>`)
- **Branding dinámico**: carga `name`, `greeting`, `brand_color`, `brand_accent` del tenant vía API
- **Memoria de sesión**: genera un UUID por tenant y lo guarda en `localStorage`. La conversación sobrevive recargas de página
- **Auto-resize** del textarea al escribir mensajes largos
- **Responsive**: se adapta a pantallas menores de 420px

### 7. Memoria conversacional persistente

LangGraph usa `AsyncSqliteSaver` como checkpointer. El `thread_id` es `{tenant_id}:{session_id}`. Cada turno:

1. LangGraph carga el estado completo del checkpoint (historial de mensajes + drafts)
2. Ejecuta los nodos correspondientes
3. Guarda el nuevo estado en el checkpoint

El historial de mensajes usa `add_messages` (acumulativo). Los campos como `appointment_draft` y `lead_draft` son reemplazados (no acumulados), lo que permite actualizar el draft sin perder datos de turnos anteriores.

### 8. Multi-tenancy

Cada tenant tiene su propio directorio en `backend/app/tenants/{id}/`:

```
config.yaml        → nombre, saludo, branding, system_prompt
knowledge/*.md     → contenido indexado en ChromaDB (colección separada)
images/            → imágenes de productos servidas en /tenants/{id}/images/
```

El backend aísla completamente los datos: colecciones ChromaDB, registros SQLite (leads, citas), y configuración de sistema. Agregar un tenant es crear la carpeta y reiniciar.

### 9. Dual backend LLM / Embeddings

La variable `LLM_BACKEND` selecciona entre:

- **`gemini`** (default): Google AI Studio, requiere `GEMINI_API_KEY`, sin proyecto GCP
- **`vertex`**: Vertex AI, requiere proyecto GCP y ADC o service account JSON

Ambos usan la misma interfaz de LangChain (`BaseChatModel`, `Embeddings`), por lo que el cambio es transparente para el resto del código. Ver [`autenticacion.md`](autenticacion.md) para setup detallado.

---

## Modelo de datos

### Tabla `tenants`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | TEXT PK | Identificador del tenant (ej. `pharmagen`) |
| `name` | TEXT | Nombre para mostrar |
| `brand_color` | TEXT | Color principal del widget (hex) |
| `brand_accent` | TEXT | Color de acento (hex) |
| `greeting` | TEXT | Mensaje de bienvenida |
| `created_at` | DATETIME | Timestamp de creación |

### Tabla `leads`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | INT PK | Autoincremental |
| `tenant_id` | TEXT | FK implícita a tenants |
| `session_id` | TEXT | UUID de la sesión del navegador |
| `name` | TEXT | Nombre del médico |
| `email` | TEXT | Email profesional |
| `interest` | TEXT | Producto o información solicitada |
| `created_at` | DATETIME | Timestamp |

### Tabla `appointments`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | INT PK | Autoincremental |
| `tenant_id` | TEXT | FK implícita a tenants |
| `session_id` | TEXT | UUID de la sesión |
| `doctor_name` | TEXT | Nombre del médico |
| `doctor_email` | TEXT | Email profesional |
| `specialty` | TEXT | Especialidad |
| `institution` | TEXT | Clínica u hospital |
| `product_interest` | TEXT | Producto(s) de interés |
| `scheduled_at` | TEXT | Datetime ISO o texto original |
| `modality` | TEXT | `"presencial"` o `"virtual"` |
| `gcal_event_id` | TEXT | ID del evento en Google Calendar (vacío si GCal deshabilitado) |
| `gcal_html_link` | TEXT | Link al evento (vacío si GCal deshabilitado) |
| `status` | TEXT | `"confirmed"` (único estado actual) |
| `created_at` | DATETIME | Timestamp |

---

## API

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| `POST` | `/api/chat` | Ninguna | Mensaje → SSE stream de tokens |
| `GET` | `/api/widget/config/{tenant_id}` | Ninguna | Branding del widget |
| `GET` | `/api/leads?tenant_id=` | Ninguna | Lista leads capturados |
| `GET` | `/api/appointments?tenant_id=` | Ninguna | Lista citas agendadas |
| `GET` | `/widget.js` | Ninguna | Bundle JS del widget |
| `GET` | `/demo/pharmagen.html` | Ninguna | Página demo |
| `GET` | `/tenants/{id}/images/{file}` | Ninguna | Imágenes de productos |
| `GET` | `/health` | Ninguna | Estado del servidor + `gcal_enabled` |

---

## Limitaciones actuales

Estas son las limitaciones conocidas del MVP, organizadas por prioridad para producción.

### Críticas (bloquean producción)

**Sin autenticación en endpoints de administración**
`/api/leads` y `/api/appointments` son públicos. Cualquiera que conozca la URL puede leer todos los datos capturados. Para producción se necesita al menos una API key o Bearer token.

**SQLite no es apto para múltiples workers**
SQLite tiene bloqueos de escritura a nivel de archivo. Con más de un proceso uvicorn (ej. `--workers 4`), se producirán errores de concurrencia. El sistema completo — base de datos, checkpoints y ChromaDB — vive en un solo proceso.

**ChromaDB embedded no escala horizontalmente**
El cliente `PersistentClient` de ChromaDB no puede ser compartido entre procesos ni máquinas. No es posible desplegar en múltiples instancias o contenedores sin migrar a ChromaDB server o PGVector.

**Sin rate limiting ni validación de entrada**
El endpoint `/api/chat` acepta cualquier payload sin límites de tamaño de mensaje ni frecuencia de requests. Un usuario malicioso puede generar costos elevados en la API de Gemini.

---

### Importantes (degradan calidad)

**Extracción de campos del appointment por posición, no por NLU**
El `appointment_collector_node` usa una cadena de `if/elif` que asigna el campo faltante siguiente basándose en el orden secuencial del mensaje. Esto falla si el médico proporciona múltiples datos en un solo mensaje ("Soy el Dr. López, cardiólogo") o si responde fuera de orden. El LLM solo genera el texto de respuesta, no extrae los campos.

**El parser de fechas puede fallar en formatos inusuales**
`dateparser` maneja bien el español estándar ("el martes a las 4pm", "próximo lunes") pero falla con expresiones coloquiales muy específicas ("ahorita en la tarde", "como a eso de las 3"). Cuando falla, el bot pide la fecha de nuevo en formato explícito.

**El historial de mensajes crece indefinidamente**
Todos los mensajes de una sesión se acumulan en el checkpoint. Para sesiones muy largas esto aumenta el tamaño del prompt enviado al LLM, incrementando costos y latencia. El router solo usa los últimos 6 mensajes, pero `answer_node` envía el historial completo.

**`extract_images_from_docs` no funciona en modo streaming**
Esta función es un fallback que inyecta imágenes de producto al final de la respuesta si el LLM las omitió. Con streaming de tokens, para cuando se detecta la omisión los tokens ya fueron enviados. En la práctica el LLM incluye las imágenes en ~90% de los casos cuando el contexto RAG las contiene.

**Sin deduplicación de leads**
Si el mismo médico envía sus datos dos veces (en sesiones distintas), se crean dos registros independientes en la tabla `leads`. No hay lógica de upsert por email.

---

### Menores (no bloquean demo)

**Sin soporte para tablas markdown en el widget**
El renderizador de markdown del widget convierte negrita, cursiva, listas, links e imágenes, pero no tablas (`| col | col |`). Si la knowledge base contiene tablas, se muestran como texto plano.

**El widget no autentica el tenant**
Cualquier sitio web puede embeber el widget con `data-tenant="pharmagen"`. No hay verificación de dominio de origen. En producción se debería validar contra una lista de dominios autorizados por tenant.

**La ingesta no detecta cambios en la knowledge base**
Al arrancar, si la colección ChromaDB del tenant ya tiene datos, se salta la ingesta. Si se modifica un archivo `.md`, hay que borrar manualmente la colección y reiniciar para re-indexar.

**Un solo representante por tenant**
La configuración de GCal solo soporta un `REP_CALENDAR_ID` por tenant. No hay lógica de round-robin o asignación de representante según especialidad o zona geográfica.

**Sin notificaciones activas**
Cuando se agenda una cita sin GCal habilitado, el representante solo se entera si revisa la tabla `appointments` manualmente o vía el endpoint de la API. No hay email, webhook ni Slack alert.

**Sin soporte para voz o archivos**
El widget solo maneja texto. No hay transcripción de audio ni lectura de PDFs o imágenes enviadas por el médico.

**Sin observabilidad**
No hay trazas, métricas de costo por tenant, ni logs estructurados de conversaciones. Es imposible saber qué preguntas no pudo responder el bot sin revisar la terminal.

---

## Ruta de evolución hacia producción

| Mejora | Impacto | Esfuerzo estimado |
|--------|---------|-------------------|
| Auth en `/api/leads` y `/api/appointments` | Crítico | 1 día |
| Migrar a Postgres + pgvector | Crítico | 2-3 días |
| Rate limiting (slowapi) | Crítico | 0.5 días |
| Extracción de campos con LLM (structured output) | Alto | 1-2 días |
| Re-indexación automática al detectar cambios | Medio | 1 día |
| Langfuse para trazas y costos | Medio | 1 día |
| Truncar historial a N turnos | Bajo | 2 horas |
| Soporte de tablas markdown en widget | Bajo | 2 horas |
| WhatsApp vía 360dialog | Alto | 3-5 días |
| Handoff a agente humano (Chatwoot) | Alto | 3-5 días |
| Múltiples representantes con asignación | Medio | 2-3 días |
| Notificaciones por email al agendar | Medio | 1 día |
