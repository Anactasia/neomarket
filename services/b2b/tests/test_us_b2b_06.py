"""
Тесты для US-B2B-06: Создание накладной на поступление товара
"""
import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import SessionLocal
from app.models.category import Category
from app.models.seller import Seller
from app.models.product import Product
from app.models.sku import SKU
from app.core.security import create_access_token
from app.schemas.product import ProductStatus


def _invoice_headers(auth_headers: dict) -> dict:
    """Добавляет Idempotency-Key к заголовкам"""
    return {
        **auth_headers,
        "Idempotency-Key": str(uuid4())
    }


def _accept_headers(auth_headers: dict) -> dict:
    """Добавляет Idempotency-Key к заголовкам для accept"""
    return {
        **auth_headers,
        "Idempotency-Key": str(uuid4())
    }


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


@pytest.fixture
def auth_headers(test_seller):
    """JWT токен для продавца"""
    access_token = create_access_token(data={"sub": str(test_seller.id)})
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def test_product_moderated(db_session, test_category, test_seller):
    """Товар со статусом MODERATED"""
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
        name="Moderated SKU",
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


@pytest.fixture
def test_product_created(db_session, test_category, test_seller):
    """Товар со статусом CREATED (не MODERATED)"""
    product = Product(
        id=uuid4(),
        seller_id=test_seller.id,
        category_id=test_category.id,
        title="Created Product",
        slug="created-product",
        description="Description",
        status=ProductStatus.CREATED.value,
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
        name="Created SKU",
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
    db_session.refresh(sku)
    return {"product": product, "sku": sku}


@pytest.fixture
def test_other_seller_sku(db_session, test_category, test_seller):
    """SKU другого продавца"""
    other_seller = Seller(
        id=uuid4(),
        email=f"other_{uuid4().hex[:12]}@example.com",
        hashed_password="fake_hash",
        first_name="Other",
        last_name="Seller",
        company_name="Other Company",
        inn=f"{uuid4().hex[:12]}",
        status="ACTIVE",
        is_active=True
    )
    db_session.add(other_seller)
    db_session.flush()
    
    product = Product(
        id=uuid4(),
        seller_id=other_seller.id,
        category_id=test_category.id,
        title="Other Product",
        slug="other-product",
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
        name="Other SKU",
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
    db_session.refresh(sku)
    return {"sku": sku, "other_seller": other_seller}


class TestB2B06AcceptInvoice:
    """Тесты для приёмки накладной"""

    def test_accept_invoice_full_returns_200_and_accepts(
        self, client, db_session, auth_headers, test_product_moderated
    ):
        """Полная приёмка накладной → ACCEPTED"""
        # Создаём накладную
        invoice_resp = client.post(
            "/api/v1/invoices/",
            json={
                "items": [
                    {
                        "sku_id": str(test_product_moderated["sku"].id),
                        "quantity": 10
                    }
                ]
            },
            headers=_invoice_headers(auth_headers)
        )
        assert invoice_resp.status_code == 201
        invoice_id = invoice_resp.json()["id"]

        # Приёмка без accepted_items (полная)
        response = client.post(
            f"/api/v1/invoices/{invoice_id}/accept",
            json={},
            headers=_accept_headers(auth_headers)
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ACCEPTED"
        assert data["items"][0]["accepted_quantity"] == 10
        
        # Проверяем, что active_quantity SKU увеличился
        db_session.refresh(test_product_moderated["sku"])
        assert test_product_moderated["sku"].active_quantity == 10

    def test_accept_invoice_partial_returns_200_and_partially_accepted(
        self, client, db_session, auth_headers, test_product_moderated
    ):
        """Частичная приёмка → PARTIALLY_ACCEPTED"""
        # Создаём накладную
        invoice_resp = client.post(
            "/api/v1/invoices/",
            json={
                "items": [
                    {
                        "sku_id": str(test_product_moderated["sku"].id),
                        "quantity": 10
                    }
                ]
            },
            headers=_invoice_headers(auth_headers)
        )
        assert invoice_resp.status_code == 201
        invoice_id = invoice_resp.json()["id"]
        invoice_item_id = invoice_resp.json()["items"][0]["id"]
        
        # Частичная приёмка
        response = client.post(
            f"/api/v1/invoices/{invoice_id}/accept",
            json={
                "accepted_items": [
                    {
                        "invoice_item_id": invoice_item_id,
                        "accepted_quantity": 7
                    }
                ]
            },
            headers=_accept_headers(auth_headers)
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "PARTIALLY_ACCEPTED"
        assert data["items"][0]["accepted_quantity"] == 7
        
        # Проверяем active_quantity
        db_session.refresh(test_product_moderated["sku"])
        assert test_product_moderated["sku"].active_quantity == 7

    def test_accept_invoice_rejected_returns_400(
        self, client, db_session, auth_headers, test_product_moderated
    ):
        """Отказ от приёмки (accepted_quantity=0) → 400 Bad Request (REJECTED удалён из спецификации)"""
        # Создаём накладную
        invoice_resp = client.post(
            "/api/v1/invoices/",
            json={
                "items": [
                    {
                        "sku_id": str(test_product_moderated["sku"].id),
                        "quantity": 10
                    }
                ]
            },
            headers=_invoice_headers(auth_headers)
        )
        assert invoice_resp.status_code == 201
        invoice_id = invoice_resp.json()["id"]
        invoice_item_id = invoice_resp.json()["items"][0]["id"]
        
        # Отказ от приёмки (все accepted_quantity = 0)
        response = client.post(
            f"/api/v1/invoices/{invoice_id}/accept",
            json={
                "accepted_items": [
                    {
                        "invoice_item_id": invoice_item_id,
                        "accepted_quantity": 0
                    }
                ]
            },
            headers=_accept_headers(auth_headers)
        )
        
        # По спецификации REJECTED не существует → 400
        assert response.status_code == 400
        error_data = response.json()
        assert error_data["code"] == "INVALID_REQUEST"
        
        # active_quantity не изменился
        db_session.refresh(test_product_moderated["sku"])
        assert test_product_moderated["sku"].active_quantity == 0

    def test_accept_invoice_not_found_returns_404(self, client, auth_headers):
        """Несуществующая накладная → 404"""
        response = client.post(
            f"/api/v1/invoices/{uuid4()}/accept",
            json={},
            headers=_accept_headers(auth_headers)
        )
        
        assert response.status_code == 404
        error_data = response.json()
        assert error_data["code"] == "NOT_FOUND"

    def test_accept_invoice_item_not_found_returns_400(
        self, client, auth_headers, test_product_moderated
    ):
        """Несуществующий invoice_item_id → 400"""
        # Создаём накладную
        invoice_resp = client.post(
            "/api/v1/invoices/",
            json={
                "items": [
                    {
                        "sku_id": str(test_product_moderated["sku"].id),
                        "quantity": 10
                    }
                ]
            },
            headers=_invoice_headers(auth_headers)
        )
        assert invoice_resp.status_code == 201
        invoice_id = invoice_resp.json()["id"]
        
        # Пробуем приёмку с несуществующим invoice_item_id
        response = client.post(
            f"/api/v1/invoices/{invoice_id}/accept",
            json={
                "accepted_items": [
                    {
                        "invoice_item_id": str(uuid4()),
                        "accepted_quantity": 5
                    }
                ]
            },
            headers=_accept_headers(auth_headers)
        )
        
        assert response.status_code == 400
        error_data = response.json()
        assert error_data["code"] == "INVALID_REQUEST"

    def test_accept_invoice_accepted_quantity_exceeds_returns_400(
        self, client, auth_headers, test_product_moderated
    ):
        """accepted_quantity > quantity → 400"""
        # Создаём накладную
        invoice_resp = client.post(
            "/api/v1/invoices/",
            json={
                "items": [
                    {
                        "sku_id": str(test_product_moderated["sku"].id),
                        "quantity": 10
                    }
                ]
            },
            headers=_invoice_headers(auth_headers)
        )
        assert invoice_resp.status_code == 201
        invoice_id = invoice_resp.json()["id"]
        invoice_item_id = invoice_resp.json()["items"][0]["id"]
        
        # Пробуем принять больше чем заявлено
        response = client.post(
            f"/api/v1/invoices/{invoice_id}/accept",
            json={
                "accepted_items": [
                    {
                        "invoice_item_id": invoice_item_id,
                        "accepted_quantity": 15
                    }
                ]
            },
            headers=_accept_headers(auth_headers)
        )
        
        assert response.status_code == 400
        error_data = response.json()
        assert error_data["code"] == "INVALID_REQUEST"


class TestB2B06CreateInvoice:
    """Тесты для создания накладной"""

    def test_create_invoice_with_moderated_sku_returns_201(
        self, client, auth_headers, test_product_moderated
    ):
        """Happy path: создание накладной с MODERATED SKU → 201"""
        response = client.post(
            "/api/v1/invoices/",
            json={
                "items": [
                    {
                        "sku_id": str(test_product_moderated["sku"].id),
                        "quantity": 10
                    }
                ]
            },
            headers=_invoice_headers(auth_headers)
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "CREATED"
        assert len(data["items"]) == 1
        assert data["items"][0]["sku_id"] == str(test_product_moderated["sku"].id)
        assert data["items"][0]["quantity"] == 10
        assert data["items"][0]["accepted_quantity"] == 0 

    def test_empty_items_returns_422(self, client, auth_headers):
        """Пустой список items → 422 Validation Error"""
        response = client.post(
            "/api/v1/invoices/",
            json={"items": []},
            headers=_invoice_headers(auth_headers)
        )

        assert response.status_code == 422
        error_data = response.json()
        assert error_data["code"] == "INVALID_REQUEST"

    def test_non_moderated_sku_returns_400(
        self, client, auth_headers, test_product_created
    ):
        """SKU товара не-MODERATED → 400"""
        response = client.post(
            "/api/v1/invoices/",
            json={
                "items": [
                    {
                        "sku_id": str(test_product_created["sku"].id),
                        "quantity": 10
                    }
                ]
            },
            headers=_invoice_headers(auth_headers)
        )

        assert response.status_code == 400
        error_data = response.json()
        assert error_data["code"] == "INVALID_REQUEST"
        assert "MODERATED" in error_data["message"]

    def test_others_sku_returns_403(
        self, client, auth_headers, test_other_seller_sku
    ):
        """SKU чужого продавца → 403"""
        response = client.post(
            "/api/v1/invoices/",
            json={
                "items": [
                    {
                        "sku_id": str(test_other_seller_sku["sku"].id),
                        "quantity": 10
                    }
                ]
            },
            headers=_invoice_headers(auth_headers)
        )

        assert response.status_code == 403
        error_data = response.json()
        assert error_data["code"] == "NOT_OWNER"

    def test_sku_not_found_returns_404(self, client, auth_headers):
        """Несуществующий SKU → 404"""
        response = client.post(
            "/api/v1/invoices/",
            json={
                "items": [
                    {
                        "sku_id": str(uuid4()),
                        "quantity": 10
                    }
                ]
            },
            headers=_invoice_headers(auth_headers)
        )

        assert response.status_code == 404
        error_data = response.json()
        assert error_data["code"] == "NOT_FOUND"

    def test_quantity_zero_returns_422(
        self, client, auth_headers, test_product_moderated
    ):
        """quantity = 0 → 422 Validation Error"""
        response = client.post(
            "/api/v1/invoices/",
            json={
                "items": [
                    {
                        "sku_id": str(test_product_moderated["sku"].id),
                        "quantity": 0
                    }
                ]
            },
            headers=_invoice_headers(auth_headers)
        )

        assert response.status_code == 422
        error_data = response.json()
        assert error_data["code"] == "INVALID_REQUEST"

    def test_quantity_negative_returns_422(
        self, client, auth_headers, test_product_moderated
    ):
        """quantity < 0 → 422 Validation Error"""
        response = client.post(
            "/api/v1/invoices/",
            json={
                "items": [
                    {
                        "sku_id": str(test_product_moderated["sku"].id),
                        "quantity": -5
                    }
                ]
            },
            headers=_invoice_headers(auth_headers)
        )

        assert response.status_code == 422
        error_data = response.json()
        assert error_data["code"] == "INVALID_REQUEST"

    def test_multiple_skus_in_one_invoice(
        self, client, auth_headers, test_product_moderated, db_session
    ):
        """Несколько SKU в одной накладной"""
        # Создаём второй MODERATED SKU
        product2 = Product(
            id=uuid4(),
            seller_id=test_product_moderated["product"].seller_id,
            category_id=test_product_moderated["product"].category_id,
            title="Product 2",
            slug="product-2",
            description="Desc",
            status=ProductStatus.MODERATED.value,
            deleted=False,
            blocked=False
        )
        db_session.add(product2)
        db_session.flush()
        
        sku2 = SKU(
            id=uuid4(),
            product_id=product2.id,
            name="SKU 2",
            price=500000,
            cost_price=300000,
            discount=0,
            image="/s3/sku2.jpg",
            stock_quantity=0,
            active_quantity=0,
            reserved_quantity=0
        )
        db_session.add(sku2)
        db_session.commit()
        
        response = client.post(
            "/api/v1/invoices/",
            json={
                "items": [
                    {"sku_id": str(test_product_moderated["sku"].id), "quantity": 10},
                    {"sku_id": str(sku2.id), "quantity": 5}
                ]
            },
            headers=_invoice_headers(auth_headers)
        )

        assert response.status_code == 201
        data = response.json()
        assert len(data["items"]) == 2
    

    def test_accept_invoice_twice_returns_409(
        self, client, db_session, auth_headers, test_product_moderated
    ):
        """Повторная приёмка уже PARTIALLY_ACCEPTED → 409 без удвоения остатков"""
        # Создаём накладную
        invoice_resp = client.post(
            "/api/v1/invoices/",
            json={"items": [{"sku_id": str(test_product_moderated["sku"].id), "quantity": 10}]},
            headers=_invoice_headers(auth_headers)
        )
        assert invoice_resp.status_code == 201
        invoice_id = invoice_resp.json()["id"]
        invoice_item_id = invoice_resp.json()["items"][0]["id"]
        
        # Первая приёмка — частичная
        resp1 = client.post(
            f"/api/v1/invoices/{invoice_id}/accept",
            json={"accepted_items": [{"invoice_item_id": invoice_item_id, "accepted_quantity": 5}]},
            headers=_accept_headers(auth_headers)
        )
        assert resp1.status_code == 200
        assert resp1.json()["status"] == "PARTIALLY_ACCEPTED"
        
        # Запоминаем active_quantity после первой приёмки
        db_session.refresh(test_product_moderated["sku"])
        active_qty_after_first = test_product_moderated["sku"].active_quantity
        assert active_qty_after_first == 5
        
        # Вторая приёмка (повторная) → 409
        resp2 = client.post(
            f"/api/v1/invoices/{invoice_id}/accept",
            json={"accepted_items": [{"invoice_item_id": invoice_item_id, "accepted_quantity": 3}]},
            headers=_accept_headers(auth_headers)
        )
        assert resp2.status_code == 409
        assert resp2.json()["code"] == "INVALID_STATE"
        
        # active_quantity НЕ увеличился повторно
        db_session.refresh(test_product_moderated["sku"])
        assert test_product_moderated["sku"].active_quantity == active_qty_after_first  # осталось 5
    

    def test_accept_other_seller_invoice_returns_404(
        self, client, db_session, auth_headers, test_other_seller_sku
    ):
        """Другой продавец пытается принять чужую накладную → 404 (из-за filter по seller_id)"""
        # Сначала создаём накладную от другого продавца
        other_auth = {"Authorization": f"Bearer {create_access_token(data={'sub': str(test_other_seller_sku['other_seller'].id)})}"}
        
        invoice_resp = client.post(
            "/api/v1/invoices/",
            json={"items": [{"sku_id": str(test_other_seller_sku["sku"].id), "quantity": 5}]},
            headers=_invoice_headers(other_auth)
        )
        assert invoice_resp.status_code == 201
        invoice_id = invoice_resp.json()["id"]
        
        # Текущий продавец пытается принять
        response = client.post(
            f"/api/v1/invoices/{invoice_id}/accept",
            json={},
            headers=_accept_headers(auth_headers)  # текущий seller, не владелец
        )
        
        # Должен быть 404, т.к. invoice не найден по (id, seller_id)
        assert response.status_code == 404
    

    def test_get_invoices_returns_paginated_list(self, client, auth_headers, test_product_moderated):
        """GET /invoices/ возвращает список накладных с пагинацией"""
        # Создаём 3 накладные
        for i in range(3):
            client.post(
                "/api/v1/invoices/",
                json={"items": [{"sku_id": str(test_product_moderated["sku"].id), "quantity": 10}]},
                headers=auth_headers
            )
        
        response = client.get(
            "/api/v1/invoices/",
            params={"limit": 2, "offset": 0},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total_count" in data
        assert data["total_count"] == 3
        assert len(data["items"]) == 2
        assert data["limit"] == 2
        assert data["offset"] == 0


    def test_get_invoices_filter_by_status(self, client, auth_headers, test_product_moderated):
        """GET /invoices/?status_filter=CREATED возвращает только CREATED накладные"""
        # Создаём накладную
        resp = client.post(
            "/api/v1/invoices/",
            json={"items": [{"sku_id": str(test_product_moderated["sku"].id), "quantity": 10}]},
            headers=auth_headers
        )
        assert resp.status_code == 201
        
        response = client.get(
            "/api/v1/invoices/",
            params={"status": "CREATED"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] >= 1
        for item in data["items"]:
            assert item["status"] == "CREATED"


    def test_get_invoice_by_id_returns_200(self, client, auth_headers, test_product_moderated):
        """GET /invoices/{id} возвращает накладную по ID"""
        # Создаём накладную
        resp = client.post(
            "/api/v1/invoices/",
            json={"items": [{"sku_id": str(test_product_moderated["sku"].id), "quantity": 10}]},
            headers=auth_headers
        )
        assert resp.status_code == 201
        invoice_id = resp.json()["id"]
        
        response = client.get(
            f"/api/v1/invoices/{invoice_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == invoice_id
        assert data["status"] == "CREATED"


    def test_get_invoice_by_id_others_returns_404(self, client, auth_headers, test_other_seller_sku):
        """Чужую накладную не видит → 404"""
        # Создаём накладную от другого продавца
        other_auth = {"Authorization": f"Bearer {create_access_token(data={'sub': str(test_other_seller_sku['other_seller'].id)})}"}
        
        resp = client.post(
            "/api/v1/invoices/",
            json={"items": [{"sku_id": str(test_other_seller_sku["sku"].id), "quantity": 5}]},
            headers=other_auth
        )
        assert resp.status_code == 201
        invoice_id = resp.json()["id"]
        
        # Текущий продавец пытается получить
        response = client.get(
            f"/api/v1/invoices/{invoice_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 404


    def test_accept_invoice_twice_returns_409(self, client, auth_headers, test_product_moderated, db_session):
        """Повторная приёмка → 409 без удвоения остатков"""
        from uuid import uuid4
        
        # Создаём накладную
        invoice_resp = client.post(
            "/api/v1/invoices/",
            json={"items": [{"sku_id": str(test_product_moderated["sku"].id), "quantity": 10}]},
            headers={**auth_headers, "Idempotency-Key": str(uuid4())}
        )
        assert invoice_resp.status_code == 201
        invoice_id = invoice_resp.json()["id"]
        invoice_item_id = invoice_resp.json()["items"][0]["id"]
        
        # Первая приёмка — частичная
        resp1 = client.post(
            f"/api/v1/invoices/{invoice_id}/accept",
            json={"accepted_items": [{"invoice_item_id": invoice_item_id, "accepted_quantity": 5}]},
            headers={**auth_headers, "Idempotency-Key": str(uuid4())}
        )
        assert resp1.status_code == 200
        assert resp1.json()["status"] == "PARTIALLY_ACCEPTED"
        
        db_session.refresh(test_product_moderated["sku"])
        active_qty_after_first = test_product_moderated["sku"].active_quantity
        assert active_qty_after_first == 5
        
        # Вторая приёмка → 409
        resp2 = client.post(
            f"/api/v1/invoices/{invoice_id}/accept",
            json={"accepted_items": [{"invoice_item_id": invoice_item_id, "accepted_quantity": 3}]},
            headers={**auth_headers, "Idempotency-Key": str(uuid4())}
        )
        assert resp2.status_code == 409
        assert resp2.json()["code"] == "INVALID_STATE"
        
        db_session.refresh(test_product_moderated["sku"])
        assert test_product_moderated["sku"].active_quantity == active_qty_after_first