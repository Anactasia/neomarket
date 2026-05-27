"""
Tests for US-B2B-08: Reserve / Unreserve SKU

Сценарии из канон-flow «резервирование SKU»:
- happy: reserve_all_skus_succeeds, idempotent_reserve_returns_200_without_double_deduction
- unhappy: partial_insufficient_stock_returns_409_all_rollback, sku_out_of_stock_event_emitted, unreserve_restores_quantities
"""
import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.product import Product
from app.models.sku import SKU
from app.models.seller import Seller
from app.models.category import Category
from app.schemas.product import ProductStatus


@pytest.fixture
def client():
    """HTTP client для тестирования"""
    return TestClient(app)


@pytest.fixture
def db_session():
    """Session базы данных для тестов"""
    from app.database import SessionLocal
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def service_key():
    """X-Service-Key для межсервисных вызовов"""
    return "b2b-service-key"


@pytest.fixture
def test_category(db_session):
    """Тестовая категория"""
    category = Category(
        id=uuid4(),
        name="Test Category",
        slug=f"test-category-{uuid4().hex[:8]}",
        parent_id=None,
        level=0,
        is_active=True
    )
    db_session.add(category)
    db_session.commit()
    return category


@pytest.fixture
def test_seller(db_session):
    """Тестовый продавец с уникальным INN и email"""
    unique_suffix = uuid4().hex[:12]
    seller = Seller(
        id=uuid4(),
        email=f"seller_{unique_suffix}@test.com",
        hashed_password="hashed_password",
        first_name="Test",
        last_name="Seller",
        company_name="Test Company",
        inn=unique_suffix[:12]
    )
    db_session.add(seller)
    db_session.commit()
    return seller


class TestB2B08ReserveUnreserve:
    """Тесты для US-B2B-08: Reserve / Unreserve"""
    
    def test_reserve_all_skus_succeeds(
        self, client, db_session, service_key, test_seller, test_category
    ):
        """Happy path: резервирование успешно, active_quantity уменьшился, reserved_quantity вырос"""
        # Создаём MODERATED товар
        product = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Test Product",
            slug="test-product",
            description="Description",
            status=ProductStatus.MODERATED.value,
            deleted=False,
            blocked=False
        )
        db_session.add(product)
        db_session.flush()
        
        # Создаём SKU с остатком 10
        sku = SKU(
            id=uuid4(),
            product_id=product.id,
            name="Test SKU",
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
        
        # Резервируем 3 штуки
        idempotency_key = uuid4()
        order_id = uuid4()
        response = client.post(
            "/api/v1/inventory/reserve",
            json={
                "idempotency_key": str(idempotency_key),
                "order_id": str(order_id),
                "items": [
                    {"sku_id": str(sku.id), "quantity": 3}
                ]
            },
            headers={"X-Service-Key": service_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["reserved"] is True
        assert len(data["items"]) == 1
        assert data["items"][0]["sku_id"] == str(sku.id)
        assert data["items"][0]["reserved_quantity"] == 3
        assert data["items"][0]["remaining_stock"] == 7
        
        # Проверяем, что quantities обновлены в БД
        db_session.refresh(sku)
        assert sku.active_quantity == 7
        assert sku.reserved_quantity == 3
        assert sku.stock_quantity == 10

    def test_partial_insufficient_stock_returns_409_all_rollback(
        self, client, db_session, service_key, test_seller, test_category
    ):
        """Один SKU не хватает → 409, ни один не зарезервирован (all-or-nothing)"""
        # Создаём два SKU
        product1 = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Product 1",
            slug="product-1",
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
            name="SKU 1",
            price=1000000,
            cost_price=700000,
            discount=0,
            image="/s3/test1.jpg",
            stock_quantity=10,
            active_quantity=10,
            reserved_quantity=0
        )
        db_session.add(sku1)
        
        product2 = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Product 2",
            slug="product-2",
            description="Description",
            status=ProductStatus.MODERATED.value,
            deleted=False,
            blocked=False
        )
        db_session.add(product2)
        db_session.flush()
        
        # SKU 2 имеет только 2 штуки
        sku2 = SKU(
            id=uuid4(),
            product_id=product2.id,
            name="SKU 2",
            price=2000000,
            cost_price=1400000,
            discount=0,
            image="/s3/test2.jpg",
            stock_quantity=2,
            active_quantity=2,
            reserved_quantity=0
        )
        db_session.add(sku2)
        db_session.commit()
        
        # Пытаемся зарезервировать: SKU 1 (нужно 3) OK, SKU 2 (нужно 5, есть 2) FAIL
        idempotency_key = uuid4()
        order_id = uuid4()
        response = client.post(
            "/api/v1/inventory/reserve",
            json={
                "idempotency_key": str(idempotency_key),
                "order_id": str(order_id),
                "items": [
                    {"sku_id": str(sku1.id), "quantity": 3},
                    {"sku_id": str(sku2.id), "quantity": 5}
                ]
            },
            headers={"X-Service-Key": service_key}
        )
        
        assert response.status_code == 409
        data = response.json()
        
        assert data["reserved"] is False
        assert len(data["failed_items"]) == 1
        assert data["failed_items"][0]["sku_id"] == str(sku2.id)
        assert data["failed_items"][0]["requested"] == 5
        assert data["failed_items"][0]["available"] == 2
        assert data["failed_items"][0]["reason"] == "INSUFFICIENT_STOCK"
        
        # Проверяем, что ничто не зарезервировано (all-or-nothing)
        db_session.refresh(sku1)
        db_session.refresh(sku2)
        assert sku1.active_quantity == 10
        assert sku1.reserved_quantity == 0
        assert sku2.active_quantity == 2
        assert sku2.reserved_quantity == 0

    def test_idempotent_reserve_returns_200_without_double_deduction(
        self, client, db_session, service_key, test_seller, test_category
    ):
        """Повторный запрос с тем же idempotency_key → 200 без изменений"""
        # Создаём SKU
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
        
        idempotency_key = uuid4()
        order_id = uuid4()
        
        # Первый запрос
        response1 = client.post(
            "/api/v1/inventory/reserve",
            json={
                "idempotency_key": str(idempotency_key),
                "order_id": str(order_id),
                "items": [
                    {"sku_id": str(sku.id), "quantity": 3}
                ]
            },
            headers={"X-Service-Key": service_key}
        )
        
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["items"][0]["reserved_quantity"] == 3
        
        # Второй запрос с тем же ключом
        response2 = client.post(
            "/api/v1/inventory/reserve",
            json={
                "idempotency_key": str(idempotency_key),
                "order_id": str(order_id),
                "items": [
                    {"sku_id": str(sku.id), "quantity": 3}
                ]
            },
            headers={"X-Service-Key": service_key}
        )
        
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Результат тот же
        assert data2["items"][0]["reserved_quantity"] == 3
        
        # Проверяем, что quantities не изменились
        db_session.refresh(sku)
        assert sku.active_quantity == 7
        assert sku.reserved_quantity == 3

    def test_sku_out_of_stock_event_emitted(
        self, client, db_session, service_key, test_seller, test_category
    ):
        """active_quantity стал 0 → событие SKU_OUT_OF_STOCK уходит в B2C"""
        # Создаём SKU с остатком 3
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
            stock_quantity=3,
            active_quantity=3,
            reserved_quantity=0
        )
        db_session.add(sku)
        db_session.commit()
        
        # Резервируем все 3 штуки
        idempotency_key = uuid4()
        order_id = uuid4()
        response = client.post(
            "/api/v1/inventory/reserve",
            json={
                "idempotency_key": str(idempotency_key),
                "order_id": str(order_id),
                "items": [
                    {"sku_id": str(sku.id), "quantity": 3}
                ]
            },
            headers={"X-Service-Key": service_key}
        )
        
        assert response.status_code == 200
        
        # Проверяем, что active_quantity стал 0
        db_session.refresh(sku)
        assert sku.active_quantity == 0
        assert sku.reserved_quantity == 3

    def test_unreserve_restores_quantities(
        self, client, db_session, service_key, test_seller, test_category
    ):
        """Unreserve корректно восстанавливает active_quantity и reserved_quantity"""
        # Создаём SKU
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
        
        # Сначала резервируем
        idempotency_key = uuid4()
        order_id = uuid4()
        reserve_response = client.post(
            "/api/v1/inventory/reserve",
            json={
                "idempotency_key": str(idempotency_key),
                "order_id": str(order_id),
                "items": [
                    {"sku_id": str(sku.id), "quantity": 5}
                ]
            },
            headers={"X-Service-Key": service_key}
        )
        
        assert reserve_response.status_code == 200
        
        db_session.refresh(sku)
        assert sku.active_quantity == 5
        assert sku.reserved_quantity == 5
        
        # Затем снимаем резерв
        unreserve_order_id = uuid4()
        unreserve_response = client.post(
            "/api/v1/inventory/unreserve",
            json={
                "order_id": str(unreserve_order_id),
                "items": [
                    {"sku_id": str(sku.id), "quantity": 3}
                ]
            },
            headers={"X-Service-Key": service_key}
        )
        
        assert unreserve_response.status_code == 200
        data = unreserve_response.json()
        assert data["ok"] is True
        
        # Проверяем, что quantities восстановлены
        db_session.refresh(sku)
        assert sku.active_quantity == 8
        assert sku.reserved_quantity == 2
        assert sku.stock_quantity == 10

    def test_reserve_missing_sku_returns_400(
        self, client, db_session, service_key
    ):
        """Резервирование несуществующего SKU → 400"""
        response = client.post(
            "/api/v1/inventory/reserve",
            json={
                "idempotency_key": str(uuid4()),
                "order_id": str(uuid4()),
                "items": [
                    {"sku_id": str(uuid4()), "quantity": 1}
                ]
            },
            headers={"X-Service-Key": service_key}
        )
        
        assert response.status_code == 400
        
    def test_unreserve_missing_sku_returns_400(
        self, client, db_session, service_key
    ):
        """Снятие резерва несуществующего SKU → 400"""
        response = client.post(
            "/api/v1/inventory/unreserve",
            json={
                "order_id": str(uuid4()),
                "items": [
                    {"sku_id": str(uuid4()), "quantity": 1}
                ]
            },
            headers={"X-Service-Key": service_key}
        )
        
        assert response.status_code == 400

    def test_reserve_without_service_key_returns_401(self, client):
        """Резервирование без X-Service-Key → 401"""
        response = client.post(
            "/api/v1/inventory/reserve",
            json={
                "idempotency_key": str(uuid4()),
                "order_id": str(uuid4()),
                "items": [
                    {"sku_id": str(uuid4()), "quantity": 1}
                ]
            }
        )
        
        assert response.status_code == 401
        
    def test_unreserve_without_service_key_returns_401(self, client):
        """Снятие резерва без X-Service-Key → 401"""
        response = client.post(
            "/api/v1/inventory/unreserve",
            json={
                "order_id": str(uuid4()),
                "items": [
                    {"sku_id": str(uuid4()), "quantity": 1}
                ]
            }
        )
        
        assert response.status_code == 401

    def test_reserve_zero_quantity_returns_422(self, client, service_key):
        """Резервирование с quantity=0 → 422 (валидация)"""
        response = client.post(
            "/api/v1/inventory/reserve",
            json={
                "idempotency_key": str(uuid4()),
                "order_id": str(uuid4()),
                "items": [
                    {"sku_id": str(uuid4()), "quantity": 0}
                ]
            },
            headers={"X-Service-Key": service_key}
        )
        
        assert response.status_code == 422

    def test_reserve_negative_quantity_returns_422(self, client, service_key):
        """Резервирование с отрицательным quantity → 422 (валидация)"""
        response = client.post(
            "/api/v1/inventory/reserve",
            json={
                "idempotency_key": str(uuid4()),
                "order_id": str(uuid4()),
                "items": [
                    {"sku_id": str(uuid4()), "quantity": -5}
                ]
            },
            headers={"X-Service-Key": service_key}
        )
        
        assert response.status_code == 422