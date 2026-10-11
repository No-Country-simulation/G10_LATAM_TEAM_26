# CommunityLab AI: front en React y API en FastAPI, servidos juntos en un solo puerto.

# 1. Compila el front (frontend/dist)
FROM node:20-alpine AS front
WORKDIR /front
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# 2. API en Python, que además sirve el front compilado
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY src/ src/
COPY data/fixtures/ data/fixtures/
COPY --from=front /front/dist frontend/dist

# Usuario sin privilegios; data/ se monta como volumen (credenciales de OCI, capturas, paquetes, base local)
RUN useradd -m -u 1000 app && mkdir -p data/raw data/processed data/cache && chown -R app:app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/openapi.json', timeout=4)"

CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
