# Autenticación — Google AI Studio vs Vertex AI

Chaty soporta dos backends para LLM y embeddings. Se selecciona con la variable `LLM_BACKEND` en `.env`.

---

## Comparativa rápida

| | Google AI Studio | Vertex AI |
|---|---|---|
| Variable clave | `GEMINI_API_KEY` | ADC / `GOOGLE_APPLICATION_CREDENTIALS` |
| Requiere proyecto GCP | No | Sí |
| Requiere facturación GCP | No (tiene free tier) | Sí |
| Modelos disponibles | Gemini 2.5 Flash/Pro | Gemini 2.5 Flash/Pro + modelos propios |
| Modelo de embeddings | `gemini-embedding-001` | `text-embedding-004` |
| Ideal para | Desarrollo local, demos | Producción, entornos corporativos |

---

## Opción A — Google AI Studio (default)

### Configuración

```env
LLM_BACKEND=gemini
GEMINI_API_KEY=AIzaSy...
GEMINI_CHAT_MODEL=gemini-2.5-flash
GEMINI_EMBED_MODEL=gemini-embedding-001
```

### Obtener la API key

1. Ve a [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Haz clic en **Create API key**
3. Copia la clave y pégala en `GEMINI_API_KEY`

No requiere cuenta de facturación. Tiene límites generosos en el free tier (60 req/min en Flash).

---

## Opción B — Vertex AI con ADC (Application Default Credentials)

ADC es el mecanismo estándar de Google Cloud para autenticación sin manejar claves manualmente. Las credenciales se obtienen del entorno — ya sea gcloud CLI, una cuenta de servicio, o el metadata server de una VM/Cloud Run.

### Jerarquía de búsqueda de ADC

Cuando el código llama a Vertex AI, las credenciales se resuelven en este orden:

```
1. Variable GOOGLE_APPLICATION_CREDENTIALS (service account JSON)
   ↓ si no existe
2. Credenciales de usuario de gcloud CLI
   (~/.config/gcloud/application_default_credentials.json)
   ↓ si no existe
3. Credenciales del metadata server (solo en GCE, Cloud Run, GKE, etc.)
   ↓ si no existe
4. Error: no se encontraron credenciales
```

### Configuración mínima en `.env`

```env
LLM_BACKEND=vertex
GOOGLE_CLOUD_PROJECT=mi-proyecto-gcp
GOOGLE_CLOUD_LOCATION=us-central1
VERTEX_CHAT_MODEL=gemini-2.5-flash
VERTEX_EMBED_MODEL=text-embedding-004
```

---

## Autenticación con gcloud CLI (desarrollo local)

Es el método más cómodo para desarrollo. No requiere manejar archivos JSON.

### 1. Instalar gcloud CLI

```bash
# macOS (Homebrew)
brew install --cask google-cloud-sdk

# Windows — descargar el instalador desde:
# https://cloud.google.com/sdk/docs/install

# Linux
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
```

### 2. Inicializar y autenticar

```bash
# Inicializar (elige proyecto GCP cuando te lo pida)
gcloud init

# Autenticar para Application Default Credentials
gcloud auth application-default login
```

Este comando abre el navegador para que hagas login con tu cuenta de Google. Las credenciales se guardan en `~/.config/gcloud/application_default_credentials.json` y son leídas automáticamente por todas las librerías de Google Cloud.

### 3. Establecer el proyecto por defecto

```bash
gcloud config set project mi-proyecto-gcp

# Verificar
gcloud config list
```

### 4. Habilitar la API de Vertex AI

```bash
gcloud services enable aiplatform.googleapis.com
```

### 5. Verificar que funciona

```bash
# Probar que las credenciales ADC están activas
gcloud auth application-default print-access-token
```

Si imprime un token largo, todo está configurado. Reinicia el servidor de Chaty y debería usar Vertex AI automáticamente.

---

## Autenticación con Service Account (producción / CI/CD)

Recomendado cuando el código corre en un servidor sin acceso a gcloud CLI (por ejemplo, un contenedor Docker, GitHub Actions, etc.).

### 1. Crear la cuenta de servicio

```bash
# Crear la cuenta
gcloud iam service-accounts create chaty-vertex \
    --display-name="Chaty Vertex AI"

# Asignar roles necesarios
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:chaty-vertex@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"

# Descargar la clave JSON
gcloud iam service-accounts keys create ./secrets/vertex-sa.json \
    --iam-account=chaty-vertex@$PROJECT_ID.iam.gserviceaccount.com
```

### 2. Configurar en `.env`

```env
LLM_BACKEND=vertex
GOOGLE_CLOUD_PROJECT=mi-proyecto-gcp
GOOGLE_CLOUD_LOCATION=us-central1

# Apuntar al JSON descargado
GOOGLE_APPLICATION_CREDENTIALS=./secrets/vertex-sa.json
```

> **Importante:** `GOOGLE_APPLICATION_CREDENTIALS` es una variable estándar de Google Cloud leída automáticamente por todas las librerías — no es necesario pasarla al código explícitamente.

### 3. Agregar al `.gitignore`

```
backend/secrets/
```

Nunca subas archivos `.json` de service accounts al repositorio.

---

## Migrar de AI Studio a Vertex AI

Si ya tienes ChromaDB con embeddings indexados con `gemini-embedding-001` (AI Studio) y cambias a Vertex AI con `text-embedding-004`, **los vectores son incompatibles** — tienen dimensionalidades distintas.

Debes re-indexar borrando la colección existente:

```bash
# Opción 1: borrar el directorio de Chroma
rm -rf backend/data/chroma/

# Opción 2: solo borrar la colección del tenant
python -c "
import chromadb
client = chromadb.PersistentClient(path='backend/data/chroma')
client.delete_collection('pharmagen')
"
```

Luego reinicia el servidor — la ingesta ocurre automáticamente al arrancar.

---

## Ubicaciones disponibles en Vertex AI

Para `GOOGLE_CLOUD_LOCATION`, elige la región más cercana a tus usuarios:

| Región | Ubicación |
|--------|-----------|
| `us-central1` | Iowa, EE.UU. (default) |
| `us-east4` | Virginia, EE.UU. |
| `us-west1` | Oregon, EE.UU. |
| `europe-west4` | Países Bajos |
| `europe-west1` | Bélgica |
| `asia-northeast1` | Tokio |
| `northamerica-northeast1` | Montreal (LATAM más cercano) |

Para uso desde México/LATAM, `us-central1` o `northamerica-northeast1` suelen tener la menor latencia.

---

## Troubleshooting

### `google.auth.exceptions.DefaultCredentialsError`
No se encontraron credenciales ADC. Solución:
```bash
gcloud auth application-default login
```

### `PermissionDenied: 403`
La cuenta no tiene el rol `aiplatform.user`. Solución:
```bash
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="user:tu@email.com" \
    --role="roles/aiplatform.user"
```

### `Project not found` / `API not enabled`
```bash
gcloud services enable aiplatform.googleapis.com --project=$PROJECT_ID
```

### Los embeddings dan resultados raros después de cambiar de backend
Los vectores en ChromaDB son de AI Studio y son incompatibles con los de Vertex. Borra y re-indexa (ver sección "Migrar de AI Studio a Vertex AI" arriba).
