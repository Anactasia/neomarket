import sys
sys.path.insert(0, '/app')

import pytest
import json
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_db
from app.models.base import Base
from app.models import (
    Seller, Category, Product, SKU
)

SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# -------------------------
# DB setup
# -------------------------

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


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
# Seed categories (REAL DATA)
# -------------------------

def create_category_tree(db, data, parent_id=None, level=0):
    category = Category(
        name=data["name"],
        slug=data["slug"],
        parent_id=parent_id,
        level=level,
        is_restricted=data.get("is_restricted", False),
        is_active=True
    )
    db.add(category)
    db.flush()

    for child in data.get("children", []):
        create_category_tree(db, child, category.id, level + 1)


@pytest.fixture
def seeded_categories(db_session):
    with open("tests/data/categories.json") as f:
        data = json.load(f)

    for root in data["categories"]:
        create_category_tree(db_session, root)

    db_session.commit()
    return True


# -------------------------
# Fixtures (clean, predictable)
# -------------------------

@pytest.fixture
def test_seller(db_session):
    seller = Seller(
        company_name="Test Company",
        inn="123456789012",
        email="test@example.com",
        phone="+79990000000",
        status="ACTIVE"
    )
    db_session.add(seller)
    db_session.commit()
    db_session.refresh(seller)
    return seller


@pytest.fixture
def test_category(db_session, seeded_categories):
    return db_session.query(Category).first()


@pytest.fixture
def test_product(db_session, test_seller, test_category):
    product = Product(
        title="Test Product",
        slug="test-product",
        seller_id=test_seller.id,
        category_id=test_category.id,
        status="CREATED"
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


@pytest.fixture
def test_sku(db_session, test_product):
    sku = SKU(
        product_id=test_product.id,
        name="Test SKU",
        price=10000,
        quantity=100,
        reserved_quantity=0
    )
    db_session.add(sku)
    db_session.commit()
    db_session.refresh(sku)
    return sku