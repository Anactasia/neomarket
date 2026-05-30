"""
Тесты для US-B2B-07: Каталог товаров для B2C (service-to-service)
"""
import os
import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# ✅ Устанавливаем переменные окружения ДО импорта приложения
os.environ["B2C_TO_B2B_KEY"] = "test-b2c-key"
os.environ["B2B_TO_MOD_KEY"] = "test-mod-key"
os.environ["B2B_SERVICE_KEY"] = "b2b-service-key"

from app.main import app
from app.database import SessionLocal
from app.models.category import Category
from app.models.seller import Seller
from app.models.product import Product, ProductImage
from app.models.sku import SKU
from app.core.security import create_access_token
from app.schemas.product import ProductStatus


@pytest.fixture
def client():
    """Тестовый клиент"""
    return TestClient(app)


@pytest.fixture
def db_session():
    """Тестовая сессия БД"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture(autouse=True, scope="function")
def clean_db(db_session):
    """Очищает таблицы в правильном порядке (с учетом внешних ключей)"""
    from app.models.invoice import InvoiceItem, Invoice
    from app.models.reservation import SKUReservation
    from app.models.unreserve_operation import UnreserveOperationItem, UnreserveOperation
    from app.models.fulfill_operation import FulfillOperationItem, FulfillOperation
    from app.models.outbox import OutboxEvent
    from app.models.product import ProductImage
    from app.models.sku import SKUImage
    from app.models.seller import Seller
    from app.models.category import Category
    
    # Удаляем в правильном порядке (от зависимых к родительским)
    
    # 1. Самые зависимые таблицы
    db_session.query(UnreserveOperationItem).delete()
    db_session.query(FulfillOperationItem).delete()
    db_session.query(SKUReservation).delete()
    db_session.query(SKUImage).delete()
    db_session.query(ProductImage).delete()
    db_session.query(InvoiceItem).delete()
    
    # 2. Промежуточные
    db_session.query(UnreserveOperation).delete()
    db_session.query(FulfillOperation).delete()
    db_session.query(Invoice).delete()
    db_session.query(OutboxEvent).delete()
    
    # 3. Основные таблицы
    db_session.query(SKU).delete()
    db_session.query(Product).delete()
    db_session.query(Category).delete()
    db_session.query(Seller).delete()
    
    db_session.commit()


@pytest.fixture
def service_key():
    """X-Service-Key для межсервисных вызовов"""
    return "test-b2c-key"  # ✅ изменено с "b2b-service-key" на "test-b2c-key"


@pytest.fixture
def test_category(db_session):
    """Создаём тестовую категорию"""
    category = Category(
        id=uuid4(),
        name="Test Category",
        slug=f"test-category-{uuid4()}",
        level=0,
        is_active=True
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


@pytest.fixture
def test_seller(db_session):
    """Создаём тестового продавца"""
    seller = Seller(
        id=uuid4(),
        email=f"test_{uuid4().hex[:12]}@example.com",
        hashed_password="fake_hash",
        first_name="Test",
        last_name="Seller",
        company_name="Test Company",
        inn=f"{uuid4().hex[:12]}",
        status="ACTIVE",
        is_active=True
    )
    db_session.add(seller)
    db_session.commit()
    db_session.refresh(seller)
    return seller


class TestB2B07PublicCatalog:
    """Тесты для публичного каталога B2C"""

    def test_catalog_returns_moderated_in_stock_products(
        self, client, db_session, service_key, test_category, test_seller
    ):
        """Happy path: каталог возвращает только MODERATED + in_stock товары"""
        # Создаём MODERATED товар с остатком
        product1 = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Moderated Product",
            slug="moderated-product",
            description="Description",
            status=ProductStatus.MODERATED.value,
            deleted=False,
            blocked=False
        )
        db_session.add(product1)
        db_session.flush()
        
        sku1 = SKU(
            id=uuid4(),
            product_id=product1.id,
            name="SKU with stock",
            price=1000000,
            cost_price=700000,
            discount=0,
            image="/s3/test.jpg",
            stock_quantity=10,
            active_quantity=10,
            reserved_quantity=0
        )
        db_session.add(sku1)
        db_session.commit()
        
        # Создаём CREATED товар (не должен попасть в каталог)
        product2 = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Created Product",
            slug="created-product",
            description="Description",
            status=ProductStatus.CREATED.value,
            deleted=False,
            blocked=False
        )
        db_session.add(product2)
        db_session.commit()
        
        response = client.get(
            "/api/v1/public/products",
            params={"limit": 20, "offset": 0},
            headers={"X-Service-Key": service_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Проверяем формат пагинации
        assert "items" in data
        assert "total_count" in data
        
        # Проверяем, что в ответе только MODERATED товары
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == str(product1.id)
        assert data["items"][0]["status"] == "MODERATED"
        assert "cost_price" not in data["items"][0]

    
    def test_catalog_excludes_hard_blocked(
        self, client, db_session, service_key, test_category, test_seller
    ):
        """HARD_BLOCKED товары не попадают в выдачу"""
        # Создаём HARD_BLOCKED товар
        product = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Hard Blocked Product",
            slug="hard-blocked-product",
            description="Description",
            status=ProductStatus.HARD_BLOCKED.value,
            deleted=False,
            blocked=True
        )
        db_session.add(product)
        db_session.flush()
        
        sku = SKU(
            id=uuid4(),
            product_id=product.id,
            name="SKU",
            price=1000000,
            cost_price=700000,
            discount=0,
            image="/s3/test.jpg",
            stock_quantity=10,
            active_quantity=10,
            reserved_quantity=0
        )
        db_session.add(sku)
        db_session.commit()
        
        response = client.get(
            "/api/v1/public/products",
            params={"limit": 20, "offset": 0},
            headers={"X-Service-Key": service_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Проверяем, что HARD_BLOCKED товар не в ответе
        assert len(data["items"]) == 0

    def test_catalog_returns_401_without_service_key(self, client):
        """Каталог без X-Service-Key → 401"""
        response = client.get(
            "/api/v1/public/products",
            params={"limit": 20, "offset": 0}
        )
        
        assert response.status_code == 401
        error_data = response.json()
        assert error_data["code"] == "UNAUTHORIZED"
        assert "X-Service-Key" in error_data["message"]

    def test_catalog_pagination_format(self, client, db_session, service_key, test_category, test_seller):
        """Проверка формата пагинации ответа"""
        # Создаём MODERATED товар
        product = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Product",
            slug="product",
            description="Description",
            status=ProductStatus.MODERATED.value,
            deleted=False,
            blocked=False
        )
        db_session.add(product)
        db_session.flush()
        
        sku = SKU(
            id=uuid4(),
            product_id=product.id,
            name="SKU",
            price=1000000,
            cost_price=700000,
            discount=0,
            image="/s3/test.jpg",
            stock_quantity=10,
            active_quantity=10,
            reserved_quantity=0
        )
        db_session.add(sku)
        db_session.commit()
        
        response = client.get(
            "/api/v1/public/products",
            params={"limit": 10, "offset": 0},
            headers={"X-Service-Key": service_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Проверяем формат пагинации
        assert "items" in data
        assert "total_count" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["items"], list)
        assert data["limit"] == 10
        assert data["offset"] == 0

    def test_catalog_response_has_no_cost_price(
        self, client, db_session, service_key, test_category, test_seller
    ):
        """В ответе каталога нет полей cost_price и reserved_quantity"""
        # Создаём MODERATED товар
        product = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Product",
            slug="product",
            description="Description",
            status=ProductStatus.MODERATED.value,
            deleted=False,
            blocked=False
        )
        db_session.add(product)
        db_session.flush()
        
        sku = SKU(
            id=uuid4(),
            product_id=product.id,
            name="SKU",
            price=1000000,
            cost_price=700000,
            discount=0,
            image="/s3/test.jpg",
            stock_quantity=10,
            active_quantity=10,
            reserved_quantity=5
        )
        db_session.add(sku)
        db_session.commit()
        
        response = client.get(
            "/api/v1/public/products",
            params={"limit": 20, "offset": 0},
            headers={"X-Service-Key": service_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) == 1
        
        # Проверяем отсутствие чувствительных полей в SKU
        if "skus" in data["items"][0] and len(data["items"][0]["skus"]) > 0:
            sku_data = data["items"][0]["skus"][0]
            assert "cost_price" not in sku_data
            assert "reserved_quantity" not in sku_data

    def test_batch_ids_returns_visible_subset(
        self, client, db_session, service_key, test_category, test_seller
    ):
        """Batch-запрос возвращает только видимые товары из списка ID"""
        # Создаём MODERATED товар
        product1 = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Moderated Product",
            slug="moderated-product",
            description="Description",
            status=ProductStatus.MODERATED.value,
            deleted=False,
            blocked=False
        )
        db_session.add(product1)
        db_session.flush()
        
        sku1 = SKU(
            id=uuid4(),
            product_id=product1.id,
            name="SKU",
            price=1000000,
            cost_price=700000,
            discount=0,
            image="/s3/test.jpg",
            stock_quantity=10,
            active_quantity=10,
            reserved_quantity=0
        )
        db_session.add(sku1)
        
        # Создаём CREATED товар (не должен попасть в ответ)
        product2 = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Created Product",
            slug="created-product",
            description="Description",
            status=ProductStatus.CREATED.value,
            deleted=False,
            blocked=False
        )
        db_session.add(product2)
        db_session.commit()
        
        response = client.post(
            "/api/v1/public/products/batch",
            json={"product_ids": [str(product1.id), str(product2.id)]},
            headers={"X-Service-Key": service_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Проверяем, что только MODERATED товар в ответе
        assert len(data) == 1
        assert data[0]["id"] == str(product1.id)
        assert data[0]["status"] == "MODERATED"

    def test_catalog_excludes_deleted_products(
        self, client, db_session, service_key, test_category, test_seller
    ):
        """Удалённые товары не попадают в каталог"""
        product = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Deleted Product",
            slug="deleted-product",
            description="Description",
            status=ProductStatus.MODERATED.value,
            deleted=True,
            blocked=False
        )
        db_session.add(product)
        db_session.flush()
        
        sku = SKU(
            id=uuid4(),
            product_id=product.id,
            name="SKU",
            price=1000000,
            cost_price=700000,
            discount=0,
            image="/s3/test.jpg",
            stock_quantity=10,
            active_quantity=10,
            reserved_quantity=0
        )
        db_session.add(sku)
        db_session.commit()
        
        response = client.get(
            "/api/v1/public/products",
            params={"limit": 20, "offset": 0},
            headers={"X-Service-Key": service_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) == 0

    def test_catalog_excludes_out_of_stock_products(
        self, client, db_session, service_key, test_category, test_seller
    ):
        """Товары без остатка (active_quantity=0) не попадают в каталог"""
        product = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Out of Stock Product",
            slug="out-of-stock-product",
            description="Description",
            status=ProductStatus.MODERATED.value,
            deleted=False,
            blocked=False
        )
        db_session.add(product)
        db_session.flush()
        
        sku = SKU(
            id=uuid4(),
            product_id=product.id,
            name="SKU",
            price=1000000,
            cost_price=700000,
            discount=0,
            image="/s3/test.jpg",
            stock_quantity=0,
            active_quantity=0,
            reserved_quantity=0
        )
        db_session.add(sku)
        db_session.commit()
        
        response = client.get(
            "/api/v1/public/products",
            params={"limit": 20, "offset": 0},
            headers={"X-Service-Key": service_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) == 0

    def test_batch_returns_401_without_service_key(self, client):
        """Batch-запрос без X-Service-Key → 401"""
        response = client.post(
            "/api/v1/public/products/batch",
            json={"product_ids": [str(uuid4())]}
        )
        
        assert response.status_code == 401
        error_data = response.json()
        assert error_data["code"] == "UNAUTHORIZED"

    def test_public_product_detail_returns_401_without_service_key(self, client):
        """Получение карточки товара без X-Service-Key → 401"""
        response = client.get(
            f"/api/v1/public/products/{uuid4()}"
        )
        
        assert response.status_code == 401
        error_data = response.json()
        assert error_data["code"] == "UNAUTHORIZED"

    # ========== ДОПОЛНИТЕЛЬНЫЕ ТЕСТЫ ==========

    def test_catalog_excludes_created_products(
        self, client, db_session, service_key, test_category, test_seller
    ):
        """CREATED товары не попадают в каталог"""
        # Создаём CREATED товар
        product = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Created Product",
            slug="created-product",
            description="Description",
            status=ProductStatus.CREATED.value,
            deleted=False,
            blocked=False
        )
        db_session.add(product)
        db_session.flush()
        
        sku = SKU(
            id=uuid4(),
            product_id=product.id,
            name="SKU",
            price=1000000,
            cost_price=700000,
            discount=0,
            image="/s3/test.jpg",
            stock_quantity=10,
            active_quantity=10,
            reserved_quantity=0
        )
        db_session.add(sku)
        db_session.commit()
        
        response = client.get(
            "/api/v1/public/products",
            params={"limit": 20, "offset": 0},
            headers={"X-Service-Key": service_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # CREATED товар не должен быть в ответе
        assert len(data["items"]) == 0


    def test_catalog_excludes_blocked_products(
        self, client, db_session, service_key, test_category, test_seller
    ):
        """BLOCKED товары не попадают в каталог"""
        # Создаём BLOCKED товар
        product = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Blocked Product",
            slug="blocked-product",
            description="Description",
            status=ProductStatus.BLOCKED.value,
            deleted=False,
            blocked=True
        )
        db_session.add(product)
        db_session.flush()
        
        sku = SKU(
            id=uuid4(),
            product_id=product.id,
            name="SKU",
            price=1000000,
            cost_price=700000,
            discount=0,
            image="/s3/test.jpg",
            stock_quantity=10,
            active_quantity=10,
            reserved_quantity=0
        )
        db_session.add(sku)
        db_session.commit()
        
        response = client.get(
            "/api/v1/public/products",
            params={"limit": 20, "offset": 0},
            headers={"X-Service-Key": service_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # BLOCKED товар не должен быть в ответе
        assert len(data["items"]) == 0


    def test_catalog_sort_price_asc(
        self, client, db_session, service_key, test_category, test_seller
    ):
        """Сортировка по возрастанию цены price_asc"""
        # Создаём товар с ценой 500
        product_cheap = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Cheap Product",
            slug="cheap-product",
            description="Cheap product",
            status=ProductStatus.MODERATED.value,
            deleted=False,
            blocked=False
        )
        db_session.add(product_cheap)
        db_session.flush()
        
        sku_cheap = SKU(
            id=uuid4(),
            product_id=product_cheap.id,
            name="SKU Cheap",
            price=50000,
            cost_price=30000,
            discount=0,
            image="/s3/test.jpg",
            stock_quantity=10,
            active_quantity=10,
            reserved_quantity=0
        )
        db_session.add(sku_cheap)
        
        # Создаём товар с ценой 1000
        product_expensive = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Expensive Product",
            slug="expensive-product",
            description="Expensive product",
            status=ProductStatus.MODERATED.value,
            deleted=False,
            blocked=False
        )
        db_session.add(product_expensive)
        db_session.flush()
        
        sku_expensive = SKU(
            id=uuid4(),
            product_id=product_expensive.id,
            name="SKU Expensive",
            price=100000,
            cost_price=70000,
            discount=0,
            image="/s3/test.jpg",
            stock_quantity=10,
            active_quantity=10,
            reserved_quantity=0
        )
        db_session.add(sku_expensive)
        db_session.commit()
        
        response = client.get(
            "/api/v1/public/products",
            params={"limit": 20, "offset": 0, "sort": "price_asc"},
            headers={"X-Service-Key": service_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) == 2
        # Дешёвый товар должен идти первым
        assert data["items"][0]["min_price"] < data["items"][1]["min_price"]


    def test_catalog_sort_price_desc(
        self, client, db_session, service_key, test_category, test_seller
    ):
        """Сортировка по убыванию цены price_desc"""
        # Создаём товар с ценой 500
        product_cheap = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Cheap Product",
            slug="cheap-product",
            description="Cheap product",
            status=ProductStatus.MODERATED.value,
            deleted=False,
            blocked=False
        )
        db_session.add(product_cheap)
        db_session.flush()
        
        sku_cheap = SKU(
            id=uuid4(),
            product_id=product_cheap.id,
            name="SKU Cheap",
            price=50000,
            cost_price=30000,
            discount=0,
            image="/s3/test.jpg",
            stock_quantity=10,
            active_quantity=10,
            reserved_quantity=0
        )
        db_session.add(sku_cheap)
        
        # Создаём товар с ценой 1000
        product_expensive = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Expensive Product",
            slug="expensive-product",
            description="Expensive product",
            status=ProductStatus.MODERATED.value,
            deleted=False,
            blocked=False
        )
        db_session.add(product_expensive)
        db_session.flush()
        
        sku_expensive = SKU(
            id=uuid4(),
            product_id=product_expensive.id,
            name="SKU Expensive",
            price=100000,
            cost_price=70000,
            discount=0,
            image="/s3/test.jpg",
            stock_quantity=10,
            active_quantity=10,
            reserved_quantity=0
        )
        db_session.add(sku_expensive)
        db_session.commit()
        
        response = client.get(
            "/api/v1/public/products",
            params={"limit": 20, "offset": 0, "sort": "price_desc"},
            headers={"X-Service-Key": service_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) == 2
        # Дорогой товар должен идти первым
        assert data["items"][0]["min_price"] > data["items"][1]["min_price"]


    def test_catalog_filter_by_characteristics_single_value(
        self, client, db_session, service_key, test_category, test_seller
    ):
        """Фильтрация по одному значению характеристики filters[color]=red"""
        # Создаём товар с характеристикой color=red
        product_red = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Red Product",
            slug="red-product",
            description="Red color product",
            status=ProductStatus.MODERATED.value,
            deleted=False,
            blocked=False,
            characteristics_json=[{"name": "color", "value": "red"}]
        )
        db_session.add(product_red)
        db_session.flush()
        
        sku_red = SKU(
            id=uuid4(),
            product_id=product_red.id,
            name="SKU Red",
            price=1000000,
            cost_price=700000,
            discount=0,
            image="/s3/test.jpg",
            stock_quantity=10,
            active_quantity=10,
            reserved_quantity=0
        )
        db_session.add(sku_red)
        
        # Создаём товар с характеристикой color=blue
        product_blue = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Blue Product",
            slug="blue-product",
            description="Blue color product",
            status=ProductStatus.MODERATED.value,
            deleted=False,
            blocked=False,
            characteristics_json=[{"name": "color", "value": "blue"}]
        )
        db_session.add(product_blue)
        db_session.flush()
        
        sku_blue = SKU(
            id=uuid4(),
            product_id=product_blue.id,
            name="SKU Blue",
            price=1000000,
            cost_price=700000,
            discount=0,
            image="/s3/test.jpg",
            stock_quantity=10,
            active_quantity=10,
            reserved_quantity=0
        )
        db_session.add(sku_blue)
        db_session.commit()
        
        # Фильтр color=red
        response = client.get(
            "/api/v1/public/products",
            params={"filters[color]": "red"},
            headers={"X-Service-Key": service_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == str(product_red.id)


    def test_catalog_filter_by_characteristics_multiple_values_or(
        self, client, db_session, service_key, test_category, test_seller
    ):
        """Фильтрация по нескольким значениям (OR) filters[color]=red,blue"""
        # Создаём товар с характеристикой color=red
        product_red = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Red Product",
            slug="red-product",
            description="Red color product",
            status=ProductStatus.MODERATED.value,
            deleted=False,
            blocked=False,
            characteristics_json=[{"name": "color", "value": "red"}]
        )
        db_session.add(product_red)
        db_session.flush()
        
        sku_red = SKU(
            id=uuid4(),
            product_id=product_red.id,
            name="SKU Red",
            price=1000000,
            cost_price=700000,
            discount=0,
            image="/s3/test.jpg",
            stock_quantity=10,
            active_quantity=10,
            reserved_quantity=0
        )
        db_session.add(sku_red)
        
        # Создаём товар с характеристикой color=blue
        product_blue = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Blue Product",
            slug="blue-product",
            description="Blue color product",
            status=ProductStatus.MODERATED.value,
            deleted=False,
            blocked=False,
            characteristics_json=[{"name": "color", "value": "blue"}]
        )
        db_session.add(product_blue)
        db_session.flush()
        
        sku_blue = SKU(
            id=uuid4(),
            product_id=product_blue.id,
            name="SKU Blue",
            price=1000000,
            cost_price=700000,
            discount=0,
            image="/s3/test.jpg",
            stock_quantity=10,
            active_quantity=10,
            reserved_quantity=0
        )
        db_session.add(sku_blue)
        
        # Создаём товар с характеристикой color=green (не должен попасть в фильтр)
        product_green = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Green Product",
            slug="green-product",
            description="Green color product",
            status=ProductStatus.MODERATED.value,
            deleted=False,
            blocked=False,
            characteristics_json=[{"name": "color", "value": "green"}]
        )
        db_session.add(product_green)
        db_session.flush()
        
        sku_green = SKU(
            id=uuid4(),
            product_id=product_green.id,
            name="SKU Green",
            price=1000000,
            cost_price=700000,
            discount=0,
            image="/s3/test.jpg",
            stock_quantity=10,
            active_quantity=10,
            reserved_quantity=0
        )
        db_session.add(sku_green)
        db_session.commit()
        
        # Фильтр color=red,blue (OR)
        response = client.get(
            "/api/v1/public/products",
            params={"filters[color]": "red,blue"},
            headers={"X-Service-Key": service_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        ids = [item["id"] for item in data["items"]]
        assert str(product_red.id) in ids
        assert str(product_blue.id) in ids
        assert str(product_green.id) not in ids


    def test_catalog_filter_by_characteristics_multiple_keys_and(
        self, client, db_session, service_key, test_category, test_seller
    ):
        """Фильтрация по нескольким ключам (AND) filters[color]=red&filters[size]=L"""
        # Создаём товар color=red, size=L
        product1 = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Red L Product",
            slug="red-l-product",
            description="Red L product",
            status=ProductStatus.MODERATED.value,
            deleted=False,
            blocked=False,
            characteristics_json=[
                {"name": "color", "value": "red"},
                {"name": "size", "value": "L"}
            ]
        )
        db_session.add(product1)
        db_session.flush()
        
        sku1 = SKU(
            id=uuid4(),
            product_id=product1.id,
            name="SKU1",
            price=1000000,
            cost_price=700000,
            discount=0,
            image="/s3/test.jpg",
            stock_quantity=10,
            active_quantity=10,
            reserved_quantity=0
        )
        db_session.add(sku1)
        
        # Создаём товар color=red, size=M (не должен попасть)
        product2 = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Red M Product",
            slug="red-m-product",
            description="Red M product",
            status=ProductStatus.MODERATED.value,
            deleted=False,
            blocked=False,
            characteristics_json=[
                {"name": "color", "value": "red"},
                {"name": "size", "value": "M"}
            ]
        )
        db_session.add(product2)
        db_session.flush()
        
        sku2 = SKU(
            id=uuid4(),
            product_id=product2.id,
            name="SKU2",
            price=1000000,
            cost_price=700000,
            discount=0,
            image="/s3/test.jpg",
            stock_quantity=10,
            active_quantity=10,
            reserved_quantity=0
        )
        db_session.add(sku2)
        db_session.commit()
        
        # Фильтр color=red AND size=L
        response = client.get(
            "/api/v1/public/products",
            params={
                "filters[color]": "red",
                "filters[size]": "L"
            },
            headers={"X-Service-Key": service_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == str(product1.id)
    