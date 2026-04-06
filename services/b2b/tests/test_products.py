# b2b/tests/test_products.py

class TestProducts:
    """Тесты для эндпоинтов товаров"""
    
    def test_create_product_success(self, client, test_seller, test_category):
        """Успешное создание товара"""
        response = client.post("/api/v1/products/", json={
            "title": "New Product",
            "slug": "new-product",
            "category_id": test_category.id,
            "seller_id": str(test_seller.id),
            "description": "Test description"
        })
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "New Product"
        assert data["status"] == "CREATED"
    
    def test_create_product_duplicate_slug(self, client, test_product):
        """Ошибка при дубликате slug"""
        response = client.post("/api/v1/products/", json={
            "title": "Another Product",
            "slug": test_product.slug,  # тот же slug
            "category_id": test_product.category_id,
            "seller_id": str(test_product.seller_id)
        })
        assert response.status_code == 400
    
    def test_create_product_invalid_category(self, client, test_seller):
        """Ошибка при несуществующей категории"""
        response = client.post("/api/v1/products/", json={
            "title": "Invalid Product",
            "slug": "invalid-product",
            "category_id": 99999,  # не существует
            "seller_id": str(test_seller.id)
        })
        assert response.status_code == 404
    
    def test_get_products_list(self, client, test_product):
        """Получение списка товаров"""
        response = client.get("/api/v1/products/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
    
    def test_get_products_with_filters(self, client, test_product, test_seller):
        """Получение товаров с фильтрацией"""
        response = client.get(f"/api/v1/products/?seller_id={test_seller.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["seller_id"] == str(test_seller.id)
    
    def test_get_product_by_id(self, client, test_product):
        """Получение товара по ID"""
        response = client.get(f"/api/v1/products/{test_product.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == test_product.title
    
    def test_get_product_not_found(self, client):
        """Ошибка при несуществующем товаре"""
        response = client.get("/api/v1/products/99999")
        assert response.status_code == 404
    
    def test_update_product(self, client, test_product):
        """Обновление товара"""
        response = client.put(f"/api/v1/products/{test_product.id}", json={
            "title": "Updated Product Title"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Product Title"
        # При обновлении статус должен стать ON_MODERATION
        assert data["status"] == "ON_MODERATION"
    
    def test_delete_product(self, client, test_product):
        """Удаление товара"""
        response = client.delete(f"/api/v1/products/{test_product.id}")
        assert response.status_code == 204
    
    def test_product_validation_error(self, client, test_seller, test_category):
        """Ошибка валидации при создании товара"""
        response = client.post("/api/v1/products/", json={
            "title": "A",  # слишком короткое
            "slug": "Invalid Slug!",  # недопустимые символы
            "category_id": 0,  # невалидный ID
            "seller_id": str(test_seller.id)
        })
        assert response.status_code == 422  # Validation error