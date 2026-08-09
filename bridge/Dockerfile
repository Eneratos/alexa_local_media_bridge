FROM python:3.13-alpine

ARG VERSION=development

LABEL org.opencontainers.image.title="Alexa Local Media Bridge"
LABEL org.opencontainers.image.description="Local media bridge for Alexa, Navidrome, and Audiobookshelf"
LABEL org.opencontainers.image.source="https://github.com/Eneratos/alexa_local_media_bridge"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.licenses="MIT"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    BRIDGE_PORT=8000 \
    BRIDGE_VERSION="${VERSION}"

WORKDIR /app

COPY LICENSE /app/LICENSE

COPY app/abs_bridge.py \
     app/abs_common.py \
    app/app_version.py \
     app/bridge_common.py \
     app/config_validation.py \
     app/main.py \
     app/queue_tokens.py \
     app/lyrics.py \
     app/resolver.py \
     app/scrobble.py \
     /app/

USER 65534:65534

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s \
    --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"]

CMD ["python", "-u", "/app/main.py"]
