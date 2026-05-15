"""
Тесты для US-B2B-02: Создание SKU
"""
import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import get_db
from app.models.category import Category
from app.models.seller import Seller
from app.models.product import Product
from app.core.security import get_password_hash, create_access_token
from app.schemas.product import ProductStatus


# Фикстуры для тестов
@pytest.fixture
def client():
    """Тестовый клиент"""
    return TestClient(app)


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
            "image": "/s3/iphone15-black-256.jpg",
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
            "image": "/s3/iphone15-black-256.jpg"
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
            "image": "/s3/iphone15-white-128.jpg"
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
            "image": "/s3/iphone15-black-256.jpg"
        }, headers=auth_headers)

        assert response.status_code == 403
        error_data = response.json()
        assert error_data["detail"]["code"] == "FORBIDDEN"
        assert "hard-blocked" in error_data["detail"]["message"].lower()

    def test_missing_image_returns_400(
        self, client, auth_headers, test_product_created
    ):
        """Сценарий 4: отсутствие image → 400"""
        response = client.post("/api/v1/skus/", json={
            "product_id": str(test_product_created.id),
            "name": "256GB Black",
            "price": 12999000,
            "cost_price": 9500000,
            "discount": 0,
            "image": None
        }, headers=auth_headers)

        assert response.status_code == 400
        error_data = response.json()
        # Проверяем структуру ошибки (может быть detail или на верхнем уровне)
        if "detail" in error_data:
            assert error_data["detail"]["code"] == "INVALID_REQUEST"
        else:
            assert error_data["code"] == "INVALID_REQUEST"

    def test_missing_price_returns_400(
        self, client, auth_headers, test_product_created
    ):
        """Сценарий 5: отсутствие price → 400"""
        response = client.post("/api/v1/skus/", json={
            "product_id": str(test_product_created.id),
            "name": "256GB Black",
            "cost_price": 9500000,
            "discount": 0,
            "image": "/s3/test.jpg"
        }, headers=auth_headers)

        # Pydantic возвращает 422 для missing required fields
        assert response.status_code in [400, 422]

    def test_price_zero_returns_400(
        self, client, auth_headers, test_product_created
    ):
        """Сценарий 6: price = 0 → 400"""
        response = client.post("/api/v1/skus/", json={
            "product_id": str(test_product_created.id),
            "name": "256GB Black",
            "price": 0,
            "cost_price": 9500000,
            "discount": 0,
            "image": "/s3/test.jpg"
        }, headers=auth_headers)

        assert response.status_code == 400
        error_data = response.json()
        # Проверяем структуру ошибки
        if "detail" in error_data:
            assert error_data["detail"]["code"] == "INVALID_REQUEST"
        else:
            assert error_data["code"] == "INVALID_REQUEST"

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
            "image": "/s3/test.jpg"
        }, headers=auth_headers)

        assert response.status_code == 404
        error_data = response.json()
        assert error_data["detail"]["code"] == "NOT_FOUND"