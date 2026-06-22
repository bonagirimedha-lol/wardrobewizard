# backend/Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies for psycopg2 and ML libs
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create directory for ML models to avoid permission issues if torch downloads them
RUN mkdir -p /root/.cache/torch

EXPOSE 5000

CMD ["python", "app.py"]
