"""
Тесты для US-B2B-09: Обработка входящих событий от Moderation
Соответствует канон-flow «применение решения модерации» из flows/b2b-flows.md
"""
import os
import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timezone

# Устанавливаем переменные окружения ДО импорта приложения
os.environ["B2B_TO_MOD_KEY"] = "test-mod-key"
os.environ["B2C_TO_B2B_KEY"] = "test-b2c-key"
os.environ["B2B_TO_B2C_KEY"] = "test-b2c-key"

from app.main import app
from app.database import SessionLocal
from app.models.category import Category
from app.models.seller import Seller
from app.models.product import Product
from app.models.sku import SKU
from app.models.outbox import OutboxEvent
from app.schemas.product import ProductStatus
from app.core.security import create_access_token


# ========== ФИКСТУРЫ ==========

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
def service_key():
    """X-Service-Key для вызовов из Moderation"""
    return "test-mod-key"


@pytest.fixture
def test_category(db_session):
    """Тестовая категория"""
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
    """Тестовый продавец"""
    seller = Seller(
        id=uuid4(),
        email=f"test_{uuid4().hex[:12]}@example.com",
        hashed_password="hashed_password",
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
def test_product(db_session, test_category, test_seller):
    """Тестовый товар со статусом ON_MODERATION и двумя SKU"""
    product = Product(
        id=uuid4(),
        seller_id=test_seller.id,
        category_id=test_category.id,
        title="Test Product",
        slug="test-product",
        description="Description",
        status=ProductStatus.ON_MODERATION.value,
        deleted=False,
        blocked=False,
        blocking_reason_id=None,
        field_reports_json=[]
    )
    db_session.add(product)
    db_session.flush()
    
    # Создаём два SKU с остатками
    sku1 = SKU(
        id=uuid4(),
        product_id=product.id,
        name="SKU 1",
        price=1000000,
        cost_price=700000,
        discount=0,
        image="/s3/test1.jpg",
        stock_quantity=10,
        active_quantity=10,
        reserved_quantity=0
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
        active_quantity=5,
        reserved_quantity=0
    )
    db_session.add_all([sku1, sku2])
    db_session.commit()
    db_session.refresh(product)
    return product


@pytest.fixture
def test_product_with_blocking_data(db_session, test_category, test_seller):
    """Тестовый товар с уже установленными блокирующими данными"""
    product = Product(
        id=uuid4(),
        seller_id=test_seller.id,
        category_id=test_category.id,
        title="Blocked Product",
        slug="blocked-product",
        description="Blocked Description",
        status=ProductStatus.BLOCKED.value,
        deleted=False,
        blocked=True,
        blocking_reason_id=uuid4(),
        field_reports_json=[
            {"field_name": "title", "sku_id": None, "comment": "Bad title"},
            {"field_name": "description", "sku_id": None, "comment": "Misleading"}
        ]
    )
    db_session.add(product)
    db_session.commit()
    return product


@pytest.fixture
def auth_headers(test_seller):
    """JWT токен для продавца"""
    access_token = create_access_token(data={"sub": str(test_seller.id)})
    return {"Authorization": f"Bearer {access_token}"}


# ========== ТЕСТЫ ==========

class TestB2B09ModerationEvents:
    """Тесты для US-B2B-09: Обработка событий от Moderation"""

    def test_moderated_event_clears_blocking_data(
        self, client, db_session, service_key, test_product_with_blocking_data
    ):
        """
        Сценарий 1: MODERATED → товар MODERATED, blocking_reason и field_reports очищены
        """
        product = test_product_with_blocking_data
        assert product.status == "BLOCKED"
        assert product.blocking_reason_id is not None
        assert len(product.field_reports_json) > 0
        
        response = client.post(
            "/api/v1/moderation/events",
            json={
                "idempotency_key": str(uuid4()),
                "product_id": str(product.id),
                "event_type": "MODERATED",
                "occurred_at": datetime.now(timezone.utc).isoformat()
            },
            headers={"X-Service-Key": service_key}
        )
        
        assert response.status_code == 204
        
        db_session.refresh(product)
        assert product.status == "MODERATED"
        assert product.blocked is False
        assert product.blocking_reason_id is None
        assert product.field_reports_json == []

    def test_blocked_soft_saves_field_reports_and_sends_cascade(
        self, client, db_session, service_key, test_product
    ):
        """
        Сценарий 2: BLOCKED soft → статус BLOCKED, field_reports сохранены, каскад в B2C
        """
        product = test_product
        blocking_reason_id = uuid4()
        
        # Очищаем outbox перед тестом
        db_session.query(OutboxEvent).delete()
        db_session.commit()
        
        response = client.post(
            "/api/v1/moderation/events",
            json={
                "idempotency_key": str(uuid4()),
                "product_id": str(product.id),
                "event_type": "BLOCKED",
                "hard_block": False,
                "blocking_reason_id": str(blocking_reason_id),
                "moderator_comment": "Product violates rules",
                "field_reports": [
                    {
                        "field_name": "description",
                        "sku_id": None,
                        "comment": "Misleading description"
                    },
                    {
                        "field_name": "sku_image",
                        "sku_id": str(uuid4()),
                        "comment": "Wrong image"
                    }
                ],
                "occurred_at": datetime.now(timezone.utc).isoformat()
            },
            headers={"X-Service-Key": service_key}
        )
        
        assert response.status_code == 204
        
        db_session.refresh(product)
        assert product.status == "BLOCKED"
        assert product.blocked is True
        assert product.blocking_reason_id == blocking_reason_id
        assert product.moderation_comment == "Product violates rules"
        assert len(product.field_reports_json) == 2
        
        # Проверяем каскадное событие в outbox
        outbox_events = db_session.query(OutboxEvent).filter(
            OutboxEvent.event_type == "PRODUCT_BLOCKED"
        ).all()
        assert len(outbox_events) >= 1
        assert outbox_events[0].target == "b2c"

    def test_blocked_hard_sets_terminal_status_and_sends_cascade(
        self, client, db_session, service_key, test_product
    ):
        """
        Сценарий 3: BLOCKED hard → статус HARD_BLOCKED, каскад в B2C
        """
        product = test_product
        blocking_reason_id = uuid4()
        
        # Очищаем outbox перед тестом
        db_session.query(OutboxEvent).delete()
        db_session.commit()
        
        response = client.post(
            "/api/v1/moderation/events",
            json={
                "idempotency_key": str(uuid4()),
                "product_id": str(product.id),
                "event_type": "BLOCKED",
                "hard_block": True,
                "blocking_reason_id": str(blocking_reason_id),
                "moderator_comment": "Fraudulent product",
                "occurred_at": datetime.now(timezone.utc).isoformat()
            },
            headers={"X-Service-Key": service_key}
        )
        
        assert response.status_code == 204
        
        db_session.refresh(product)
        assert product.status == "HARD_BLOCKED"
        assert product.blocked is True
        assert product.blocking_reason_id == blocking_reason_id
        
        # Проверяем каскадное событие в outbox (PRODUCT_HARD_BLOCKED)
        outbox_events = db_session.query(OutboxEvent).filter(
            OutboxEvent.event_type == "PRODUCT_HARD_BLOCKED"
        ).all()
        assert len(outbox_events) >= 1
        assert outbox_events[0].target == "b2c"

    def test_hard_blocked_product_rejects_seller_edits(
        self, client, auth_headers, db_session, service_key, test_product
    ):
        """
        Сценарий 4: HARD_BLOCKED товар → PUT/PATCH/DELETE от продавца → 403
        """
        product = test_product
        blocking_reason_id = uuid4()
        
        # Сначала делаем товар HARD_BLOCKED через модерацию
        client.post(
            "/api/v1/moderation/events",
            json={
                "idempotency_key": str(uuid4()),
                "product_id": str(product.id),
                "event_type": "BLOCKED",
                "hard_block": True,
                "blocking_reason_id": str(blocking_reason_id),
                "occurred_at": datetime.now(timezone.utc).isoformat()
            },
            headers={"X-Service-Key": service_key}
        )
        
        db_session.refresh(product)
        assert product.status == "HARD_BLOCKED"
        
        # Пытаемся отредактировать (PATCH)
        response_patch = client.patch(
            f"/api/v1/products/{product.id}",
            json={"title": "New Title"},
            headers=auth_headers
        )
        assert response_patch.status_code == 403
        error_data = response_patch.json()
        assert error_data["code"] == "FORBIDDEN"
        
        # Пытаемся удалить (DELETE)
        response_delete = client.delete(
            f"/api/v1/products/{product.id}",
            headers=auth_headers
        )
        assert response_delete.status_code == 403

    def test_duplicate_event_same_idempotency_key_no_side_effects(
        self, client, db_session, service_key, test_product
    ):
        """
        Сценарий 5: повторное событие с тем же idempotency_key → 204 без изменений
        """
        product = test_product
        idempotency_key = str(uuid4())
        blocking_reason_id = uuid4()
        
        # Первый запрос
        response1 = client.post(
            "/api/v1/moderation/events",
            json={
                "idempotency_key": idempotency_key,
                "product_id": str(product.id),
                "event_type": "BLOCKED",
                "hard_block": False,
                "blocking_reason_id": str(blocking_reason_id),
                "moderator_comment": "Blocked",
                "occurred_at": datetime.now(timezone.utc).isoformat()
            },
            headers={"X-Service-Key": service_key}
        )
        assert response1.status_code == 204
        
        # Сохраняем состояние после первого запроса
        db_session.refresh(product)
        assert product.status == "BLOCKED"
        
        # Второй запрос с тем же ключом (пытаемся одобрить, но идемпотентность должна сработать)
        response2 = client.post(
            "/api/v1/moderation/events",
            json={
                "idempotency_key": idempotency_key,
                "product_id": str(product.id),
                "event_type": "MODERATED",  # Другой статус, но игнорируется
                "occurred_at": datetime.now(timezone.utc).isoformat()
            },
            headers={"X-Service-Key": service_key}
        )
        assert response2.status_code == 204
        
        # Статус не изменился (остался BLOCKED)
        db_session.refresh(product)
        assert product.status == "BLOCKED"  # Не MODERATED

    def test_missing_service_key_returns_401(self, client):
        """
        Сценарий 6: отсутствует X-Service-Key → 401
        """
        response = client.post(
            "/api/v1/moderation/events",
            json={
                "idempotency_key": str(uuid4()),
                "product_id": str(uuid4()),
                "event_type": "MODERATED",
                "occurred_at": datetime.now(timezone.utc).isoformat()
            }
        )
        assert response.status_code == 401
        error_data = response.json()
        assert error_data["code"] == "UNAUTHORIZED"

    def test_product_not_found_returns_404(self, client, service_key):
        """
        Сценарий 7: несуществующий product_id → 404
        """
        response = client.post(
            "/api/v1/moderation/events",
            json={
                "idempotency_key": str(uuid4()),
                "product_id": str(uuid4()),
                "event_type": "MODERATED",
                "occurred_at": datetime.now(timezone.utc).isoformat()
            },
            headers={"X-Service-Key": service_key}
        )
        assert response.status_code == 404
        error_data = response.json()
        assert error_data["code"] == "NOT_FOUND"

    def test_invalid_service_key_returns_401(self, client):
        """
        Сценарий 8: неверный X-Service-Key → 401
        """
        response = client.post(
            "/api/v1/moderation/events",
            json={
                "idempotency_key": str(uuid4()),
                "product_id": str(uuid4()),
                "event_type": "MODERATED",
                "occurred_at": datetime.now(timezone.utc).isoformat()
            },
            headers={"X-Service-Key": "wrong-key"}
        )
        assert response.status_code == 401
        error_data = response.json()
        assert error_data["code"] == "UNAUTHORIZED"