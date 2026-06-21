import asyncio

from fastapi.testclient import TestClient

from console import server
from console.security import is_sensitive


def test_health_endpoint(monkeypatch):
    fake = [{"name": "bot1", "alive": True, "pid": "1", "version": "abc",
             "dirty": False, "last_good": "", "started": "", "label": "l"}]
    monkeypatch.setattr(server, "collect_health", lambda: fake)
    client = TestClient(server.app)
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["bots"][0]["name"] == "bot1"


def test_promote_rejects_empty_message():
    client = TestClient(server.app)
    r = client.post("/api/promote", json={"message": ""})
    assert r.status_code == 400


def test_config_endpoint_never_leaks_secret():
    # 不 mock read_bot_config，走真实的读配置 + 脱敏链路，
    # 证明真实链路确实脱敏，而不是只验证“mock 出来的已脱敏值”。
    client = TestClient(server.app)
    r = client.get("/api/config")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    for bot_name, cfg in body["configs"].items():
        for key, value in cfg.items():
            if not is_sensitive(key):
                continue
            # 敏感 key 的值必须是脱敏形态：以 **** 开头，或本身极短（全打码）
            assert value == "" or value.startswith("****") or len(value) <= 4, (
                f"{bot_name}.{key} 疑似明文外泄：{value!r}"
            )


def test_run_publish_returns_409_when_already_locked():
    # 直接对 _run_publish 做单测：第一次调用后锁应处于已获取状态，
    # 第二次调用（在第一个流被消费完之前）必须立刻拿到 409，
    # 这才能证明“检测锁”与“获取锁”之间没有竞态窗口。
    async def run():
        first = await server._run_publish(["true"])
        try:
            assert server.publish_lock.locked() is True
            second = await server._run_publish(["true"])
            assert second.status_code == 409
        finally:
            # 清理：把第一个流跑完以释放锁，避免污染其它测试
            async for _ in first.body_iterator:
                pass
            assert server.publish_lock.locked() is False

    asyncio.run(run())


def test_logs_stream_unknown_bot_returns_404():
    client = TestClient(server.app)
    r = client.get("/api/logs/stream", params={"bot": "unknown"})
    assert r.status_code == 404
