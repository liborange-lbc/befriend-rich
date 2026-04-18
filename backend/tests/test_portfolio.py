def test_create_record(client):
    client.post("/api/v1/funds", json={"code": "510300", "name": "沪深300"})

    resp = client.post("/api/v1/portfolio/records", json={
        "fund_id": 1,
        "record_date": "2026-04-18",
        "amount": 50000,
        "profit": 3200,
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["amount"] == 50000


def test_create_record_dedup(client):
    client.post("/api/v1/funds", json={"code": "510300", "name": "沪深300"})

    client.post("/api/v1/portfolio/records", json={"fund_id": 1, "record_date": "2026-04-18", "amount": 50000})
    resp = client.post("/api/v1/portfolio/records", json={"fund_id": 1, "record_date": "2026-04-18", "amount": 60000})

    assert resp.json()["data"]["amount"] == 60000


def test_batch_create(client):
    client.post("/api/v1/funds", json={"code": "510300", "name": "沪深300"})
    client.post("/api/v1/funds", json={"code": "QQQ", "name": "纳斯达克", "currency": "USD", "data_source": "yahoo"})

    resp = client.post("/api/v1/portfolio/records/batch", json={
        "records": [
            {"fund_id": 1, "record_date": "2026-04-18", "amount": 50000, "profit": 3200},
            {"fund_id": 2, "record_date": "2026-04-18", "amount": 10000, "profit": 500},
        ]
    })
    assert resp.status_code == 200


def test_list_records(client):
    client.post("/api/v1/funds", json={"code": "510300", "name": "沪深300"})
    client.post("/api/v1/portfolio/records", json={"fund_id": 1, "record_date": "2026-04-11", "amount": 40000})
    client.post("/api/v1/portfolio/records", json={"fund_id": 1, "record_date": "2026-04-18", "amount": 50000})

    resp = client.get("/api/v1/portfolio/records")
    assert len(resp.json()["data"]) == 2


def test_latest_records(client):
    client.post("/api/v1/funds", json={"code": "510300", "name": "沪深300"})
    client.post("/api/v1/portfolio/records", json={"fund_id": 1, "record_date": "2026-04-11", "amount": 40000})
    client.post("/api/v1/portfolio/records", json={"fund_id": 1, "record_date": "2026-04-18", "amount": 50000})

    resp = client.get("/api/v1/portfolio/records/latest")
    data = resp.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["amount"] == 50000


def test_top5(client):
    for i in range(7):
        client.post("/api/v1/funds", json={"code": f"F{i}", "name": f"Fund {i}"})
        client.post("/api/v1/portfolio/records", json={
            "fund_id": i + 1,
            "record_date": "2026-04-18",
            "amount": (7 - i) * 10000,
        })

    resp = client.get("/api/v1/portfolio/top5")
    data = resp.json()["data"]
    assert len(data) == 5
    assert data[0]["rank"] == 1
    assert data[0]["amount_cny"] > data[4]["amount_cny"]
