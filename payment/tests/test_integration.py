import pytest
import os
import redis as redis_lib


@pytest.fixture(scope="session")
def redis_client():
    client = redis_lib.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        password=os.getenv("REDIS_PASSWORD", None),
        decode_responses=True
    )
    client.ping()
    yield client
    client.close()


class TestRedisConnection:

    def test_ping(self, redis_client):
        assert redis_client.ping() is True

    def test_set_and_get(self, redis_client):
        redis_client.set("test:key", "hello")
        value = redis_client.get("test:key")
        assert value == "hello"
        redis_client.delete("test:key")

    def test_delete_key(self, redis_client):
        redis_client.set("test:del", "value")
        redis_client.delete("test:del")
        assert redis_client.get("test:del") is None


class TestRedisStream:

    def test_xadd_and_xread(self, redis_client):
        stream_key = "test:stream:orders"
        redis_client.delete(stream_key)

        msg_id = redis_client.xadd(stream_key, {
            "product_id": "prod-1",
            "price": "100.0",
            "status": "completed"
        })
        assert msg_id is not None

        messages = redis_client.xread({stream_key: "0-0"}, count=1)
        assert len(messages) == 1
        data = messages[0][1][0][1]
        assert data["product_id"] == "prod-1"
        assert data["status"] == "completed"

        redis_client.delete(stream_key)

    def test_consumer_group_creation(self, redis_client):
        stream_key = "test:stream:refund"
        group_name = "test-group"
        redis_client.delete(stream_key)

        redis_client.xgroup_create(stream_key, group_name, mkstream=True)
        groups = redis_client.xinfo_groups(stream_key)
        group_names = [g["name"] for g in groups]
        assert group_name in group_names

        redis_client.delete(stream_key)

    def test_xreadgroup(self, redis_client):
        stream_key = "test:stream:refund2"
        group_name = "test-group2"
        redis_client.delete(stream_key)

        redis_client.xgroup_create(stream_key, group_name, mkstream=True)
        redis_client.xadd(stream_key, {"pk": "order-xyz"})

        results = redis_client.xreadgroup(
            group_name, "consumer-1", {stream_key: ">"}, count=1
        )
        assert len(results) == 1
        data = results[0][1][0][1]
        assert data["pk"] == "order-xyz"

        redis_client.delete(stream_key)


class TestRedisHashOperations:

    def test_hset_and_hget(self, redis_client):
        key = "test:hash:order-1"
        redis_client.delete(key)
        redis_client.hset(key, mapping={
            "product_id": "prod-1",
            "price": "100.0",
            "status": "pending"
        })
        assert redis_client.hget(key, "status") == "pending"
        redis_client.delete(key)

    def test_hset_update_status(self, redis_client):
        key = "test:hash:order-2"
        redis_client.delete(key)
        redis_client.hset(key, mapping={"status": "pending"})
        redis_client.hset(key, "status", "completed")
        assert redis_client.hget(key, "status") == "completed"
        redis_client.delete(key)