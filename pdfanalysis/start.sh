#!/bin/bash
# Sağlık kontrolünü geçmek için HTTP sunucusunu arka planda başlat
python3 -m http.server 8000 &

# Celery worker'ı başlat
celery -A config worker --loglevel=info --concurrency=1