# syntax=docker/dockerfile:1
# Container image for remote (streamable-HTTP) deployment.
#
# Databricks Apps does not need this file: it builds from the synced source
# and app.yaml. Keep it for any other container host, and for running the
# server locally in isolation.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
ENV PORT=8080

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml README.md ./
COPY src ./src
RUN uv pip install --system --no-cache .

EXPOSE 8080

# PORT is set above, so app.py serves streamable-HTTP on that port.
CMD ["python", "-m", "weather_mcp.app"]
