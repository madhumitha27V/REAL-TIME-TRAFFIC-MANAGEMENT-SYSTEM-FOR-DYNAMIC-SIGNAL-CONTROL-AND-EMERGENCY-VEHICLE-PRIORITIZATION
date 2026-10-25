
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV SUMO_HOME=/usr/share/sumo

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    sumo \
    sumo-tools \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 10000

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
