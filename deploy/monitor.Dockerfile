FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY services/monitor/backend/requirements*.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c requirements-dev.lock.txt
COPY services/monitor/backend/app ./app
COPY services/monitor/backend/scripts/seed_user.py ./scripts/seed_user.py
COPY services/monitor/backend/tests/fixtures/ps_config_v1.json ./portal-config.json
COPY services/monitor/backend/tests/fixtures/generation_readiness_v1.json ./portal-readiness.json
COPY deploy/bootstrap.py ./bootstrap.py
RUN useradd --system --uid 10001 portal
USER portal
CMD ["sh", "-c", "python bootstrap.py && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]

