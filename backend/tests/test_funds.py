def test_create_fund(client):
    resp = client.post("/api/v1/funds", json={
        "code": "510300",
        "name": "沪深300ETF",
        "currency": "CNY",
        "data_source": "tushare",
        "fee_rate": 0.12,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["code"] == "510300"
    assert data["data"]["name"] == "沪深300ETF"
    assert data["data"]["is_active"] is True


def test_create_fund_duplicate_code(client):
    client.post("/api/v1/funds", json={"code": "510300", "name": "A"})
    resp = client.post("/api/v1/funds", json={"code": "510300", "name": "B"})
    assert resp.status_code == 400
    assert "已存在" in resp.json()["detail"]


def test_list_funds(client):
    client.post("/api/v1/funds", json={"code": "510300", "name": "沪深300"})
    client.post("/api/v1/funds", json={"code": "QQQ", "name": "纳斯达克100", "currency": "USD", "data_source": "yahoo"})

    resp = client.get("/api/v1/funds")
    data = resp.json()
    assert data["success"] is True
    assert len(data["data"]) == 2
    assert data["meta"]["total"] == 2


def test_list_funds_search(client):
    client.post("/api/v1/funds", json={"code": "510300", "name": "沪深300"})
    client.post("/api/v1/funds", json={"code": "QQQ", "name": "纳斯达克"})

    resp = client.get("/api/v1/funds", params={"keyword": "沪深"})
    data = resp.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["code"] == "510300"


def test_get_fund(client):
    create_resp = client.post("/api/v1/funds", json={"code": "510300", "name": "沪深300"})
    fund_id = create_resp.json()["data"]["id"]

    resp = client.get(f"/api/v1/funds/{fund_id}")
    assert resp.json()["data"]["code"] == "510300"


def test_get_fund_not_found(client):
    resp = client.get("/api/v1/funds/999")
    assert resp.status_code == 404


def test_update_fund(client):
    create_resp = client.post("/api/v1/funds", json={"code": "510300", "name": "沪深300"})
    fund_id = create_resp.json()["data"]["id"]

    resp = client.put(f"/api/v1/funds/{fund_id}", json={"name": "沪深300ETF", "fee_rate": 0.15})
    data = resp.json()
    assert data["data"]["name"] == "沪深300ETF"
    assert data["data"]["fee_rate"] == 0.15


def test_deactivate_fund(client):
    create_resp = client.post("/api/v1/funds", json={"code": "510300", "name": "沪深300"})
    fund_id = create_resp.json()["data"]["id"]

    resp = client.put(f"/api/v1/funds/{fund_id}", json={"is_active": False})
    assert resp.json()["data"]["is_active"] is False


def test_delete_fund(client):
    create_resp = client.post("/api/v1/funds", json={"code": "510300", "name": "沪深300"})
    fund_id = create_resp.json()["data"]["id"]

    resp = client.delete(f"/api/v1/funds/{fund_id}")
    assert resp.json()["data"]["deleted"] is True

    resp = client.get(f"/api/v1/funds/{fund_id}")
    assert resp.status_code == 404
