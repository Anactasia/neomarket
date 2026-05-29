"""
Тесты для US-B2B-11: Список товаров продавца
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
from app.core.security import create_access_token
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
def test_other_seller(db_session):
    seller = Seller(
        id=uuid4(),
        email=f"other_{uuid4().hex[:12]}@example.com",
        hashed_password="hashed",
        first_name="Other",
        last_name="Seller",
        company_name="Other Company",
        inn=uuid4().hex[:12],
        status="ACTIVE",
        is_active=True
    )
    db_session.add(seller)
    db_session.commit()
    return seller


@pytest.fixture
def auth_headers(test_seller):
    access_token = create_access_token(data={"sub": str(test_seller.id)})
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def test_products(db_session, test_category, test_seller, test_other_seller):
    """Создаёт товары для текущего и другого продавца"""
    product1 = Product(
        id=uuid4(),
        seller_id=test_seller.id,
        category_id=test_category.id,
        title="Active Product",
        slug="active-product",
        description="Active description",
        status=ProductStatus.MODERATED.value,
        deleted=False,
        blocked=False
    )
    product2 = Product(
        id=uuid4(),
        seller_id=test_seller.id,
        category_id=test_category.id,
        title="Blocked Product",
        slug="blocked-product",
        description="Blocked description",
        status=ProductStatus.BLOCKED.value,
        deleted=False,
        blocked=True
    )
    product3 = Product(
        id=uuid4(),
        seller_id=test_seller.id,
        category_id=test_category.id,
        title="Deleted Product",
        slug="deleted-product",
        description="Deleted description",
        status=ProductStatus.CREATED.value,
        deleted=True,
        blocked=False
    )
    product_other = Product(
        id=uuid4(),
        seller_id=test_other_seller.id,
        category_id=test_category.id,
        title="Other Seller Product",
        slug="other-product",
        description="Other description",
        status=ProductStatus.MODERATED.value,
        deleted=False,
        blocked=False
    )
    
    db_session.add_all([product1, product2, product3, product_other])
    db_session.commit()
    
    return {
        "product1": product1,
        "product2": product2,
        "product3": product3,
        "product_other": product_other
    }


class TestB2B11SellerProducts:
    """Тесты для US-B2B-11: Список товаров продавца"""

    def test_list_returns_only_own_products(
        self, client, auth_headers, test_products
    ):
        """Только товары текущего продавца (IDOR защита)"""
        response = client.get(
            "/api/v1/products/",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Должны быть только НЕ удалённые товары текущего продавца (2 штуки)
        assert data["total_count"] == 2
        product_ids = [p["id"] for p in data["items"]]
        assert str(test_products["product_other"].id) not in product_ids
        # Удалённый товар не должен быть в ответе (без include_deleted)
        assert str(test_products["product3"].id) not in product_ids

    def test_deleted_products_visible_with_deleted_flag(
        self, client, auth_headers, test_products
    ):
        """Удалённые товары видны с include_deleted=true"""
        response = client.get(
            "/api/v1/products/?include_deleted=true",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_count"] == 3
        
        deleted_product = next(
            (p for p in data["items"] if p["id"] == str(test_products["product3"].id)),
            None
        )
        assert deleted_product is not None
        assert deleted_product["deleted"] is True

    def test_status_filter_works_correctly(
        self, client, auth_headers, test_products
    ):
        """Фильтр по статусу работает корректно"""
        response = client.get(
            "/api/v1/products/?status=BLOCKED",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_count"] == 1
        assert data["items"][0]["id"] == str(test_products["product2"].id)
        assert data["items"][0]["status"] == "BLOCKED"

    def test_search_by_title_case_insensitive(
        self, client, auth_headers, test_products
    ):
        """Поиск по названию регистронезависимый"""
        response = client.get(
            "/api/v1/products/?search=ACTIVE",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_count"] == 1
        assert data["items"][0]["title"] == "Active Product"

    def test_missing_auth_returns_401(self, client):
        """Отсутствует JWT → 401"""
        response = client.get("/api/v1/products/")
        assert response.status_code == 401
        error_data = response.json()
        assert error_data["code"] == "UNAUTHORIZED"