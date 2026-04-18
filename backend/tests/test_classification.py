def test_create_model(client):
    resp = client.post("/api/v1/classification/models", json={"name": "良田模型", "description": "粮食作物和经济作物"})
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "良田模型"


def test_create_model_duplicate(client):
    client.post("/api/v1/classification/models", json={"name": "良田模型"})
    resp = client.post("/api/v1/classification/models", json={"name": "良田模型"})
    assert resp.status_code == 400


def test_list_models(client):
    client.post("/api/v1/classification/models", json={"name": "良田模型"})
    client.post("/api/v1/classification/models", json={"name": "股债模型"})
    resp = client.get("/api/v1/classification/models")
    assert len(resp.json()["data"]) == 2


def test_create_category(client):
    model_resp = client.post("/api/v1/classification/models", json={"name": "良田模型"})
    model_id = model_resp.json()["data"]["id"]

    resp = client.post("/api/v1/classification/categories", json={"model_id": model_id, "name": "粮食作物"})
    assert resp.json()["data"]["name"] == "粮食作物"
    assert resp.json()["data"]["level"] == 1


def test_create_subcategory(client):
    model_resp = client.post("/api/v1/classification/models", json={"name": "良田模型"})
    model_id = model_resp.json()["data"]["id"]

    parent_resp = client.post("/api/v1/classification/categories", json={"model_id": model_id, "name": "粮食作物"})
    parent_id = parent_resp.json()["data"]["id"]

    resp = client.post("/api/v1/classification/categories", json={"model_id": model_id, "parent_id": parent_id, "name": "中国宽基"})
    assert resp.json()["data"]["level"] == 2
    assert resp.json()["data"]["parent_id"] == parent_id


def test_category_tree(client):
    model_resp = client.post("/api/v1/classification/models", json={"name": "良田模型"})
    model_id = model_resp.json()["data"]["id"]

    parent_resp = client.post("/api/v1/classification/categories", json={"model_id": model_id, "name": "粮食作物"})
    parent_id = parent_resp.json()["data"]["id"]
    client.post("/api/v1/classification/categories", json={"model_id": model_id, "parent_id": parent_id, "name": "中国宽基"})

    resp = client.get("/api/v1/classification/categories/tree", params={"model_id": model_id})
    tree = resp.json()["data"]
    assert len(tree) == 1
    assert tree[0]["name"] == "粮食作物"
    assert len(tree[0]["children"]) == 1
    assert tree[0]["children"][0]["name"] == "中国宽基"


def test_fund_mapping(client):
    fund_resp = client.post("/api/v1/funds", json={"code": "510300", "name": "沪深300"})
    fund_id = fund_resp.json()["data"]["id"]

    model_resp = client.post("/api/v1/classification/models", json={"name": "良田模型"})
    model_id = model_resp.json()["data"]["id"]

    cat_resp = client.post("/api/v1/classification/categories", json={"model_id": model_id, "name": "粮食作物"})
    cat_id = cat_resp.json()["data"]["id"]

    resp = client.post("/api/v1/classification/mappings", json={"fund_id": fund_id, "category_id": cat_id, "model_id": model_id})
    assert resp.json()["data"]["fund_id"] == fund_id


def test_fund_mapping_replace_same_model(client):
    fund_resp = client.post("/api/v1/funds", json={"code": "510300", "name": "沪深300"})
    fund_id = fund_resp.json()["data"]["id"]

    model_resp = client.post("/api/v1/classification/models", json={"name": "良田模型"})
    model_id = model_resp.json()["data"]["id"]

    cat1 = client.post("/api/v1/classification/categories", json={"model_id": model_id, "name": "粮食作物"}).json()["data"]["id"]
    cat2 = client.post("/api/v1/classification/categories", json={"model_id": model_id, "name": "经济作物"}).json()["data"]["id"]

    client.post("/api/v1/classification/mappings", json={"fund_id": fund_id, "category_id": cat1, "model_id": model_id})
    client.post("/api/v1/classification/mappings", json={"fund_id": fund_id, "category_id": cat2, "model_id": model_id})

    resp = client.get("/api/v1/classification/mappings", params={"fund_id": fund_id, "model_id": model_id})
    mappings = resp.json()["data"]
    assert len(mappings) == 1
    assert mappings[0]["category_id"] == cat2


def test_delete_model_cascades(client):
    model_resp = client.post("/api/v1/classification/models", json={"name": "良田模型"})
    model_id = model_resp.json()["data"]["id"]
    client.post("/api/v1/classification/categories", json={"model_id": model_id, "name": "粮食作物"})

    client.delete(f"/api/v1/classification/models/{model_id}")

    resp = client.get("/api/v1/classification/categories", params={"model_id": model_id})
    assert len(resp.json()["data"]) == 0
