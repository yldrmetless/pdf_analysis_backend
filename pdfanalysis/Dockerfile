# En güncel Python sürümün
FROM python:3.13.9-slim

# Python'ın çıktılarını anlık görmemiz için (logging)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# PostgreSQL 17 için gerekli sistem kütüphanelerini kuruyoruz
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Bağımlılıkları kopyala ve kur
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Projenin kalanını kopyala
COPY . .

# Django'nun çalışacağı portu belirt
EXPOSE 8000