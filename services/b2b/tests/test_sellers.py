# b2b/tests/test_sellers.py

import pytest
from uuid import uuid4


class TestSellers:
    """Тесты для эндпоинтов продавцов"""
    
    def test_create_seller_success(self, client):
        """Успешное создание продавца"""
        response = client.post("/api/v1/sellers/", json={
            "company_name": "New Company",
            "inn": "987654321098",
            "email": "new@example.com",
            "phone": "+79998887766"
        })
        assert response.status_code == 201
        data = response.json()
        assert data["company_name"] == "New Company"
        assert data["inn"] == "987654321098"
        assert data["status"] == "PENDING"
    
    def test_create_seller_duplicate_inn(self, client, test_seller):
        """Ошибка при дубликате ИНН"""
        response = client.post("/api/v1/sellers/", json={
            "company_name": "Another Company",
            "inn": test_seller.inn,  # тот же ИНН
            "email": "another@example.com"
        })
        assert response.status_code == 400
        assert "ИНН" in response.text
    
    def test_get_sellers_list(self, client, test_seller):
        """Получение списка продавцов"""
        response = client.get("/api/v1/sellers/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["id"] == str(test_seller.id)
    
    def test_get_seller_by_id(self, client, test_seller):
        """Получение продавца по ID"""
        response = client.get(f"/api/v1/sellers/{test_seller.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["company_name"] == test_seller.company_name
    
    def test_get_seller_not_found(self, client):
        """Ошибка при несуществующем продавце"""
        fake_id = uuid4()
        response = client.get(f"/api/v1/sellers/{fake_id}")
        assert response.status_code == 404
    
    def test_update_seller(self, client, test_seller):
        """Обновление продавца"""
        response = client.put(f"/api/v1/sellers/{test_seller.id}", json={
            "company_name": "Updated Company Name"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["company_name"] == "Updated Company Name"