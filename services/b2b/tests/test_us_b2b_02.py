"""
Тесты для US-B2B-02: Создание SKU
"""
import os
import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock

# Устанавливаем переменные окружения ДО импорта приложения
os.environ["B2B_TO_MOD_KEY"] = "test-mod-key"
os.environ["B2C_TO_B2B_KEY"] = "test-b2c-key"

from app.main import app
from app.database import get_db
from app.models.category import Category
from app.models.sku import SKU
from app.models.seller import Seller
from app.models.product import Product
from app.core.security import get_password_hash, create_access_token
from app.schemas.product import ProductStatus

# Фикстуры для тестов
@pytest.fixture
def client(db_session):
    """Тестовый клиент с переопределённой БД"""
    def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def db_session():
    """Тестовая сессия БД"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def test_category(db_session):
    """Создаём тестовую категорию с уникальным slug"""
    unique_suffix = str(uuid4())[:8]
    category = Category(
        id=uuid4(),
        name="Test Category",
        slug=f"test-category-{unique_suffix}",
        level=0,
        is_active=True
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


@pytest.fixture
def test_seller(db_session):
    """Создаём тестового продавца с уникальным INN и email"""
    unique_suffix = str(uuid4()).replace('-', '')[:12]
    seller = Seller(
        id=uuid4(),
        email=f"test_{unique_suffix}@example.com",
        hashed_password="fake_hash_for_testing",
        first_name="Test",
        last_name="Seller",
        company_name="Test Company",
        inn=f"{unique_suffix[:12]}",
        status="ACTIVE",
        is_active=True
    )
    db_session.add(seller)
    db_session.commit()
    db_session.refresh(seller)
    return seller


@pytest.fixture
def auth_headers(test_seller):
    """Создаём JWT токен для тестового продавца"""
    access_token = create_access_token(data={"sub": str(test_seller.id)})
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def test_product_created(db_session, test_category, test_seller):
    """Создаём тестовый товар со статусом CREATED"""
    product = Product(
        id=uuid4(),
        seller_id=test_seller.id,
        category_id=test_category.id,
        title="Test Product",
        slug="test-product",
        description="Test Description",
        status=ProductStatus.CREATED.value,
        deleted=False,
        blocked=False,
        moderation_comment=None,
        blocking_reason_id=None
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


@pytest.fixture
def test_product_hard_blocked(db_session, test_category, test_seller):
    """Создаём тестовый товар со статусом HARD_BLOCKED"""
    product = Product(
        id=uuid4(),
        seller_id=test_seller.id,
        category_id=test_category.id,
        title="Blocked Product",
        slug="blocked-product",
        description="Blocked Description",
        status=ProductStatus.HARD_BLOCKED.value,
        deleted=False,
        blocked=True,
        moderation_comment=None,
        blocking_reason_id=uuid4()
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


@pytest.fixture
def test_other_seller_product(db_session, test_category, test_seller):
    """Создаём товар другого продавца"""
    unique_suffix = str(uuid4()).replace('-', '')[:12]
    other_seller = Seller(
        id=uuid4(),
        email=f"other_{unique_suffix}@example.com",
        hashed_password="fake_hash_for_testing",
        first_name="Other",
        last_name="Seller",
        company_name="Other Company",
        inn=f"{unique_suffix[:12]}",
        status="ACTIVE",
        is_active=True
    )
    db_session.add(other_seller)
    db_session.flush()
    
    product = Product(
        id=uuid4(),
        seller_id=other_seller.id,
        category_id=test_category.id,
        title="Other Seller Product",
        slug="other-seller-product",
        description="Other Description",
        status=ProductStatus.CREATED.value,
        deleted=False,
        blocked=False,
        moderation_comment=None,
        blocking_reason_id=None
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return {"product": product, "other_seller": other_seller}


@pytest.fixture
def test_product_moderated(db_session, test_category, test_seller):
    """Создаём тестовый товар со статусом MODERATED и одним SKU"""
    product = Product(
        id=uuid4(),
        seller_id=test_seller.id,
        category_id=test_category.id,
        title="Moderated Product",
        slug="moderated-product",
        description="Description",
        status=ProductStatus.MODERATED.value,
        deleted=False,
        blocked=False,
        moderation_comment=None,
        blocking_reason_id=None
    )
    db_session.add(product)
    db_session.flush()
    
    sku = SKU(
        id=uuid4(),
        product_id=product.id,
        name="Existing SKU",
        price=1000000,
        cost_price=700000,
        discount=0,
        image="/s3/test.jpg",
        stock_quantity=0,
        active_quantity=0,
        reserved_quantity=0,
        article=None
    )
    db_session.add(sku)
    db_session.commit()
    db_session.refresh(product)
    db_session.refresh(sku)
    return {"product": product, "sku": sku}

class TestB2B02CreateSKU:
    """Тесты для US-B2B-02: Создание SKU"""

    def test_first_sku_transitions_product_to_on_moderation(
        self, client, auth_headers, test_product_created
    ):
        """Сценарий 1: первый SKU переводит товар в ON_MODERATION"""
        response = client.post("/api/v1/skus/", json={
            "product_id": str(test_product_created.id),
            "name": "256GB Black",
            "price": 12999000,
            "cost_price": 9500000,
            "discount": 0,
            "images": [
                {"url": "/s3/iphone15-black-256.jpg", "ordering": 0}
            ],
            "characteristics": [
                {"name": "Цвет", "value": "Чёрный"},
                {"name": "Объём памяти", "value": "256 ГБ"}
            ]
        }, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "256GB Black"
        assert data["price"] == 12999000
        assert data["cost_price"] == 9500000

        # Проверяем, что товар перешёл в ON_MODERATION
        product_response = client.get(
            f"/api/v1/products/{test_product_created.id}",
            headers=auth_headers
        )
        assert product_response.status_code == 200
        assert product_response.json()["status"] == "ON_MODERATION"

    def test_second_sku_no_state_change(
        self, client, auth_headers, test_product_created
    ):
        """Сценарий 2: второй SKU не меняет статус товара"""
        # Создаём первый SKU
        client.post("/api/v1/skus/", json={
            "product_id": str(test_product_created.id),
            "name": "256GB Black",
            "price": 12999000,
            "cost_price": 9500000,
            "discount": 0,
            "images": [
                {"url": "/s3/iphone15-black-256.jpg", "ordering": 0}
            ]
        }, headers=auth_headers)

        # Проверяем, что товар в ON_MODERATION
        product_response = client.get(
            f"/api/v1/products/{test_product_created.id}",
            headers=auth_headers
        )
        assert product_response.json()["status"] == "ON_MODERATION"

        # Создаём второй SKU
        response = client.post("/api/v1/skus/", json={
            "product_id": str(test_product_created.id),
            "name": "128GB White",
            "price": 9999000,
            "cost_price": 7500000,
            "discount": 0,
            "images": [
                {"url": "/s3/iphone15-white-128.jpg", "ordering": 0}
            ]
        }, headers=auth_headers)

        assert response.status_code == 201

        # Проверяем, что статус остался ON_MODERATION
        product_response = client.get(
            f"/api/v1/products/{test_product_created.id}",
            headers=auth_headers
        )
        assert product_response.json()["status"] == "ON_MODERATION"

    def test_add_sku_to_hard_blocked_returns_403(
        self, client, auth_headers, test_product_hard_blocked
    ):
        """Сценарий 3: добавление SKU к HARD_BLOCKED товару → 403"""
        response = client.post("/api/v1/skus/", json={
            "product_id": str(test_product_hard_blocked.id),
            "name": "256GB Black",
            "price": 12999000,
            "cost_price": 9500000,
            "discount": 0,
            "images": [
                {"url": "/s3/iphone15-black-256.jpg", "ordering": 0}
            ]
        }, headers=auth_headers)

        assert response.status_code == 403
        error_data = response.json()
        assert error_data["code"] == "FORBIDDEN"
        assert "hard-blocked" in error_data["message"].lower()

    def test_create_sku_with_empty_images_returns_201(
        self, client, auth_headers, test_product_created
    ):
        """OpenAPI: images опциональный, пустой массив допустим"""
        response = client.post("/api/v1/skus/", json={
            "product_id": str(test_product_created.id),
            "name": "256GB Black",
            "price": 12999000,
            "cost_price": 9500000,
            "discount": 0,
            "images": []  # пустой массив
        }, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["images"] == []

    def test_missing_price_returns_422(
        self, client, auth_headers, test_product_created
    ):
        """Сценарий 5: отсутствие price → 422 Validation Error (Pydantic)"""
        response = client.post("/api/v1/skus/", json={
            "product_id": str(test_product_created.id),
            "name": "256GB Black",
            "cost_price": 9500000,
            "discount": 0,
            "images": [
                {"url": "/s3/test.jpg", "ordering": 0}
            ]
        }, headers=auth_headers)

        # Pydantic validation error → 422
        assert response.status_code == 422

    def test_price_zero_returns_201(
        self, client, auth_headers, test_product_created
    ):
        """Сценарий 6: price = 0 разрешён (distressed/discounted SKU)"""
        response = client.post("/api/v1/skus/", json={
            "product_id": str(test_product_created.id),
            "name": "256GB Black",
            "price": 0,
            "cost_price": 9500000,
            "discount": 0,
            "images": [
                {"url": "/s3/test.jpg", "ordering": 0}
            ]
        }, headers=auth_headers)

        # price=0 разрешён по OpenAPI
        assert response.status_code == 201

    def test_product_not_found_returns_404(
        self, client, auth_headers
    ):
        """Сценарий 7: несуществующий product_id → 404"""
        response = client.post("/api/v1/skus/", json={
            "product_id": str(uuid4()),
            "name": "256GB Black",
            "price": 12999000,
            "cost_price": 9500000,
            "discount": 0,
            "images": [
                {"url": "/s3/test.jpg", "ordering": 0}
            ]
        }, headers=auth_headers)

        assert response.status_code == 404
        error_data = response.json()
        assert error_data["code"] == "NOT_FOUND"

    def test_create_sku_for_others_product_returns_403(
        self, client, auth_headers, test_other_seller_product
    ):
        """Сценарий 8: добавление SKU к чужому товару → 403"""
        response = client.post("/api/v1/skus/", json={
            "product_id": str(test_other_seller_product["product"].id),
            "name": "256GB Black",
            "price": 12999000,
            "cost_price": 9500000,
            "discount": 0,
            "images": [
                {"url": "/s3/iphone15-black-256.jpg", "ordering": 0}
            ]
        }, headers=auth_headers)

        assert response.status_code == 403
        error_data = response.json()
        assert error_data["code"] == "NOT_OWNER"  # ← FORBIDDEN → NOT_OWNER
        assert "does not belong" in error_data["message"].lower()
    
    def test_first_sku_sends_created_event_to_moderation(
        self, client, auth_headers, test_product_created, db_session
    ):
        """Проверка: первый SKU сохраняет событие CREATED в outbox"""
        from app.models.outbox import OutboxEvent
        
        response = client.post("/api/v1/skus/", json={
            "product_id": str(test_product_created.id),
            "name": "256GB Black",
            "price": 12999000,
            "cost_price": 9500000,
            "discount": 0,
            "images": [{"url": "/s3/test.jpg", "ordering": 0}]
        }, headers=auth_headers)
        
        assert response.status_code == 201
        
        # Проверяем, что событие сохранено в outbox
        outbox_events = db_session.query(OutboxEvent).all()
        assert len(outbox_events) >= 1
        
        # Проверяем, что событие правильного типа
        created_events = [e for e in outbox_events if e.event_type == "PRODUCT_CREATED"]
        assert len(created_events) >= 1
        
        event = created_events[0]
        assert event.target == "moderation"
        headers = event.headers
        assert headers.get("X-Service-Key") is not None
        assert len(headers.get("X-Service-Key", "")) > 0
    

    def test_adding_sku_to_moderated_re_moderates_product(
        self, client, db_session, auth_headers, test_product_moderated
    ):
        """Добавление SKU к MODERATED товару → товар в ON_MODERATION + событие EDITED"""
        # Проверяем, что товар изначально в MODERATED
        product_response = client.get(
            f"/api/v1/products/{test_product_moderated['product'].id}",
            headers=auth_headers
        )
        assert product_response.json()["status"] == "MODERATED"
        
        # Добавляем второй SKU
        response = client.post("/api/v1/skus/", json={
            "product_id": str(test_product_moderated["product"].id),
            "name": "Second SKU",
            "price": 12999000,
            "cost_price": 9500000,
            "discount": 0,
            "images": [{"url": "/s3/test.jpg", "ordering": 0}]
        }, headers=auth_headers)

        assert response.status_code == 201
        
        # Проверяем, что товар перешёл в ON_MODERATION
        product_response = client.get(
            f"/api/v1/products/{test_product_moderated['product'].id}",
            headers=auth_headers
        )
        assert product_response.json()["status"] == "ON_MODERATION"