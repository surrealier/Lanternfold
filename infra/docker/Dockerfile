FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/api-gateway/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

ENV PYTHONPATH=/app/services/api-gateway
ENV EVENTOPS_DATABASE_URL=sqlite:////app/data/eventops.db
ENV EVENTOPS_STORAGE_ROOT=/app/data/storage
ENV EVENTOPS_SEED_SAMPLE_DATA=true
ENV EVENTOPS_NOTIFICATION_MODE=record

EXPOSE 8000

CMD ["uvicorn", "app.main:create_default_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]