FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

ARG GIT_COMMIT=unknown
ENV APP_GIT_COMMIT=${GIT_COMMIT}
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY VERSION ./VERSION
RUN mkdir -p /app/data/media

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
