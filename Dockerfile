# One container for everything (Hugging Face Spaces, Docker SDK):
#   :7860  agent backend + built React app   (public)
#   :8001  database backend                  (inside the container only)

# ---- 1. build the React app
FROM node:20-slim AS web
WORKDIR /web
COPY municipal_complaint_agent/frontend/package.json municipal_complaint_agent/frontend/package-lock.json ./
RUN npm ci
COPY municipal_complaint_agent/frontend/ ./
RUN npm run build

# ---- 2. python runtime
FROM python:3.11-slim
WORKDIR /app

COPY backend/requirements.txt backend-requirements.txt
COPY municipal_complaint_agent/requirements.txt agent-requirements.txt
RUN pip install --no-cache-dir -r backend-requirements.txt -r agent-requirements.txt

COPY backend/ backend/
COPY municipal_complaint_agent/app/ agent/app/
COPY municipal_complaint_agent/run.py agent/run.py
COPY --from=web /web/dist static/

# Spaces runs the container as an unprivileged user; SQLite needs a writable backend/ folder.
RUN useradd -m -u 1000 user && chown -R user:user /app
USER user

ENV STATIC_DIR=/app/static \
    DB_BACKEND_URL=http://127.0.0.1:8001 \
    LLM_PROVIDER=mock \
    VERIFICATION_SCENARIO=manual \
    PYTHONUNBUFFERED=1

EXPOSE 7860
CMD ["sh", "-c", "(cd /app/backend && uvicorn app.main:app --host 127.0.0.1 --port 8001) & cd /app/agent && exec python run.py serve --host 0.0.0.0 --port 7860"]
