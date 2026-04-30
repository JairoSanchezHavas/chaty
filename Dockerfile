# Usamos una imagen ligera de Python 3.11
FROM python:3.11-slim

# Directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiamos las dependencias para aprovechar el cache de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto del código del proyecto
COPY . .

# Cloud Run escucha en el puerto 8080 por defecto
EXPOSE 8080

# Comando para iniciar FastAPI (ajusta 'main:app' según tu punto de entrada)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]