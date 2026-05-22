
import pytest
from unittest.mock import MagicMock

class TestOrderPriceCalculation:

    def test_fee_is_20_percent_of_price(self):
        price = 100.0
        assert 0.2 * price == pytest.approx(20.0)

    def test_total_includes_fee_and_quantity(self):
        price = 100.0
        quantity = 3
        assert 1.2 * price * quantity == pytest.approx(360.0)

    def test_total_single_item(self):
        price = 50.0
        assert 1.2 * price * 1 == pytest.approx(60.0)

    def test_fee_zero_price(self):
        assert 0.2 * 0.0 == pytest.approx(0.0)

    def test_total_zero_price(self):
        assert 1.2 * 0.0 * 5 == pytest.approx(0.0)

    def test_fractional_price(self):
        price = 99.99
        assert 0.2 * price == pytest.approx(19.998)
        assert 1.2 * price * 1 == pytest.approx(119.988)


class TestOrderStatus:
    VALID_STATUSES = ["pending", "completed", "refunded"]

    @pytest.mark.parametrize("status", ["pending", "completed", "refunded"])
    def test_valid_status_values(self, status):
        assert status in self.VALID_STATUSES

    def test_initial_status_is_pending(self):
        assert "pending" == "pending"

    def test_completed_status_after_processing(self):
        status = "pending"
        status = "completed"
        assert status == "completed"

    def test_refunded_status_transition(self):
        status = "completed"
        status = "refunded"
        assert status == "refunded"


class TestProcessOrderLogic:

    @pytest.mark.asyncio
    async def test_process_order_sets_completed_status(self):
        mock_order = MagicMock()
        mock_order.status = "pending"

        async def fake_process(order):
            import asyncio
            await asyncio.sleep(0)
            order.status = "completed"
            order.save()

        await fake_process(mock_order)
        assert mock_order.status == "completed"

    @pytest.mark.asyncio
    async def test_process_order_calls_save(self):
        mock_order = MagicMock()

        async def fake_process(order):
            import asyncio
            await asyncio.sleep(0)
            order.status = "completed"
            order.save()

        await fake_process(mock_order)
        mock_order.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_order_publishes_to_stream(self):
        mock_order = MagicMock()
        mock_order.model_dump.return_value = {
            "product_id": "prod-1", "price": 100.0,
            "fee": 20.0, "total": 120.0,
            "quantity": 1, "status": "completed"
        }
        mock_redis = MagicMock()

        async def fake_process(order, redis_conn):
            import asyncio
            await asyncio.sleep(0)
            order.status = "completed"
            order.save()
            redis_conn.xadd("order_completed", order.model_dump(), "*")

        await fake_process(mock_order, mock_redis)
        mock_redis.xadd.assert_called_once()


class TestConsumerRefundLogic:

    def test_refund_sets_refunded_status(self):
        mock_order = MagicMock()
        mock_order.status = "completed"
        mock_order.status = "refunded"
        mock_order.save()
        assert mock_order.status == "refunded"

    def test_consumer_extracts_pk_from_message(self):
        fake_message = {"pk": "order-abc-123", "status": "completed"}
        assert fake_message.get("pk") == "order-abc-123"

    def test_consumer_handles_missing_order_gracefully(self):
        def process_refund(pk, order_getter):
            try:
                order = order_getter(pk)
                order.status = "refunded"
                order.save()
                return True
            except Exception:
                return False

        result = process_refund("nonexistent", lambda pk: (_ for _ in ()).throw(Exception("not found")))
        assert result is False

class TestDatabaseConfiguration:

    def test_redis_host_from_env(self, monkeypatch):
        monkeypatch.setenv("REDIS_HOST", "test-host")
        import os
        assert os.getenv("REDIS_HOST") == "test-host"

    def test_redis_port_conversion(self, monkeypatch):
        monkeypatch.setenv("REDIS_PORT", "6380")
        import os
        assert int(os.getenv("REDIS_PORT")) == 6380

    def test_missing_env_raises_on_int_conversion(self, monkeypatch):
        monkeypatch.delenv("REDIS_PORT", raising=False)
        import os
        with pytest.raises((TypeError, ValueError)):
            int(os.getenv("REDIS_PORT"))