# Blink: API + web site in one process. Works on Render, Fly.io, Cloud Run, Hugging Face Spaces.
#   docker build -t blink . && docker run -p 8000:8000 blink   ->  http://localhost:8000
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY api ./api
COPY web ./web
COPY data ./data
# Committed snapshot of the demo objects: copied into the cache at startup, so a fresh
# container opens them instantly even if IRSA is slow or down.
COPY cache/demo ./cache/demo

# Hosts give the container a writable /tmp; the cache refills there from IRSA as needed.
ENV BLINK_CACHE=/tmp/blink-cache
EXPOSE 8000
# Most hosts set $PORT; default 8000 for local runs.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
