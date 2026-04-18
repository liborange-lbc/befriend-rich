def test_create_strategy(client):
    resp = client.post("/api/v1/strategy", json={
        "name": "沪深300定投",
        "type": "dca",
        "config": '{"buy":{"type":"dca","amount":1000,"interval":"weekly"}}',
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "沪深300定投"
    assert resp.json()["data"]["alert_enabled"] is True


def test_list_strategies(client):
    client.post("/api/v1/strategy", json={"name": "策略A", "type": "dca"})
    client.post("/api/v1/strategy", json={"name": "策略B", "type": "condition"})

    resp = client.get("/api/v1/strategy")
    assert len(resp.json()["data"]) == 2


def test_update_strategy(client):
    create_resp = client.post("/api/v1/strategy", json={"name": "策略A", "type": "dca"})
    sid = create_resp.json()["data"]["id"]

    resp = client.put(f"/api/v1/strategy/{sid}", json={"alert_enabled": False})
    assert resp.json()["data"]["alert_enabled"] is False


def test_delete_strategy(client):
    create_resp = client.post("/api/v1/strategy", json={"name": "策略A", "type": "dca"})
    sid = create_resp.json()["data"]["id"]

    resp = client.delete(f"/api/v1/strategy/{sid}")
    assert resp.json()["data"]["deleted"] is True
