# syntax=docker/dockerfile:1
# Construir desde la copia publica, nunca desde el directorio de trabajo privado.
FROM node:24-bookworm-slim AS interfaz
WORKDIR /build/frontend
ENV NPM_CONFIG_AUDIT=false \
    NPM_CONFIG_FUND=false
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/index.html frontend/tsconfig.json frontend/vite.config.ts ./
COPY frontend/src/ ./src/
COPY frontend/public/ ./public/
RUN npm run build

FROM python:3.12-slim-bookworm AS dependencias
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential pkg-config libcairo2-dev libpango1.0-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN python -m venv /app/.venv
COPY pyproject.toml restricciones-python.txt ./
COPY src/videocodigo/ ./src/videocodigo/
COPY src/videocodigo_web/ ./src/videocodigo_web/
RUN /app/.venv/bin/python -m pip install --constraint restricciones-python.txt '.[web]'

FROM python:3.12-slim-bookworm AS aplicacion
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIDEOCODIGO_RAIZ=/app \
    FILMCODE_DOCKER=1 \
    NO_PROXY=localhost,127.0.0.1,::1 \
    no_proxy=localhost,127.0.0.1,::1
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates ffmpeg libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgl1 libegl1 fontconfig fonts-dejavu-core fonts-texgyre-math \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 filmcode \
    && useradd --uid 10001 --gid 10001 --create-home filmcode
WORKDIR /app
COPY --from=dependencias /app/.venv/ /app/.venv/
COPY pyproject.toml ./
COPY src/videocodigo/ ./src/videocodigo/
COPY src/videocodigo_web/ ./src/videocodigo_web/
COPY --from=interfaz /build/frontend/dist/ ./frontend/dist/
COPY fonts.conf /etc/fonts/conf.d/99-filmcode.conf
RUN fc-cache -f \
    && mkdir -p /app/videos /app/.web /home/filmcode/.cache \
    && chown -R 10001:10001 /app/videos /app/.web /home/filmcode
USER 10001:10001
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD ["/app/.venv/bin/python", "-c", "import json, urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8765/api/identidad', timeout=3); assert json.load(r).get('aplicacion') == 'videocodigo-web'"]
CMD ["/app/.venv/bin/python", "-m", "videocodigo_web", "--puerto", "8765"]
