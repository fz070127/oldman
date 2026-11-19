FROM python:3.11-slim-bookworm AS builder
WORKDIR /build
COPY pyproject.toml .
COPY app ./app
COPY config/escalate.yaml ./config/escalate.yaml
RUN python -m pip install --no-cache-dir --prefix=/opt/runtime .

FROM python:3.11-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system silverbell \
    && useradd --system --gid silverbell silverbell
WORKDIR /srv
COPY --from=builder /opt/runtime /usr/local
COPY alembic.ini ./
COPY alembic ./alembic
COPY --chmod=755 docker-entrypoint.sh ./
USER silverbell
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl --fail --silent --show-error --max-time 4 "http://127.0.0.1:${APP_PORT:-8000}/health" >/dev/null
ENTRYPOINT ["/srv/docker-entrypoint.sh"]
CMD ["python", "-m", "app.main"]
