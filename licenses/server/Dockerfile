FROM python:3.12-slim

RUN useradd -r -s /bin/false appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# Создаём том для базы данных
VOLUME ["/app/data"]
RUN mkdir -p /app/data && chown appuser:appuser /app/data

# Используем путь к БД в volume
ENV DB_PATH=/app/data/licenses.db

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/')" || exit 1

CMD ["python", "public_server.py"]
