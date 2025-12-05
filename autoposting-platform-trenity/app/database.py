from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.logger import db_logger as logger

logger.info(f"Подключение к базе данных: {settings.database_url.split('@')[1] if '@' in settings.database_url else 'скрыто'}")

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Ошибка работы с БД: {str(e)}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()
