"""
Тесты для US-B2B-05: Просмотр карточки товара и причин блокировки
"""
import os
import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Устанавливаем переменные окружения для тестов
os.environ["B2C_TO_B2B_KEY"] = "test-b2c-key"
os.environ["B2B_TO_MOD_KEY"] = "test-mod-key"

from app.main import app
from app.database import get_db
from app.models.category import Category
from app.models.seller import Seller
from app.models.product import Product
from app.models.sku import SKU
from app.core.security import create_access_token
from app.schemas.product import ProductStatus


# ========== БАЗОВЫЕ ФИКСТУРЫ ==========

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
def client_with_db(db_session, auth_headers):
    """Тестовый клиент с переопределённой БД"""
    def _get_db():
        return db_session
    app.dependency_overrides[get_db] = _get_db
    client = TestClient(app)
    client.headers = auth_headers
    yield client
    app.dependency_overrides.clear()


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
def test_moderated_product(db_session, test_category, test_seller):
    """Создаём тестовый товар со статусом MODERATED"""
    product = Product(
        id=uuid4(),
        seller_id=test_seller.id,
        category_id=test_category.id,
        title="Moderated Product",
        slug="moderated-product",
        description="Approved product description",
        status=ProductStatus.MODERATED.value,
        deleted=False,
        blocked=False,
        moderation_comment=None,
        blocking_reason_id=None,
        field_reports_json=[]
    )
    db_session.add(product)
    db_session.flush()
    
    sku = SKU(
        id=uuid4(),
        product_id=product.id,
        name="SKU 1",
        price=1000000,
        cost_price=700000,
        discount=0,
        image="/s3/sku1.jpg",
        stock_quantity=10,
        active_quantity=5,
        reserved_quantity=2,
        article="SKU-001"
    )
    db_session.add(sku)
    db_session.commit()
    db_session.refresh(product)
    db_session.refresh(sku)
    return {"product": product, "sku": sku}


@pytest.fixture
def test_blocked_product(db_session, test_category, test_seller):
    """Создаём тестовый товар со статусом BLOCKED"""
    blocking_reason_id = uuid4()
    product = Product(
        id=uuid4(),
        seller_id=test_seller.id,
        category_id=test_category.id,
        title="Blocked Product",
        slug="blocked-product",
        description="This product was rejected",
        status=ProductStatus.BLOCKED.value,
        deleted=False,
        blocked=True,
        moderation_comment="Описание не соответствует товару",
        blocking_reason_id=blocking_reason_id,
        field_reports_json=[
            {
                "field_name": "description",
                "sku_id": None,
                "comment": "В описании указан материал 'натуральная кожа', на фото -- синтетика"
            },
            {
                "field_name": "sku_image",
                "sku_id": str(uuid4()),
                "comment": "Фото SKU не соответствует указанному цвету"
            }
        ]
    )
    db_session.add(product)
    db_session.flush()
    
    sku = SKU(
        id=uuid4(),
        product_id=product.id,
        name="SKU 1",
        price=899000,
        cost_price=450000,
        discount=0,
        image="/s3/sku1.jpg",
        stock_quantity=0,
        active_quantity=0,
        reserved_quantity=0,
        article="SKU-BLOCKED"
    )
    db_session.add(sku)
    db_session.commit()
    db_session.refresh(product)
    db_session.refresh(sku)
    return {"product": product, "sku": sku, "blocking_reason_id": blocking_reason_id}


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
        status=ProductStatus.MODERATED.value,
        deleted=False,
        blocked=False,
        moderation_comment=None,
        blocking_reason_id=None
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return {"product": product, "other_seller": other_seller}


# ========== ТЕСТЫ ==========

class TestB2B05ViewProduct:
    """Тесты для US-B2B-05: Просмотр карточки товара"""

    def test_get_moderated_product_returns_full_payload(
        self, client_with_db, test_moderated_product
    ):
        """Сценарий 1: MODERATED товар возвращает полный payload с cost_price"""
        product_id = test_moderated_product["product"].id
        
        response = client_with_db.get(
            f"/api/v1/products/{product_id}",
            headers=client_with_db.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Проверяем основные поля
        assert data["id"] == str(product_id)
        assert data["title"] == "Moderated Product"
        assert data["status"] == "MODERATED"
        assert data["deleted"] is False
        
        # blocking_reason_id должен быть None для MODERATED товара
        assert data["blocking_reason_id"] is None
        
        # Проверяем SKU с cost_price и reserved_quantity
        assert len(data["skus"]) == 1
        sku = data["skus"][0]
        assert sku["cost_price"] == 700000
        assert sku["reserved_quantity"] == 2
        assert sku["active_quantity"] == 5

    def test_get_blocked_product_returns_blocking_reason_and_field_reports(
        self, client_with_db, test_blocked_product
    ):
        """Сценарий 2: BLOCKED товар возвращает blocking_reason_id"""
        product_id = test_blocked_product["product"].id
        
        response = client_with_db.get(
            f"/api/v1/products/{product_id}",
            headers=client_with_db.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Проверяем основные поля
        assert data["id"] == str(product_id)
        assert data["title"] == "Blocked Product"
        assert data["status"] == "BLOCKED"
        assert data["deleted"] is False
        
        # blocking_reason_id должен быть заполнен
        assert data["blocking_reason_id"] == str(test_blocked_product["blocking_reason_id"])
        
        # moderator_comment должен быть заполнен
        assert data["moderator_comment"] is not None

    def test_get_others_product_returns_404(
        self, client_with_db, test_other_seller_product
    ):
        """Сценарий 3: чужой товар → 404 (не раскрываем существование)"""
        response = client_with_db.get(
            f"/api/v1/products/{test_other_seller_product['product'].id}",
            headers=client_with_db.headers
        )
        
        assert response.status_code == 404
        error_data = response.json()
        assert error_data["code"] == "NOT_FOUND"

    def test_get_nonexistent_returns_404(
        self, client_with_db
    ):
        """Сценарий 4: несуществующий товар → 404"""
        response = client_with_db.get(
            f"/api/v1/products/{uuid4()}",
            headers=client_with_db.headers
        )
        
        assert response.status_code == 404
        error_data = response.json()
        assert error_data["code"] == "NOT_FOUND"