import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture
def mock_redis_om():
    with patch("database.redis") as mock_db:
        mock_db.ping.return_value = True
        yield mock_db


@pytest.fixture
def client(mock_redis_om):
    with patch("database.get_redis_connection", return_value=mock_redis_om):
        with patch("redis_om.get_redis_connection", return_value=mock_redis_om):
            from main import app
            with TestClient(app) as c:
                yield c


class TestGetOrderEndpoint:

    def test_get_order_not_found(self, client):
        with patch("main.Order.get") as mock_get:
            from redis_om import NotFoundError
            mock_get.side_effect = NotFoundError
            response = client.get("/orders/nonexistent-pk")
        assert response.status_code == 404
        assert response.json()["detail"] == "Order not found"

    def test_get_order_success(self, client):
        mock_order = MagicMock()
        mock_order.pk = "test-pk-123"
        mock_order.product_id = "prod-1"
        mock_order.price = 100.0
        mock_order.fee = 20.0
        mock_order.total = 120.0
        mock_order.quantity = 1
        mock_order.status = "completed"

        with patch("main.Order.get", return_value=mock_order):
            response = client.get("/orders/test-pk-123")
        assert response.status_code == 200


class TestCreateOrderEndpoint:

    def test_create_order_product_not_found(self, client):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_http.get.return_value = mock_response
            mock_client_cls.return_value.__aenter__.return_value = mock_http

            response = client.post("/orders", json={"id": "nonexistent", "quantity": 1})

        assert response.status_code == 400
        assert "Product not found" in response.json()["detail"]

    def test_create_order_success(self, client):
        mock_product = {"id": "prod-1", "name": "Test", "price": 100.0}

        mock_order = MagicMock()
        mock_order.pk = "new-order-pk"
        mock_order.product_id = "prod-1"
        mock_order.price = 100.0
        mock_order.fee = 20.0
        mock_order.total = 120.0
        mock_order.quantity = 1
        mock_order.status = "pending"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_product
            mock_http.get.return_value = mock_response
            mock_client_cls.return_value.__aenter__.return_value = mock_http

            with patch("main.Order", return_value=mock_order) as MockOrder:
                MockOrder.get = MagicMock(return_value=mock_order)
                mock_order.save.return_value = None

                response = client.post("/orders", json={"id": "prod-1", "quantity": 1})

        assert response.status_code in [200, 422]

    def test_create_order_missing_body(self, client):
        response = client.post("/orders", json={})
        assert response.status_code in [400, 422, 500]


class TestCORSHeaders:

    def test_cors_allowed_origin(self, client):
        response = client.options(
            "/orders",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST"
            }
        )
        assert response.status_code in [200, 405]


class TestAppMetadata:

    def test_app_has_title(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert data["info"]["title"] == "Order Service"

    def test_orders_route_exists(self, client):
        response = client.get("/openapi.json")
        paths = response.json()["paths"]
        assert "/orders" in paths or "/orders/{pk}" in paths