from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sys

try:
    from app.routers import accounts, videos, posts, workflow, groups, publish
    from app.database import Base, engine
    from app.logger import logger, setup_logger
    from app.config import settings
except Exception as e:
    print(f"Ошибка импорта модулей: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    raise

# Настраиваем логирование
try:
    setup_logger("autoposting", settings.log_level)
    logger.info("Инициализация приложения...")
except Exception as e:
    print(f"Ошибка настройки логирования: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    raise

# Создаем таблицы (если их еще нет)
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Таблицы базы данных проверены/созданы")
except Exception as e:
    logger.error(f"Ошибка создания таблиц: {e}", exc_info=True)
    # Не прерываем запуск, так как миграции Alembic должны создать таблицы
    print(f"Предупреждение: не удалось создать таблицы через SQLAlchemy: {e}", file=sys.stderr)

app = FastAPI(
    title="Autoposting Platform API",
    description="API для автопубликации видео в социальные сети",
    version="1.0.0"
)

# Middleware для логирования запросов
@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"{request.method} {request.url.path} - {request.client.host if request.client else 'unknown'}")
    response = await call_next(request)
    logger.info(f"{request.method} {request.url.path} - Status: {response.status_code}")
    return response

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(accounts.router)
app.include_router(videos.router)
app.include_router(posts.router)
app.include_router(workflow.router)
app.include_router(groups.router)
app.include_router(publish.router)


@app.get("/")
def root():
    return {"message": "Autoposting Platform API"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
