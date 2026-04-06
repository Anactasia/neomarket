# b2b/tests/test_invoices.py

class TestInvoices:
    """Тесты для эндпоинтов накладных"""
    
    def test_create_invoice_success(self, client, test_seller, test_sku):
        """Успешное создание накладной"""
        response = client.post("/api/v1/invoices/", json={
            "seller_id": str(test_seller.id),
            "invoice_number": "INV-001",
            "items": [
                {"sku_id": test_sku.id, "quantity": 10}
            ]
        })
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "CREATED"
        assert len(data["items"]) == 1
    
    def test_get_invoices_list(self, client, test_seller):
        """Получение списка накладных"""
        response = client.get("/api/v1/invoices/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_invoices_by_seller(self, client, test_seller):
        """Получение накладных по продавцу"""
        response = client.get(f"/api/v1/invoices/?seller_id={test_seller.id}")
        assert response.status_code == 200
    
    def test_get_invoice_by_id(self, client, test_seller, test_sku):
        """Получение накладной по ID"""
        # Сначала создаем накладную
        create_response = client.post("/api/v1/invoices/", json={
            "seller_id": str(test_seller.id),
            "invoice_number": "INV-002",
            "items": [{"sku_id": test_sku.id, "quantity": 5}]
        })
        invoice_id = create_response.json()["id"]
        
        # Получаем по ID
        response = client.get(f"/api/v1/invoices/{invoice_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == invoice_id
    
    def test_accept_invoice(self, client, test_seller, test_sku):
        """Принятие накладной (обновление остатков)"""
        # Создаем накладную
        create_response = client.post("/api/v1/invoices/", json={
            "seller_id": str(test_seller.id),
            "invoice_number": "INV-003",
            "items": [{"sku_id": test_sku.id, "quantity": 20}]
        })
        invoice_id = create_response.json()["id"]
        
        # Получаем старый остаток
        old_sku = client.get(f"/api/v1/skus/{test_sku.id}").json()
        old_quantity = old_sku["quantity"]
        
        # Принимаем накладную
        response = client.post(f"/api/v1/invoices/{invoice_id}/accept")
        assert response.status_code == 200
        
        # Проверяем, что остаток увеличился
        new_sku = client.get(f"/api/v1/skus/{test_sku.id}").json()
        assert new_sku["quantity"] == old_quantity + 20