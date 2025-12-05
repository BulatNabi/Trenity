# Инструкция по деплою на сервер tatplease.kai.ru

## Предварительные требования

1. Docker и Docker Compose установлены на сервере
2. Nginx установлен на сервере
3. Домен `tatplease.kai.ru` настроен и указывает на IP сервера
4. SSL сертификат для HTTPS (Let's Encrypt или другой)

## Шаги деплоя

### 1. Подготовка сервера

```bash
# Установка Docker (если не установлен)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Установка Docker Compose
sudo apt-get update
sudo apt-get install docker-compose-plugin

# Установка Nginx (если не установлен)
sudo apt-get install nginx
```

### 2. Клонирование проекта на сервер

```bash
cd /opt  # или другая директория
git clone <your-repo-url> Trenity
cd Trenity
```

### 3. Настройка переменных окружения

Создайте файл `.env` в корне проекта:

```env
# PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
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

# Uniquization API (не используется, но оставлено для совместимости)
UNIQ_API_URL=https://uniq.down-web.ru/

# Logging
LOG_LEVEL=INFO
```

### 4. Настройка Nginx на сервере

Скопируйте конфигурацию из `nginx-server.conf`:

```bash
sudo cp nginx-server.conf /etc/nginx/sites-available/tatplease.kai.ru
sudo ln -s /etc/nginx/sites-available/tatplease.kai.ru /etc/nginx/sites-enabled/
```

**ВАЖНО:** Отредактируйте файл `/etc/nginx/sites-available/tatplease.kai.ru` и укажите пути к SSL сертификатам:

```nginx
ssl_certificate /etc/letsencrypt/live/tatplease.kai.ru/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/tatplease.kai.ru/privkey.pem;
```

Если используете Let's Encrypt:

```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d tatplease.kai.ru
```

Проверьте конфигурацию Nginx:

```bash
sudo nginx -t
```

Перезапустите Nginx:

```bash
sudo systemctl restart nginx
```

### 5. Настройка GPU (если требуется)

Если на сервере есть NVIDIA GPU:

```bash
# Установка nvidia-container-toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

Проверьте доступность GPU:

```bash
docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi
```

### 6. Сборка и запуск контейнеров

```bash
# Сборка образов
docker-compose build

# Запуск в фоновом режиме
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Проверка статуса
docker-compose ps
```

### 7. Проверка работы

1. Откройте в браузере: `https://tatplease.kai.ru`
2. Проверьте API документацию: `https://tatplease.kai.ru/docs`
3. Проверьте логи: `docker-compose logs backend`

## Обновление приложения

```bash
# Остановить контейнеры
docker-compose down

# Обновить код
git pull

# Пересобрать и запустить
docker-compose build
docker-compose up -d
```

## Полезные команды

```bash
# Просмотр логов
docker-compose logs -f backend
docker-compose logs -f frontend

# Остановка всех сервисов
docker-compose down

# Остановка с удалением volumes (ОСТОРОЖНО: удалит данные БД!)
docker-compose down -v

# Перезапуск конкретного сервиса
docker-compose restart backend

# Выполнение миграций БД вручную
docker-compose exec backend alembic upgrade head
```

## Структура портов

- **Frontend (nginx в контейнере)**: порт 80 → проксируется внешним nginx
- **Backend (FastAPI)**: порт 8000 → доступен только внутри Docker сети
- **PostgreSQL**: порт 5432 → доступен только внутри Docker сети
- **Внешний Nginx**: порты 80 и 443 → проксирует на frontend:80

## Устранение неполадок

### Проблема: 502 Bad Gateway

```bash
# Проверьте, что контейнеры запущены
docker-compose ps

# Проверьте логи
docker-compose logs backend
docker-compose logs frontend

# Проверьте, что frontend доступен на порту 80
curl http://localhost:80
```

### Проблема: SSL сертификат не работает

```bash
# Проверьте конфигурацию Nginx
sudo nginx -t

# Проверьте сертификаты
sudo certbot certificates

# Обновите сертификат
sudo certbot renew
```

### Проблема: GPU не работает

```bash
# Проверьте доступность GPU в контейнере
docker-compose exec backend nvidia-smi

# Проверьте логи инициализации
docker-compose logs backend | grep GPU
```

## Безопасность

1. **Измените пароли БД** в `.env` файле
2. **Настройте firewall**:
   ```bash
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```
3. **Регулярно обновляйте** Docker образы и зависимости
4. **Делайте резервные копии** базы данных:
   ```bash
   docker-compose exec db pg_dump -U postgres autoposting_db > backup.sql
   ```

