# b2b/scripts/import_categories.py

"""
Скрипт для импорта категорий из JSON файла
Запуск: python scripts/import_categories.py
"""

import json
import sys
import os
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.category import Category


def import_categories_from_json(json_path: str):
    """Импорт категорий из JSON файла"""
    
    # Проверяем существование файла
    if not os.path.exists(json_path):
        print(f"❌ Файл не найден: {json_path}")
        return False
    
    with open(json_path, 'r', encoding='utf-8') as f:
        categories_data = json.load(f)
    
    # Поддерживаем два формата
    if isinstance(categories_data, dict) and 'categories' in categories_data:
        categories_data = categories_data['categories']
    
    db = SessionLocal()
    
    def create_category_recursive(data, parent_id=None, level=0):
        count = 0
        for cat in data:
            # Проверяем, не существует ли уже такая категория
            existing = db.query(Category).filter(Category.slug == cat['slug']).first()
            if existing:
                print(f"⚠️ Пропущено (уже существует): {cat['name']}")
                continue
            
            category = Category(
                name=cat['name'],
                slug=cat['slug'],
                parent_id=parent_id,
                level=level,
                is_active=cat.get('is_active', True),
                sort_order=cat.get('sort_order', 0)
            )
            db.add(category)
            db.flush()  # Получаем ID
            count += 1
            print(f"  {'  ' * level}✅ {cat['name']}")
            
            if 'children' in cat and cat['children']:
                child_count = create_category_recursive(cat['children'], category.id, level + 1)
                count += child_count
        
        return count
    
    try:
        total = create_category_recursive(categories_data)
        db.commit()
        print(f"\n🎉 Импортировано {total} категорий")
        return True
    except Exception as e:
        db.rollback()
        print(f"❌ Ошибка: {e}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    # Правильный путь к файлу categories.json в папке data
    base_dir = Path(__file__).parent.parent
    json_path = base_dir / "data" / "categories.json"
    
    print(f"📂 Загрузка категорий из: {json_path}")
    success = import_categories_from_json(str(json_path))
    sys.exit(0 if success else 1)