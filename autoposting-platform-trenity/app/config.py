from pydantic_settings import BaseSettings
from typing import Optional
import os
import logging
import sys

# Настраиваем базовый логгер для конфигурации (до инициализации основного логгера)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
config_logger = logging.getLogger("autoposting.config")


class Settings(BaseSettings):
    # Database
    database_url: str

    # S3 Yandex Cloud (опциональные для разработки, но обязательные для работы)
    s3_endpoint_url: Optional[str] = None
    s3_access_key_id: Optional[str] = None
    s3_secret_access_key: Optional[str] = None
    s3_bucket_name: Optional[str] = None
    s3_region: str = "ru-central1"

    # SmmBox API
    smmbox_api_url: str = "https://smmbox.com/api/"
    smmbox_api_token: Optional[str] = None

    # Uniquization API
    uniq_api_url: str = "https://uniq.down-web.ru/"

    # Local storage
    data_folder: str = "data"

    # Logging
    log_level: str = "INFO"

    def validate_s3_settings(self):
        """Проверяет, что S3 настройки установлены (вызывается при использовании)"""
        if not all([self.s3_endpoint_url, self.s3_access_key_id,
                   self.s3_secret_access_key, self.s3_bucket_name]):
            raise ValueError(
                "S3 настройки не установлены. Установите переменные окружения: "
                "S3_ENDPOINT_URL, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_BUCKET_NAME"
            )

    class Config:
        env_file = ".env"
        case_sensitive = False
        # Позволяем загружать из переменных окружения без .env файла
        env_file_encoding = 'utf-8'


def mask_sensitive_value(value: Optional[str], show_chars: int = 4) -> str:
    """Маскирует чувствительные значения, показывая только первые и последние символы"""
    if not value:
        return "НЕ УСТАНОВЛЕНО"
    if len(value) <= show_chars * 2:
        return "***"  # Слишком короткое значение - полностью скрываем
    return f"{value[:show_chars]}...{value[-show_chars:]}"


def log_environment_variables():
    """Логирует все переменные окружения, связанные с приложением"""
    env_vars = {
        "DATABASE_URL": os.getenv("DATABASE_URL"),
        "S3_ENDPOINT_URL": os.getenv("S3_ENDPOINT_URL"),
        "S3_ACCESS_KEY_ID": os.getenv("S3_ACCESS_KEY_ID"),
        "S3_SECRET_ACCESS_KEY": os.getenv("S3_SECRET_ACCESS_KEY"),
        "S3_BUCKET_NAME": os.getenv("S3_BUCKET_NAME"),
        "S3_REGION": os.getenv("S3_REGION"),
        "SMMBOX_API_URL": os.getenv("SMMBOX_API_URL"),
        "SMMBOX_API_TOKEN": os.getenv("SMMBOX_API_TOKEN"),
        "UNIQ_API_URL": os.getenv("UNIQ_API_URL"),
        "DATA_FOLDER": os.getenv("DATA_FOLDER"),
        "LOG_LEVEL": os.getenv("LOG_LEVEL"),
    }

    config_logger.info("=" * 60)
    config_logger.info("Проверка переменных окружения:")
    config_logger.info("=" * 60)

    for var_name, var_value in env_vars.items():
        if var_name in ["S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY", "SMMBOX_API_TOKEN"]:
            # Чувствительные данные - маскируем
            masked = mask_sensitive_value(var_value)
            status = "✓ УСТАНОВЛЕНО" if var_value else "✗ НЕ УСТАНОВЛЕНО"
            config_logger.info(f"  {var_name}: {status} ({masked})")
        elif var_name == "DATABASE_URL":
            # Для DATABASE_URL показываем только часть после @
            if var_value:
                if "@" in var_value:
                    db_part = var_value.split("@")[-1]
                    config_logger.info(
                        f"  {var_name}: ✓ УСТАНОВЛЕНО (***@{db_part})")
                else:
                    config_logger.info(f"  {var_name}: ✓ УСТАНОВЛЕНО (скрыто)")
            else:
                config_logger.info(f"  {var_name}: ✗ НЕ УСТАНОВЛЕНО")
        else:
            # Обычные переменные - показываем полностью
            status = "✓ УСТАНОВЛЕНО" if var_value else "✗ НЕ УСТАНОВЛЕНО"
            value_display = var_value if var_value else "НЕ УСТАНОВЛЕНО"
            config_logger.info(f"  {var_name}: {status} = {value_display}")

    config_logger.info("=" * 60)

    # Проверяем наличие .env файла
    env_file_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_file_path):
        config_logger.info(f"Файл .env найден: {env_file_path}")
        # Пытаемся прочитать содержимое .env файла (без чувствительных данных)
        try:
            with open(env_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                config_logger.info(f"Строк в .env файле: {len(lines)}")
                for i, line in enumerate(lines, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        key = line.split('=')[0].strip()
                        value = line.split('=', 1)[1].strip() if len(
                            line.split('=')) > 1 else ""
                        # Маскируем чувствительные данные
                        if any(sensitive in key.upper() for sensitive in ['TOKEN', 'KEY', 'SECRET', 'PASSWORD']):
                            masked = mask_sensitive_value(value)
                            config_logger.info(
                                f"  Строка {i}: {key} = {masked}")
                        else:
                            config_logger.info(f"  Строка {i}: {key} = {value[:50]}..." if len(
                                value) > 50 else f"  Строка {i}: {key} = {value}")
        except Exception as e:
            config_logger.warning(f"Не удалось прочитать .env файл: {e}")
    else:
        config_logger.warning(f"Файл .env НЕ найден: {env_file_path}")
        config_logger.warning(
            "Переменные окружения загружаются только из системных переменных")

    # Также проверяем переменные окружения, которые могли быть переданы через Docker
    config_logger.info("Текущая рабочая директория: " + os.getcwd())


# Безопасная инициализация настроек
try:
    # Логируем переменные окружения ДО создания Settings
    log_environment_variables()

    settings = Settings()

    # Логируем загруженные настройки (после создания Settings)
    config_logger.info("Загруженные настройки приложения:")
    config_logger.info(
        f"  DATABASE_URL: {'✓' if settings.database_url else '✗'}")
    config_logger.info(
        f"  S3_ENDPOINT_URL: {settings.s3_endpoint_url or 'НЕ УСТАНОВЛЕНО'}")
    config_logger.info(
        f"  S3_ACCESS_KEY_ID: {mask_sensitive_value(settings.s3_access_key_id)}")
    config_logger.info(
        f"  S3_SECRET_ACCESS_KEY: {mask_sensitive_value(settings.s3_secret_access_key)}")
    config_logger.info(
        f"  S3_BUCKET_NAME: {settings.s3_bucket_name or 'НЕ УСТАНОВЛЕНО'}")
    config_logger.info(f"  SMMBOX_API_URL: {settings.smmbox_api_url}")
    config_logger.info(
        f"  SMMBOX_API_TOKEN: {mask_sensitive_value(settings.smmbox_api_token)}")
    config_logger.info(f"  UNIQ_API_URL: {settings.uniq_api_url}")
    config_logger.info(f"  DATA_FOLDER: {settings.data_folder}")
    config_logger.info(f"  LOG_LEVEL: {settings.log_level}")

except Exception as e:
    # Если не удалось загрузить настройки, выводим понятную ошибку
    config_logger.error(f"Ошибка загрузки настроек: {e}", exc_info=True)
    print(f"Ошибка загрузки настроек: {e}", file=sys.stderr)
    print("Убедитесь, что все необходимые переменные окружения установлены:", file=sys.stderr)
    print("  - DATABASE_URL", file=sys.stderr)
    print("  - S3_ENDPOINT_URL", file=sys.stderr)
    print("  - S3_ACCESS_KEY_ID", file=sys.stderr)
    print("  - S3_SECRET_ACCESS_KEY", file=sys.stderr)
    print("  - S3_BUCKET_NAME", file=sys.stderr)
    raise
