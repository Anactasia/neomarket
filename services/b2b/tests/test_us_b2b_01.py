"""
Тесты для US-B2B-01: Создание карточки товара
"""
import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import get_db
from app.models.category import Category
from app.models.seller import Seller
from app.core.security import get_password_hash


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
        hashed_password=get_password_hash("123456"),
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
    from app.core.security import create_access_token
    
    access_token = create_access_token(data={"sub": str(test_seller.id)})
    return {"Authorization": f"Bearer {access_token}"}


class TestB2B01CreateProduct:
    """Тесты для US-B2B-01: Создание карточки товара"""
    
    def test_create_product_returns_201_with_created_status(self, client, auth_headers, test_category):
        """Сценарий 1: товар создаётся со статусом CREATED и пустым skus"""
        response = client.post("/api/v1/products/", json={
            "title": "iPhone 15 Pro Max",
            "description": "Флагманский смартфон Apple 2024 года",
            "category_id": str(test_category.id),
            "images": [
                {"url": "/s3/iphone15-front.jpg", "ordering": 0},
                {"url": "/s3/iphone15-back.jpg", "ordering": 1}
            ],
            "characteristics": [
                {"name": "Бренд", "value": "Apple"}
            ]
        }, headers=auth_headers)
        
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "CREATED"
        assert data["skus"] == []
        assert "id" in data
        # Проверка обязательных полей ProductResponse (обновлённые названия)
        assert "slug" in data
        assert "deleted" in data
        assert "blocked" in data  # ← изменено с blocking_reason_id
        assert "blocking_reason" in data  # ← добавлено
        assert "moderator_comment" in data
    
    def test_seller_id_taken_from_jwt(self, client, auth_headers, test_category, test_seller):
        """Сценарий 2: seller_id берётся из JWT, а не из тела запроса"""
        response = client.post("/api/v1/products/", json={
            "title": "Test Product",
            "description": "Test Description",
            "category_id": str(test_category.id),
            "images": [{"url": "/s3/test.jpg", "ordering": 0}]
        }, headers=auth_headers)
        
        assert response.status_code == 201
        product_id = response.json()["id"]
        
        # Получаем товар и проверяем seller_id
        get_response = client.get(f"/api/v1/products/{product_id}", headers=auth_headers)
        assert get_response.status_code == 200
        assert get_response.json()["seller_id"] == str(test_seller.id)
    
    def test_missing_images_returns_400(self, client, auth_headers, test_category):
        """Сценарий 3: отсутствие images -> 400 Bad Request"""
        response = client.post("/api/v1/products/", json={
            "title": "Test Product",
            "description": "Test Description",
            "category_id": str(test_category.id),
            "images": []  # пустой массив
        }, headers=auth_headers)
        
        assert response.status_code == 400
    
    def test_missing_category_returns_400(self, client, auth_headers):
        """Сценарий 4: отсутствие category_id -> 400 Bad Request"""
        response = client.post("/api/v1/products/", json={
            "title": "Test Product",
            "description": "Test Description",
            "images": [{"url": "/s3/test.jpg", "ordering": 0}]
            # category_id отсутствует
        }, headers=auth_headers)
        
        assert response.status_code == 400
    
    def test_invalid_category_id_returns_400(self, client, auth_headers):
        """Сценарий 5: несуществующая категория -> 400 Bad Request"""
        response = client.post("/api/v1/products/", json={
            "title": "Test Product",
            "description": "Test Description",
            "category_id": str(uuid4()),
            "images": [{"url": "/s3/test.jpg", "ordering": 0}]
        }, headers=auth_headers)
        
        assert response.status_code == 400
        error_data = response.json()
        # Проверяем flat-формат ошибки
        assert error_data["code"] == "INVALID_REQUEST" or "Category not found" in str(error_data)
    
    def test_title_too_long_returns_400(self, client, auth_headers, test_category):
        """Сценарий 6: title длиннее 255 символов -> 400 Bad Request"""
        response = client.post("/api/v1/products/", json={
            "title": "A" * 256,
            "description": "Test Description",
            "category_id": str(test_category.id),
            "images": [{"url": "/s3/test.jpg", "ordering": 0}]
        }, headers=auth_headers)
        
        assert response.status_code == 400
    
    def test_product_not_sent_to_moderation_without_skus(self, client, auth_headers, test_category):
        """Инвариант B2B-1: товар без SKU остаётся в статусе CREATED, не ON_MODERATION"""
        response = client.post("/api/v1/products/", json={
            "title": "Test Product No SKU",
            "description": "Test Description",
            "category_id": str(test_category.id),
            "images": [{"url": "/s3/test.jpg", "ordering": 0}]
        }, headers=auth_headers)
        
        assert response.status_code == 201
        data = response.json()
        
        # Статус должен быть CREATED, а не ON_MODERATION
        assert data["status"] == "CREATED"
        
        # SKU должен быть пустым
        assert data["skus"] == []
        
        # Проверка через GET
        product_id = data["id"]
        get_response = client.get(f"/api/v1/products/{product_id}", headers=auth_headers)
        assert get_response.status_code == 200
        assert get_response.json()["status"] == "CREATED"