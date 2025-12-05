"""
Скрипт для проверки подключения к БД и состояния таблиц
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text

load_dotenv()

database_url = os.getenv("DATABASE_URL")
if not database_url:
    print("❌ DATABASE_URL не найден в .env файле!")
    exit(1)

print(f"🔌 Подключение к БД: {database_url.split('@')[1] if '@' in database_url else 'скрыто'}")

try:
    engine = create_engine(database_url)
    
    # Проверяем подключение
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version();"))
        version = result.fetchone()[0]
        print(f"✅ Подключение успешно!")
        print(f"📊 PostgreSQL версия: {version}")
        
        # Проверяем существующие таблицы
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        print(f"\n📋 Таблицы в базе данных:")
        if tables:
            for table in tables:
                print(f"  - {table}")
        else:
            print("  (таблиц нет)")
        
        # Проверяем enum типы
        result = conn.execute(text("""
            SELECT t.typname 
            FROM pg_type t 
            JOIN pg_enum e ON t.oid = e.enumtypid 
            GROUP BY t.typname;
        """))
        enums = [row[0] for row in result.fetchall()]
        
        print(f"\n🔤 Enum типы в базе данных:")
        if enums:
            for enum_type in enums:
                print(f"  - {enum_type}")
        else:
            print("  (enum типов нет)")
        
        # Проверяем таблицу alembic_version
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'alembic_version';
        """))
        alembic_table = result.fetchone()
        
        if alembic_table:
            result = conn.execute(text("SELECT version_num FROM alembic_version;"))
            version_num = result.fetchone()
            if version_num:
                print(f"\n📦 Текущая версия миграции: {version_num[0]}")
            else:
                print(f"\n📦 Таблица alembic_version существует, но пуста")
        else:
            print(f"\n📦 Таблица alembic_version не найдена (миграции не применялись)")
            
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()

