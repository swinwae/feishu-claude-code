from fastapi.testclient import TestClient

from console import server


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


def test_config_endpoint_never_leaks_secret(monkeypatch):
    monkeypatch.setattr(server, "read_bot_config",
                        lambda bot: {"FEISHU_APP_SECRET": "****abcd", "DEFAULT_MODEL": "m"})
    client = TestClient(server.app)
    r = client.get("/api/config")
    assert r.status_code == 200
    assert "****abcd" in r.text
    # 明文不应出现
    assert "supersecret" not in r.text
