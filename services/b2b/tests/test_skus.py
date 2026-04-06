# b2b/tests/test_skus.py

class TestSKUs:
    """Тесты для эндпоинтов SKU"""
    
    def test_create_sku_success(self, client, test_product):
        """Успешное создание SKU"""
        response = client.post("/api/v1/skus/", json={
            "product_id": test_product.id,
            "name": "256GB Black",
            "price": 9990000,
            "quantity": 50
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "256GB Black"
        assert data["price"] == 9990000
        assert data["quantity"] == 50
    
    def test_create_sku_invalid_product(self, client):
        """Ошибка при несуществующем товаре"""
        response = client.post("/api/v1/skus/", json={
            "product_id": 99999,
            "name": "Test SKU",
            "price": 10000
        })
        assert response.status_code == 404
    
    def test_get_skus_list(self, client, test_sku):
        """Получение списка SKU"""
        response = client.get("/api/v1/skus/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
    
    def test_get_skus_by_product(self, client, test_product, test_sku):
        """Получение SKU по товару"""
        response = client.get(f"/api/v1/skus/?product_id={test_product.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["product_id"] == test_product.id
    
    def test_get_sku_by_id(self, client, test_sku):
        """Получение SKU по ID"""
        response = client.get(f"/api/v1/skus/{test_sku.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == test_sku.name
    
    def test_update_sku(self, client, test_sku):
        """Обновление SKU"""
        response = client.put(f"/api/v1/skus/{test_sku.id}", json={
            "price": 15000,
            "name": "Updated SKU Name"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["price"] == 15000
        assert data["name"] == "Updated SKU Name"
    
    def test_update_sku_quantity(self, client, test_sku):
        """Обновление остатка SKU"""
        response = client.put(f"/api/v1/skus/{test_sku.id}/quantity", 
                              params={"quantity": 75})
        assert response.status_code == 200
        data = response.json()
        assert data["quantity"] == 75
    
    def test_delete_sku(self, client, test_sku):
        """Удаление SKU"""
        response = client.delete(f"/api/v1/skus/{test_sku.id}")
        assert response.status_code == 204