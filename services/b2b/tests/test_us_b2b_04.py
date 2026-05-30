"""
Тесты для US-B2B-04: Удаление товара
"""
import os
import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock

# Устанавливаем переменные окружения ДО импорта приложения
os.environ["B2B_TO_MOD_KEY"] = "test-mod-key"
os.environ["B2B_TO_B2C_KEY"] = "test-b2c-key"

from app.main import app
from app.database import get_db
from app.models.category import Category
from app.models.seller import Seller
from app.models.product import Product
from app.models.sku import SKU
from app.core.security import get_password_hash, create_access_token
from app.schemas.product import ProductStatus

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
    # Сохраняем headers для использования в тестах
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
def test_product_with_skus(db_session, test_category, test_seller):
    """Создаём тестовый товар со статусом MODERATED и SKU"""
    product = Product(
        id=uuid4(),
        seller_id=test_seller.id,
        category_id=test_category.id,
        title="Product with SKUs",
        slug="product-with-skus",
        description="Description",
        status=ProductStatus.MODERATED.value,
        deleted=False,
        blocked=False,
        moderation_comment=None,
        blocking_reason_id=None
    )
    db_session.add(product)
    db_session.flush()
    
    # Создаем SKU
    sku1 = SKU(
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
    sku2 = SKU(
        id=uuid4(),
        product_id=product.id,
        name="SKU 2",
        price=1500000,
        cost_price=900000,
        discount=0,
        image="/s3/sku2.jpg",
        stock_quantity=20,
        active_quantity=15,
        reserved_quantity=3,
        article="SKU-002"
    )
    db_session.add(sku1)
    db_session.add(sku2)
    db_session.commit()
    db_session.refresh(product)
    db_session.refresh(sku1)
    db_session.refresh(sku2)
    return {"product": product, "sku1": sku1, "sku2": sku2}


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


@pytest.fixture
def test_product_hard_blocked(db_session, test_category, test_seller):
    """Создаём HARD_BLOCKED товар"""
    product = Product(
        id=uuid4(),
        seller_id=test_seller.id,
        category_id=test_category.id,
        title="Hard Blocked Product",
        slug="hard-blocked-product",
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


class TestB2B04DeleteProduct:
    """Тесты для US-B2B-04: Удаление товара"""

    def test_delete_sets_deleted_true(
    self, client_with_db, test_product_created, db_session
):
        """Сценарий 1: happy path — soft delete устанавливает deleted=true"""
        response = client_with_db.delete(
            f"/api/v1/products/{test_product_created.id}",
            headers=client_with_db.headers
        )
        
        # OpenAPI требует 204 No Content
        assert response.status_code == 204
        assert response.text == ""  # пустое тело
        
        # Проверяем, что deleted=true в БД
        from app.models.product import Product
        product_in_db = db_session.query(Product).filter(
            Product.id == test_product_created.id
        ).first()
        assert product_in_db.deleted is True

    def test_delete_already_deleted_returns_400(
        self, client_with_db, test_product_created
    ):
        """Сценарий 2: повторное удаление → 400 (бизнес-ошибка)"""
        # Первое удаление
        response = client_with_db.delete(
            f"/api/v1/products/{test_product_created.id}",
            headers=client_with_db.headers
        )
        assert response.status_code == 204
        
        # Второе удаление (товар уже удалён) → 400
        response = client_with_db.delete(
            f"/api/v1/products/{test_product_created.id}",
            headers=client_with_db.headers
        )
        
        # US-B2B-04 требует 400 с {"code": "INVALID_REQUEST", "message": "Product already deleted"}
        assert response.status_code == 400
        data = response.json()
        assert data["code"] == "INVALID_REQUEST"
        assert "deleted" in data["message"].lower()
        
    def test_delete_others_product_returns_403(
        self, client_with_db, test_other_seller_product
    ):
        """Сценарий 3: удаление чужого товара → 403 NOT_OWNER"""
        response = client_with_db.delete(
            f"/api/v1/products/{test_other_seller_product['product'].id}",
            headers=client_with_db.headers
        )
        
        assert response.status_code == 403
        error_data = response.json()
        assert error_data["code"] == "NOT_OWNER"
        assert "belong" in error_data["message"].lower()

    def test_delete_nonexistent_product_returns_404(
        self, client_with_db
    ):
        """Сценарий 4: удаление несуществующего товара → 404"""
        response = client_with_db.delete(
            f"/api/v1/products/{uuid4()}",
            headers=client_with_db.headers
        )
        
        assert response.status_code == 404
        error_data = response.json()
        # flat-формат ошибки
        assert error_data["code"] == "NOT_FOUND"

    def test_deleted_product_not_in_seller_list(
        self, client_with_db, test_product_created
    ):
        """Сценарий 5: удалённый товар не виден в списке продавца"""
        # Удаляем товар
        client_with_db.delete(
            f"/api/v1/products/{test_product_created.id}",
            headers=client_with_db.headers
        )
        
        # Проверяем список товаров
        response = client_with_db.get(
            "/api/v1/products/",
            headers=client_with_db.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        product_ids = [p["id"] for p in data["items"]]
        assert str(test_product_created.id) not in product_ids

    def test_deleted_product_visible_with_include_deleted(
        self, client_with_db, test_product_created
    ):
        """Сценарий 6: удалённый товар виден с include_deleted=true"""
        # Удаляем товар
        client_with_db.delete(
            f"/api/v1/products/{test_product_created.id}",
            headers=client_with_db.headers
        )
        
        # Проверяем список с include_deleted=true
        response = client_with_db.get(
            "/api/v1/products/?include_deleted=true",
            headers=client_with_db.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        product_ids = [p["id"] for p in data["items"]]
        assert str(test_product_created.id) in product_ids

    def test_delete_with_skus_sends_sku_ids(
        self, client_with_db, test_product_with_skus, db_session
    ):
        """Сценарий 7: при удалении товара с SKU в B2C уходят sku_ids"""
        from app.models.outbox import OutboxEvent
        
        # Очищаем outbox перед тестом
        db_session.query(OutboxEvent).delete()
        db_session.commit()
        
        product = test_product_with_skus["product"]
        sku1 = test_product_with_skus["sku1"]
        sku2 = test_product_with_skus["sku2"]
        
        response = client_with_db.delete(
            f"/api/v1/products/{product.id}",
            headers=client_with_db.headers
        )
        
        assert response.status_code == 204
        
        # Проверяем, что товар удалён
        product_in_db = db_session.query(Product).filter(
            Product.id == product.id
        ).first()
        assert product_in_db.deleted is True
        
        # Проверяем outbox на наличие события для B2C
        db_session.commit()
        outbox_events = db_session.query(OutboxEvent).filter(
            OutboxEvent.target == "b2c",
            OutboxEvent.event_type == "PRODUCT_DELETED"
        ).all()
        
        assert len(outbox_events) >= 1, "Should have at least one B2C event in outbox"
        
        # Находим событие для нашего товара (фильтруем по product_id)
        event = None
        for e in outbox_events:
            if e.payload["payload"]["product_id"] == str(product.id):
                event = e
                break
        
        assert event is not None, "Event for this product not found"
        assert event.target == "b2c"
        import os
        expected_key = os.getenv("B2B_TO_B2C_KEY", "b2b-to-b2c-key")
        assert expected_key in str(event.headers), f"Expected '{expected_key}' in headers, got {event.headers}"
        
        payload = event.payload
        assert payload["event_type"] == "PRODUCT_DELETED"
        assert payload["payload"]["product_id"] == str(product.id)
        assert str(sku1.id) in payload["payload"]["sku_ids"]
        assert str(sku2.id) in payload["payload"]["sku_ids"]
    

    def test_delete_sends_deleted_event_to_moderation(
        self, client_with_db, test_product_created, db_session
    ):
        """Проверка: удаление отправляет событие DELETED в Moderation"""
        from app.models.outbox import OutboxEvent
        
        response = client_with_db.delete(
            f"/api/v1/products/{test_product_created.id}",
            headers=client_with_db.headers
        )
        
        assert response.status_code == 204
        
        db_session.commit()
        
        # Фильтруем по product_id для точности
        outbox_events = db_session.query(OutboxEvent).filter(
            OutboxEvent.target == "moderation",
            OutboxEvent.event_type == "PRODUCT_DELETED"
        ).all()
        
        # Находим событие для нашего товара
        event = None
        for e in outbox_events:
            if e.payload["payload"]["product_id"] == str(test_product_created.id):
                event = e
                break
        
        assert event is not None, "Event for this product not found"
        assert event.target == "moderation"
        
        # Проверяем, что заголовок X-Service-Key установлен (не пустой)
        headers = event.headers
        assert headers.get("X-Service-Key") is not None
        assert len(headers.get("X-Service-Key", "")) > 0
        
        payload = event.payload
        assert payload["event_type"] == "PRODUCT_DELETED"
        assert "idempotency_key" in payload
        assert "occurred_at" in payload
        assert payload["payload"]["product_id"] == str(test_product_created.id)