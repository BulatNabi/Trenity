"""
Скрипт для проверки структуры таблиц и enum значений
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

database_url = os.getenv("DATABASE_URL")
engine = create_engine(database_url)

print("🔍 Проверка структуры таблиц и enum...\n")

with engine.connect() as conn:
    # Проверяем значения enum
    print("📋 Значения enum 'socialnetwork':")
    result = conn.execute(text("""
        SELECT enumlabel 
        FROM pg_enum 
        WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'socialnetwork')
        ORDER BY enumsortorder;
    """))
    enum_values = [row[0] for row in result.fetchall()]
    for value in enum_values:
        print(f"  ✓ {value}")
    
    # Проверяем структуру таблицы accounts
    print("\n📊 Структура таблицы 'accounts':")
    result = conn.execute(text("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'accounts'
        ORDER BY ordinal_position;
    """))
    for row in result.fetchall():
        nullable = "NULL" if row[2] == 'YES' else "NOT NULL"
        print(f"  - {row[0]}: {row[1]} ({nullable})")
    
    # Проверяем структуру таблицы posts
    print("\n📊 Структура таблицы 'posts':")
    result = conn.execute(text("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'posts'
        ORDER BY ordinal_position;
    """))
    for row in result.fetchall():
        nullable = "NULL" if row[2] == 'YES' else "NOT NULL"
        print(f"  - {row[0]}: {row[1]} ({nullable})")
    
    # Проверяем индексы
    print("\n🔑 Индексы:")
    result = conn.execute(text("""
        SELECT tablename, indexname
        FROM pg_indexes
        WHERE schemaname = 'public'
        AND tablename IN ('accounts', 'posts')
        ORDER BY tablename, indexname;
    """))
    for row in result.fetchall():
        print(f"  - {row[0]}.{row[1]}")
    
    # Проверяем внешние ключи
    print("\n🔗 Внешние ключи:")
    result = conn.execute(text("""
        SELECT
            tc.table_name, 
            kcu.column_name, 
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name 
        FROM information_schema.table_constraints AS tc 
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
          ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY' 
        AND tc.table_name IN ('accounts', 'posts');
    """))
    fks = result.fetchall()
    if fks:
        for fk in fks:
            print(f"  - {fk[0]}.{fk[1]} -> {fk[2]}.{fk[3]}")
    else:
        print("  (внешних ключей не найдено)")
    
    # Проверяем количество записей
    print("\n📈 Количество записей:")
    result = conn.execute(text("SELECT COUNT(*) FROM accounts;"))
    accounts_count = result.fetchone()[0]
    print(f"  - accounts: {accounts_count}")
    
    result = conn.execute(text("SELECT COUNT(*) FROM posts;"))
    posts_count = result.fetchone()[0]
    print(f"  - posts: {posts_count}")

print("\n✅ Проверка завершена!")

