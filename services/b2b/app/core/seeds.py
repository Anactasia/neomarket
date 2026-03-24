# services/b2b/app/core/seeds.py
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.category import Category
from app.models.seller import Seller
from app.models.product import Product,ProductImage 
from app.models.sku import SKU

def seed_telegram_market():
    db = SessionLocal()
    try:
        print("--- ⚡ ЗАПУСК ГЛОБАЛЬНОЙ СИНХРОНИЗАЦИИ ДАННЫХ ⚡ ---")

        # 1. Очистка (порядок важен из-за FK)
        db.query(SKU).delete()
        db.query(Product).delete()
        db.query(Category).delete()
        db.query(Seller).delete()
        db.commit()

        # 2. ДЕРЕВО КАТЕГОРИЙ (US.1 - Leaf node logic)
        print("Создаем иерархию секторов...")
        
        # Root 1
        cat_info = Category(name="Информационный фронт", slug="info-war", level=0)
        db.add(cat_info)
        db.flush()

        # Sub-categories for Root 1
        cat_leaks = Category(name="Сливы баз данных", slug="db-leaks", parent_id=cat_info.id, level=1)
        cat_news = Category(name="Подпольные новости", slug="dark-news", parent_id=cat_info.id, level=1)
        
        # Root 2
        cat_finance = Category(name="Финансовые операции", slug="fin-ops", level=0)
        db.add(cat_finance)
        db.flush()

        # Sub-category for Root 2
        cat_crypto = Category(name="Крипто-сигналы", slug="crypto-nodes", parent_id=cat_finance.id, level=1)
        
        db.add_all([cat_leaks, cat_news, cat_crypto])
        db.flush()

        # 3. ПРОДАВЦЫ (РАЗНЫЕ СТАТУСЫ)
        print("Вербуем продавцов...")
        
        def create_seller(name, inn):
            s = Seller(
                id=str(uuid.uuid4()),
                company_name=name,
                inn=inn,
                status="ACTIVE",
                email=f"contact@{name.lower().replace(' ', '_')}.net"
            )
            db.add(s)
            db.flush()
            return s

        s1 = create_seller("Arasaka Intelligence", "7700100001")
        s2 = create_seller("NetWatchers Team", "7700100002")
        s3 = create_seller("Bunker Diggers", "7700100003")

        # 4. ТОВАРЫ (КАНАЛЫ) - Добавляем поле img_url
        print("Загружаем каналы в сеть...")

        products_data = [
            {
                "seller_id": s1.id, "category_id": cat_leaks.id,
                "title": "@Red_File_Leaks", "slug": "red-file-leaks",
                "desc": "Сливых переписок чиновников верхнего уровня. 120к сабов.",
                "status": "MODERATED", "meta_t": "Купить канал со сливами", 
                "meta_d": "Продажа топового канала Leaks",
                "img_url": "https://picsum.photos/seed/leaks/600/400" # Заглушка
            },
            {
                "seller_id": s2.id, "category_id": cat_crypto.id,
                "title": "Crypto Ghost Node", "slug": "crypto-ghost",
                "desc": "Сигналы по анонимным монетам. Скрытый чат на 5к декеров.",
                "status": "ON_MODERATION", "meta_t": "Крипто канал Telegram", 
                "meta_d": "Инвестиции в анонимность",
                "img_url": "https://picsum.photos/seed/crypto/600/400"
            },
            {
                "seller_id": s3.id, "category_id": cat_news.id,
                "title": "Голос Пустоши", "slug": "voice-of-waste",
                "desc": "Радиопередачи из заброшенных секторов. Только правда.",
                "status": "DRAFT", "meta_t": "Черновик канала", 
                "meta_d": "Описание скоро будет",
                "img_url": "https://picsum.photos/seed/radio/600/400"
            },
            {
                "seller_id": s1.id, "category_id": cat_leaks.id,
                "title": "Corporation Secrets", "slug": "corp-secrets",
                "desc": "Архивы Arasaka за 2024-2025 года. Эксклюзив.",
                "status": "REJECTED", "meta_t": "Запрещенка", 
                "meta_d": "Отклонено модератором",
                "img_url": "https://picsum.photos/seed/corp/600/400"
            }
        ]

        created_products = []
        for p in products_data:
            new_p = Product(
                seller_id=p["seller_id"],
                category_id=p["category_id"],
                title=p["title"],
                slug=p["slug"],
                description=p["desc"],
                status=p["status"],
                meta_title=p["meta_t"],
                meta_description=p["meta_d"],
                meta_keywords="cyber, telegram, buy, channel"
            )
            db.add(new_p)
            db.flush() # Получаем ID товара для картинки

            # --- ДОБАВЛЯЕМ КАРТИНКУ ---
            img = ProductImage(
                product_id=new_p.id,
                url=p["img_url"],
                is_main=True,
                sort_order=0
            )
            db.add(img)
            db.flush() # Получаем ID картинки

            # Привязываем ID картинки как главную к товару
            new_p.main_image_id = img.id
            # --------------------------

            created_products.append(new_p)

        # 5. SKU (ВАРИАНТЫ ПРОДАЖИ)
        print("Генерируем лоты...")
        
        for p in created_products:
            # Лот 1: Рекламный пост
            db.add(SKU(
                product_id=p.id,
                name=f"Рекламный пост в {p.title}",
                price=500000, # 5к
                quantity=10,
                is_active=True
            ))
            # Лот 2: Полный доступ (только для опубликованных)
            if p.status == "MODERATED":
                db.add(SKU(
                    product_id=p.id,
                    name=f"ПРАВА ВЛАДЕЛЬЦА (Owner) - {p.title}",
                    price=25000000, # 250к
                    quantity=1,
                    is_active=True
                ))

        db.commit()
        print("\n✅ СЕТЬ ЗАПОЛНЕНА УСПЕШНО.")
        print(f"Категорий: {db.query(Category).count()}")
        print(f"Товаров (Каналов): {db.query(Product).count()}")
        print(f"Лотов (SKU): {db.query(SKU).count()}")

    except Exception as e:
        print(f"❌ АВАРИЙНЫЙ ВЫХОД: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_telegram_market()