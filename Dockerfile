# 1. Imagen base oficial ligera de Python
FROM python:3.11-slim

# 2. Variables de entorno estándar para ejecución de Python y Streamlit
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# 3. Instalar curl y herramientas de compilación para librerías como OCI / Crypto
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 4. Directorio de trabajo
WORKDIR /app

# 5. Instalar dependencias aprovechando la caché
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6. Copiar el código de la aplicación
COPY . .

# 7. Crear usuario sin privilegios y asegurar permisos en carpetas de datos y runtime
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/data/raw /app/data/processed /app/data/fixtures && \
    chown -R appuser:appuser /app

USER appuser

# 8. Exponer el puerto
EXPOSE 8501

# 9. Healthcheck del servicio Streamlit
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8501/_stcore/health || exit 1

# 10. Comando de ejecución limpio (usa las variables de entorno definidas arriba)
CMD ["streamlit", "run", "run_app.py"]