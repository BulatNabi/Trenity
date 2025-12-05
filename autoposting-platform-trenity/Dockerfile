# Используем базовый образ с CUDA поддержкой (если доступен) или обычный Python
# Для GPU используйте: nvidia/cuda:12.0.0-base-ubuntu22.04
# Для CPU используйте: python:3.11-slim
FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Проверка и установка NVIDIA утилит (если доступны)
# nvidia-smi будет доступен через nvidia-container-runtime
RUN if command -v nvidia-smi >/dev/null 2>&1 || [ -n "$NVIDIA_VISIBLE_DEVICES" ]; then \
    echo "NVIDIA runtime detected"; \
    else \
    echo "NVIDIA runtime not detected - GPU will not be available"; \
    fi

# Копирование requirements
COPY autoposting-platform-trenity/requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование trenity-uniqalize-system для локального уникализатора
RUN mkdir -p /app/trenity-uniqalize-system
COPY trenity-uniqalize-system/video_uniqueizer.py /app/trenity-uniqalize-system/

# Копирование кода приложения
COPY autoposting-platform-trenity/ .

# Создание директорий для данных и логов
RUN mkdir -p data logs

# Открытие порта
EXPOSE 8000

# Запуск приложения
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

