FROM python:3.11-slim AS builder
WORKDIR /build
COPY pyproject.toml .
COPY app ./app
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir .

FROM python:3.11-slim AS runtime
ENV PATH="/opt/venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN groupadd --system silverbell && useradd --system --gid silverbell silverbell
WORKDIR /srv
COPY --from=builder /opt/venv /opt/venv
USER silverbell
EXPOSE 8000
CMD ["python", "-m", "app.main"]
