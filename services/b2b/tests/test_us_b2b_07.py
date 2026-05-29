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
    
    # Сначала удаляем зависимые записи (дочерние таблицы)
    db_session.query(InvoiceItem).delete()
    db_session.query(Invoice).delete()
    db_session.query(SKU).delete()
    db_session.query(Product).delete()
    db_session.commit()
    yield


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