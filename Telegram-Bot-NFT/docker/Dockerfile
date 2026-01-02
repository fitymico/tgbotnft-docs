# ================== Build Stage для Node.js ==================
FROM node:20-alpine AS node-builder

WORKDIR /app/Gift_API

# Копируем package файлы
COPY Gift_API/package*.json ./

# Устанавливаем зависимости
RUN npm ci --only=production

# Копируем исходники TypeScript
COPY Gift_API/src ./src
COPY Gift_API/tsconfig.json ./

# Компилируем TypeScript
RUN npm run build 2>/dev/null || npx tsc

# ================== Production Stage ==================
FROM python:3.12-slim

WORKDIR /app

# Устанавливаем Node.js
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Копируем Python зависимости
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Копируем Node.js приложение из builder
COPY --from=node-builder /app/Gift_API/node_modules ./Gift_API/node_modules
COPY --from=node-builder /app/Gift_API/dist ./Gift_API/dist
COPY Gift_API/package*.json ./Gift_API/

# Копируем Python бота
COPY Message_Bot ./Message_Bot
COPY config.py ./
COPY scripts ./scripts

# Создаём директорию для данных
RUN mkdir -p /app/data

# Делаем скрипты исполняемыми
RUN chmod +x scripts/*.sh

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production

# Точка входа
COPY docker/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
