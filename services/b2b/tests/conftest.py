import os
import sys
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.database import get_db
from app.models.base import Base
from app.models import (
    Seller, Category, Product, SKU, ProductImage,
    ProductCharacteristic, SKUCharacteristic, SKUImage,
    SKUReservation, Invoice, InvoiceItem, OutboxEvent,
    ProductStatusHistory, Characteristic, CharacteristicValue,
    CategoryCharacteristic, UnreserveOperation, FulfillOperation,
    Image, FulfillOperationItem, UnreserveOperationItem
)
from app.core.security import create_access_token

# Определяем, запущены ли тесты в CI
IN_CI = os.getenv("CI", "false").lower() == "true"
USE_POSTGRES = os.getenv("USE_POSTGRES_FOR_TESTS", "false").lower() == "true"

def get_test_engine():
    """Создаёт engine для тестовой БД"""
    if USE_POSTGRES or IN_CI:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            if IN_CI:
                database_url = "postgresql://postgres:postgres@postgres:5432/neomarket_b2b"
            else:
                database_url = "postgresql://postgres:postgres@localhost:5432/neomarket_b2b"
        print(f"Using database URL: {database_url}")
        return create_engine(database_url, poolclass=StaticPool)
    else:
        print("Using SQLite for tests")
        return create_engine(
            "sqlite:///./test.db",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )


engine = get_test_engine()
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# -------------------------
# DB setup - ПРОСТОЙ ВАРИАНТ
# -------------------------
@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Очищает таблицы в БД после тестов (создаёт Alembic)"""
    yield
    # После тестов очищаем, игнорируя ошибки
    try:
        Base.metadata.drop_all(bind=engine, checkfirst=True)
    except Exception as e:
        print(f"Ignoring cleanup error: {e}")

# -------------------------
# Transaction per test
# -------------------------
@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


# -------------------------
# Test client
# -------------------------
@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# -------------------------
# Seed categories
# -------------------------
def create_category_tree(db, data, parent_id=None, level=0):
    category = Category(
        name=data["name"],
        parent_id=parent_id,
        level=level,
        is_active=True
    )
    db.add(category)
    db.flush()
    for child in data.get("children", []):
        create_category_tree(db, child, category.id, level + 1)


@pytest.fixture
def seeded_categories(db_session):
    try:
        with open("tests/data/categories.json") as f:
            data = json.load(f)
        for root in data["categories"]:
            create_category_tree(db_session, root)
        db_session.commit()
    except FileNotFoundError:
        test_cat = Category(name="Test Category", level=0, is_active=True)
        db_session.add(test_cat)
        db_session.commit()
    return True


# -------------------------
# Fixtures
# -------------------------
@pytest.fixture
def test_seller(db_session):
    seller = Seller(
        id=uuid4(),
        email="test@example.com",
        first_name="Test",
        last_name="Seller",
        company_name="Test Company",
        inn="123456789012",
        phone="+79990000000",
        hashed_password="hashed_password_123",
        is_active=True,
        role="SELLER"
    )
    db_session.add(seller)
    db_session.commit()
    db_session.refresh(seller)
    return seller


@pytest.fixture
def test_category(db_session, seeded_categories):
    category = db_session.query(Category).first()
    if not category:
        category = Category(
            id=uuid4(),
            name="Test Category",
            slug="test-category",
            level=0,
            is_active=True
        )
        db_session.add(category)
        db_session.commit()
        db_session.refresh(category)
    return category


@pytest.fixture
def test_product(db_session, test_seller, test_category):
    product = Product(
        id=uuid4(),
        title="Test Product",
        slug="test-product",
        description="Test description",
        seller_id=test_seller.id,
        category_id=test_category.id,
        status="CREATED",
        deleted=False,
        characteristics_json=[]
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


@pytest.fixture
def test_sku(db_session, test_product):
    sku = SKU(
        id=uuid4(),
        product_id=test_product.id,
        name="Test SKU",
        price=10000,
        cost_price=8000,
        discount=0,
        stock_quantity=100,
        active_quantity=100,
        reserved_quantity=0,
        article="TEST-001"
    )
    db_session.add(sku)
    db_session.commit()
    db_session.refresh(sku)
    return sku


# -------------------------
# Auth fixtures
# -------------------------
@pytest.fixture
def auth_headers(test_seller):
    access_token = create_access_token(data={"sub": str(test_seller.id)})
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def service_key_headers():
    return {"X-Service-Key": os.getenv("B2B_TO_MOD_KEY", "test-service-key")}