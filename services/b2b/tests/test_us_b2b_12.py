"""
Тесты для US-B2B-12: Удаление SKU
"""
import os
import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch

os.environ["B2C_TO_B2B_KEY"] = "test-b2c-key"
os.environ["B2B_TO_MOD_KEY"] = "test-mod-key"
os.environ["B2C_WEBHOOK_URL"] = "http://b2c:8000/api/v1/b2b/events"
os.environ["B2B_TO_B2C_KEY"] = "test-b2b-to-b2c-key"

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
def other_auth_headers(test_other_seller):
    access_token = create_access_token(data={"sub": str(test_other_seller.id)})
    return {"Authorization": f"Bearer {access_token}"}


class TestB2B12DeleteSKU:
    """Тесты для US-B2B-12: Удаление SKU"""

    @pytest.fixture
    def test_product_with_skus(self, db_session, test_category, test_seller):
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
            active_quantity=5,
            reserved_quantity=0,
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
            stock_quantity=0,
            active_quantity=0,
            reserved_quantity=0,
            article="SKU-002"
        )
        db_session.add_all([sku1, sku2])
        db_session.commit()
        db_session.refresh(sku1)
        db_session.refresh(sku2)
        return {"product": product, "sku1": sku1, "sku2": sku2}

    @pytest.fixture
    def test_product_with_reserved_sku(self, db_session, test_category, test_seller):
        product = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Product with Reserve",
            slug="product-reserve",
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
            name="SKU with Reserve",
            price=1000000,
            cost_price=700000,
            discount=0,
            image="/s3/test.jpg",
            stock_quantity=10,
            active_quantity=5,
            reserved_quantity=3,
            article="SKU-RESERVED"
        )
        db_session.add(sku)
        db_session.commit()
        return {"product": product, "sku": sku}

    @pytest.fixture
    def test_product_on_moderation(self, db_session, test_category, test_seller):
        product = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="On Moderation Product",
            slug="on-moderation",
            description="Description",
            status=ProductStatus.ON_MODERATION.value,
            deleted=False,
            blocked=False
        )
        db_session.add(product)
        db_session.flush()
        
        sku = SKU(
            id=uuid4(),
            product_id=product.id,
            name="Last SKU",
            price=1000000,
            cost_price=700000,
            discount=0,
            image="/s3/test.jpg",
            stock_quantity=10,
            active_quantity=5,
            reserved_quantity=0,
            article="SKU-LAST"
        )
        db_session.add(sku)
        db_session.commit()
        return {"product": product, "sku": sku}

    @pytest.fixture
    def test_product_hard_blocked(self, db_session, test_category, test_seller):
        product = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Hard Blocked Product",
            slug="hard-blocked",
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
            name="SKU in Hard Blocked",
            price=1000000,
            cost_price=700000,
            discount=0,
            image="/s3/test.jpg",
            stock_quantity=10,
            active_quantity=5,
            reserved_quantity=0,
            article="SKU-HARD"
        )
        db_session.add(sku)
        db_session.commit()
        return {"product": product, "sku": sku}

    @pytest.fixture
    def test_moderated_product_with_stock(self, db_session, test_category, test_seller):
        product = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Moderated Product",
            slug="moderated-stock",
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
            name="SKU with Stock",
            price=1000000,
            cost_price=700000,
            discount=0,
            image="/s3/test.jpg",
            stock_quantity=10,
            active_quantity=5,
            reserved_quantity=0,
            article="SKU-STOCK"
        )
        db_session.add(sku)
        db_session.commit()
        return {"product": product, "sku": sku}

    # ========== ОСНОВНЫЕ ТЕСТЫ (guardrails) ==========

    def test_delete_sku_succeeds(
        self, client, auth_headers, test_product_with_skus
    ):
        """Happy path: удаление SKU успешно"""
        sku = test_product_with_skus["sku2"]
        
        response = client.delete(
            f"/api/v1/skus/{sku.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 204

    def test_delete_sku_with_active_reserves_returns_409(
        self, client, auth_headers, test_product_with_reserved_sku
    ):
        """reserved_quantity > 0 → 409"""
        sku = test_product_with_reserved_sku["sku"]
        
        response = client.delete(
            f"/api/v1/skus/{sku.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 409
        error_data = response.json()
        assert error_data["code"] == "CONFLICT"

    def test_last_sku_on_moderation_transitions_product_to_created(
        self, client, db_session, auth_headers, test_product_on_moderation
    ):
        """Последний SKU удалён + товар ON_MODERATION → товар CREATED"""
        product = test_product_on_moderation["product"]
        sku = test_product_on_moderation["sku"]
        
        assert product.status == ProductStatus.ON_MODERATION.value
        
        response = client.delete(
            f"/api/v1/skus/{sku.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 204
        
        db_session.refresh(product)
        assert product.status == ProductStatus.CREATED.value

    def test_delete_sku_hard_blocked_product_returns_403(
        self, client, auth_headers, test_product_hard_blocked
    ):
        """Товар HARD_BLOCKED → 403"""
        sku = test_product_hard_blocked["sku"]
        
        response = client.delete(
            f"/api/v1/skus/{sku.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 403
        error_data = response.json()
        assert error_data["code"] == "FORBIDDEN"

    def test_sku_not_found_returns_404(
        self, client, auth_headers
    ):
        """Несуществующий SKU → 404"""
        response = client.delete(
            f"/api/v1/skus/{uuid4()}",
            headers=auth_headers
        )
        
        assert response.status_code == 404
        error_data = response.json()
        assert error_data["code"] == "NOT_FOUND"

    def test_delete_others_sku_returns_403(
        self, client, other_auth_headers, test_product_with_skus
    ):
        """Чужой SKU → 403"""
        sku = test_product_with_skus["sku1"]
        
        response = client.delete(
            f"/api/v1/skus/{sku.id}",
            headers=other_auth_headers
        )
        
        assert response.status_code == 403
        error_data = response.json()
        assert error_data["code"] == "NOT_OWNER"

    # ========== ТЕСТЫ СОБЫТИЙ ==========

    @patch('app.api.skus.save_to_outbox')
    def test_delete_sku_sends_out_of_stock_event_when_had_stock(
        self, mock_save_to_outbox, client, auth_headers, test_moderated_product_with_stock
    ):
        """При удалении SKU с active_quantity > 0 отправляется событие SKU_OUT_OF_STOCK"""
        product = test_moderated_product_with_stock["product"]
        sku = test_moderated_product_with_stock["sku"]
        
        assert sku.active_quantity > 0
        
        response = client.delete(
            f"/api/v1/skus/{sku.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 204
        
        # Проверяем, что save_to_outbox был вызван с SKU_OUT_OF_STOCK
        out_of_stock_calls = [
            call for call in mock_save_to_outbox.call_args_list 
            if call[1].get('event_type') == 'SKU_OUT_OF_STOCK'
        ]
        assert len(out_of_stock_calls) == 1
        
        call_kwargs = out_of_stock_calls[0][1]
        assert call_kwargs['target'] == 'b2c'
        payload = call_kwargs['payload']
        assert payload['event_type'] == 'SKU_OUT_OF_STOCK'
        assert payload['payload']['sku_id'] == str(sku.id)
        assert payload['payload']['product_id'] == str(product.id)
        assert payload['payload']['reason'] == 'deleted'

    @patch('app.api.skus.save_to_outbox')
    def test_delete_sku_no_out_of_stock_event_when_no_stock(
        self, mock_save_to_outbox, client, auth_headers, test_product_with_skus
    ):
        """При удалении SKU с active_quantity = 0 НЕ отправляется SKU_OUT_OF_STOCK"""
        sku = test_product_with_skus["sku2"]
        
        assert sku.active_quantity == 0
        
        response = client.delete(
            f"/api/v1/skus/{sku.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 204
        
        out_of_stock_calls = [
            call for call in mock_save_to_outbox.call_args_list 
            if call[1].get('event_type') == 'SKU_OUT_OF_STOCK'
        ]
        assert len(out_of_stock_calls) == 0

    @patch('app.api.skus.send_event_to_moderation')
    def test_delete_last_sku_sends_product_edited_to_moderation(
        self, mock_send_event, client, db_session, auth_headers, test_product_on_moderation
    ):
        """Удаление последнего SKU товара ON_MODERATION отправляет PRODUCT_EDITED в Moderation"""
        product = test_product_on_moderation["product"]
        sku = test_product_on_moderation["sku"]
        
        response = client.delete(
            f"/api/v1/skus/{sku.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 204
        assert mock_send_event.called
        
        call_kwargs = mock_send_event.call_args[1]
        assert call_kwargs['event_type'] == 'PRODUCT_EDITED'
        assert call_kwargs['json_before']['status'] == ProductStatus.ON_MODERATION.value
        assert call_kwargs['json_after']['status'] == ProductStatus.CREATED.value

    @patch('app.api.skus.send_event_to_moderation')
    def test_delete_non_last_sku_on_moderation_sends_product_edited(
        self, mock_send_event, client, db_session, test_category, test_seller, auth_headers
    ):
        """Удаление НЕ последнего SKU товара ON_MODERATION отправляет PRODUCT_EDITED"""
        product = Product(
            id=uuid4(),
            seller_id=test_seller.id,
            category_id=test_category.id,
            title="Product with multiple SKUs",
            slug="multiple-skus",
            description="Description",
            status=ProductStatus.ON_MODERATION.value,
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
            active_quantity=5,
            reserved_quantity=0,
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
            stock_quantity=10,
            active_quantity=5,
            reserved_quantity=0,
            article="SKU-002"
        )
        db_session.add_all([sku1, sku2])
        db_session.commit()
        
        response = client.delete(
            f"/api/v1/skus/{sku2.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 204
        assert mock_send_event.called
        
        call_kwargs = mock_send_event.call_args[1]
        assert call_kwargs['event_type'] == 'PRODUCT_EDITED'