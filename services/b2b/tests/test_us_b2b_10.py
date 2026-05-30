"""
Тесты для US-B2B-10: Списание резерва при доставке (fulfill)
"""
import os
import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

os.environ["B2C_TO_B2B_KEY"] = "test-b2c-key"
os.environ["B2B_TO_MOD_KEY"] = "test-mod-key"

from app.main import app
from app.database import SessionLocal
from app.models.category import Category
from app.models.seller import Seller
from app.models.product import Product
from app.models.sku import SKU
from app.models.fulfill_operation import FulfillOperation
from app.schemas.product import ProductStatus


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def service_key():
    return "test-b2c-key"


@pytest.fixture
def test_category(db_session):
    category = Category(
        id=uuid4(),
        name="Test Category",
        slug=f"test-category-{uuid4().hex[:8]}",
        level=0,
        is_active=True
    )
    db_session.add(category)
    db_session.commit()
    return category


@pytest.fixture
def test_seller(db_session):
    seller = Seller(
        id=uuid4(),
        email=f"test_{uuid4().hex[:12]}@example.com",
        hashed_password="hashed",
        first_name="Test",
        last_name="Seller",
        company_name="Test Company",
        inn=uuid4().hex[:12],
        status="ACTIVE",
        is_active=True
    )
    db_session.add(seller)
    db_session.commit()
    return seller


@pytest.fixture
def test_product_with_skus(db_session, test_category, test_seller):
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
    
    sku1 = SKU(
        id=uuid4(),
        product_id=product.id,
        name="SKU 1",
        price=1000000,
        cost_price=700000,
        discount=0,
        image="/s3/test1.jpg",
        stock_quantity=10,
        active_quantity=8,
        reserved_quantity=2,
        article="SKU-001"
    )
    sku2 = SKU(
        id=uuid4(),
        product_id=product.id,
        name="SKU 2",
        price=2000000,
        cost_price=1400000,
        discount=0,
        image="/s3/test2.jpg",
        stock_quantity=5,
        active_quantity=3,
        reserved_quantity=2,
        article="SKU-002"
    )
    db_session.add_all([sku1, sku2])
    db_session.commit()
    db_session.refresh(sku1)
    db_session.refresh(sku2)
    return {"product": product, "sku1": sku1, "sku2": sku2}


class TestB2B10Fulfill:
    """Тесты для US-B2B-10: Списание резерва при доставке"""

    def test_fulfill_decreases_reserved_quantity(
        self, client, db_session, service_key, test_product_with_skus
    ):
        """fulfill уменьшает reserved_quantity"""
        sku1 = test_product_with_skus["sku1"]
        order_id = uuid4()
        
        original_reserved = sku1.reserved_quantity  # 2
        
        response = client.post(
            "/api/v1/inventory/fulfill",
            json={
                "order_id": str(order_id),
                "items": [{"sku_id": str(sku1.id), "quantity": 1}]
            },
            headers={"X-Service-Key": service_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["order_id"] == str(order_id)
        assert data["status"] == "FULFILLED"
        
        db_session.refresh(sku1)
        assert sku1.reserved_quantity == original_reserved - 1  # 1

    def test_fulfill_active_quantity_unchanged(
        self, client, db_session, service_key, test_product_with_skus
    ):
        """active_quantity не изменяется после fulfill"""
        sku1 = test_product_with_skus["sku1"]
        order_id = uuid4()
        
        original_active = sku1.active_quantity  # 8
        
        client.post(
            "/api/v1/inventory/fulfill",
            json={
                "order_id": str(order_id),
                "items": [{"sku_id": str(sku1.id), "quantity": 1}]
            },
            headers={"X-Service-Key": service_key}
        )
        
        db_session.refresh(sku1)
        assert sku1.active_quantity == original_active  # осталось 8

    def test_fulfill_insufficient_reserved_returns_409(
        self, client, service_key, test_product_with_skus
    ):
        """попытка списать больше, чем зарезервировано → 409"""
        sku1 = test_product_with_skus["sku1"]
        order_id = uuid4()
        
        response = client.post(
            "/api/v1/inventory/fulfill",
            json={
                "order_id": str(order_id),
                "items": [{"sku_id": str(sku1.id), "quantity": 10}]
            },
            headers={"X-Service-Key": service_key}
        )
        
        assert response.status_code == 409
        error_data = response.json()
        assert error_data["code"] == "INSUFFICIENT_RESERVED"

    def test_idempotent_fulfill_no_double_deduction(
        self, client, db_session, service_key, test_product_with_skus
    ):
        """повторный запрос с тем же order_id → 200, данные не изменились"""
        sku1 = test_product_with_skus["sku1"]
        order_id = uuid4()
        
        # Первый запрос
        response1 = client.post(
            "/api/v1/inventory/fulfill",
            json={
                "order_id": str(order_id),
                "items": [{"sku_id": str(sku1.id), "quantity": 1}]
            },
            headers={"X-Service-Key": service_key}
        )
        assert response1.status_code == 200
        
        db_session.refresh(sku1)
        reserved_after_first = sku1.reserved_quantity  # 1 (было 2)
        
        # Второй запрос с тем же order_id
        response2 = client.post(
            "/api/v1/inventory/fulfill",
            json={
                "order_id": str(order_id),
                "items": [{"sku_id": str(sku1.id), "quantity": 1}]
            },
            headers={"X-Service-Key": service_key}
        )
        assert response2.status_code == 200
        
        db_session.refresh(sku1)
        assert sku1.reserved_quantity == reserved_after_first  # не изменилось

    def test_missing_service_key_returns_401(self, client):
        """отсутствует X-Service-Key → 401"""
        response = client.post(
            "/api/v1/inventory/fulfill",
            json={
                "order_id": str(uuid4()),
                "items": [{"sku_id": str(uuid4()), "quantity": 1}]
            }
        )
        assert response.status_code == 401

    def test_invalid_service_key_returns_401(self, client):
        """неверный X-Service-Key → 401"""
        response = client.post(
            "/api/v1/inventory/fulfill",
            json={
                "order_id": str(uuid4()),
                "items": [{"sku_id": str(uuid4()), "quantity": 1}]
            },
            headers={"X-Service-Key": "wrong-key"}
        )
        assert response.status_code == 401

    def test_sku_not_found_returns_404(self, client, service_key):
        """несуществующий SKU → 404"""
        response = client.post(
            "/api/v1/inventory/fulfill",
            json={
                "order_id": str(uuid4()),
                "items": [{"sku_id": str(uuid4()), "quantity": 1}]
            },
            headers={"X-Service-Key": service_key}
        )
        assert response.status_code == 404
        error_data = response.json()
        assert error_data["code"] == "NOT_FOUND"