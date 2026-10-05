FROM python:3.12-slim

WORKDIR /app

COPY thinkgate/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY thinkgate/ ./

ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]
