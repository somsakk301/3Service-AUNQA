# Mornitor backend (FastAPI). Build context: backend/
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

# Runtime packages only (requirements.txt), held to the versions the test suite passed with.
COPY requirements.txt requirements-dev.lock.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c requirements-dev.lock.txt

COPY app ./app

RUN useradd --system --no-create-home --uid 10001 mornitor
USER mornitor

EXPOSE 8000
# The databases are given at run time (MORNITOR_DB_URI, MORNITOR_DB_NAME ...), never built into the image.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
