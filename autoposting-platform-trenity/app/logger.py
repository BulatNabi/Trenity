import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Создаем директорию для логов
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Формат логов
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Настройка root logger
def setup_logger(name: str = "autoposting", log_level: str = "INFO") -> logging.Logger:
    """
    Настройка логгера для приложения
    
    Args:
        name: Имя логгера
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Настроенный logger
    """
    logger = logging.getLogger(name)
    
    # Устанавливаем уровень логирования
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)
    
    # Очищаем существующие handlers
    logger.handlers.clear()
    
    # Форматтер
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    
    # Handler для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Handler для файла (общий лог)
    file_handler = RotatingFileHandler(
        LOG_DIR / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Handler для ошибок (отдельный файл)
    error_handler = RotatingFileHandler(
        LOG_DIR / "errors.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)
    
    # Предотвращаем дублирование логов
    logger.propagate = False
    
    return logger


# Создаем основной logger
logger = setup_logger("autoposting")

# Создаем специализированные логгеры
db_logger = logging.getLogger("autoposting.database")
api_logger = logging.getLogger("autoposting.api")
service_logger = logging.getLogger("autoposting.services")

