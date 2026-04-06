from app.models.category import Category

class TestCategories:

    def test_get_categories_list(self, client, seeded_categories):
        response = client.get("/api/v1/categories/")
        assert response.status_code == 200

        data = response.json()
        assert len(data) > 0

    def test_get_category_tree(self, client, seeded_categories):
        response = client.get("/api/v1/categories/tree")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        # проверим вложенность
        assert "children" in data[0]

    def test_get_restricted_category(self, client, db_session, seeded_categories):
        restricted = db_session.query(Category).filter_by(is_restricted=True).first()

        response = client.get(f"/api/v1/categories/{restricted.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["is_restricted"] is True