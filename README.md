# Инструкция по запуску с Docker

## Быстрый старт

1. **Создайте файл `.env`** в корне проекта (скопируйте из примера ниже)

2. **Запустите все сервисы:**
   ```bash
   docker-compose up -d
   ```

3. **Откройте в браузере:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000/docs

## Пример .env файла

```env
# PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=autoposting_db

# S3 Yandex Cloud
S3_ENDPOINT_URL=https://storage.yandexcloud.net
S3_ACCESS_KEY_ID=your_access_key
S3_SECRET_ACCESS_KEY=your_secret_key
S3_BUCKET_NAME=your_bucket_name
S3_REGION=ru-central1

# SmmBox API
SMMBOX_API_URL=https://smmbox.com/api/
SMMBOX_API_TOKEN=your_smmbox_token

# Uniquization API
UNIQ_API_URL=https://uniq.down-web.ru/

# Logging
LOG_LEVEL=INFO
```

## Полезные команды

```bash
# Просмотр логов
docker-compose logs -f

# Остановка всех сервисов
docker-compose down

# Пересборка образов
docker-compose build --no-cache

# Просмотр статуса
docker-compose ps
```

## Структура сервисов

- **db** - PostgreSQL база данных (порт 5432)
- **backend** - FastAPI приложение (порт 8000)
- **frontend** - React приложение (порт 3000)

## Примечания

- При первом запуске автоматически выполняются миграции базы данных
- Все временные файлы хранятся в volumes и не теряются при перезапуске
- Логи доступны через `docker-compose logs`

