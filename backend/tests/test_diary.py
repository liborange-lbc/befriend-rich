"""Tests for investment diary feature."""

from datetime import date


class TestDiaryCRUD:
    def test_create_entry(self, client, db_session):
        resp = client.post("/api/v1/diary", json={
            "entry_date": date.today().isoformat(),
            "title": "加仓沪深300",
            "content": "市场恐慌，偏离度-10%以下，加倍定投。",
            "mood": "bullish",
            "tags": ["定投", "加仓"],
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["title"] == "加仓沪深300"
        assert data["mood"] == "bullish"
        assert data["tags"] == ["定投", "加仓"]

    def test_list_entries(self, client, db_session):
        client.post("/api/v1/diary", json={"entry_date": "2024-01-01", "title": "Test 1"})
        client.post("/api/v1/diary", json={"entry_date": "2024-01-02", "title": "Test 2"})

        resp = client.get("/api/v1/diary")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        # Sorted by date desc
        assert data[0]["entry_date"] == "2024-01-02"

    def test_list_with_keyword(self, client, db_session):
        client.post("/api/v1/diary", json={"entry_date": "2024-01-01", "title": "加仓", "content": "沪深300"})
        client.post("/api/v1/diary", json={"entry_date": "2024-01-02", "title": "减仓", "content": "中证500"})

        resp = client.get("/api/v1/diary", params={"keyword": "沪深"})
        data = resp.json()["data"]
        assert len(data) == 1

    def test_update_entry(self, client, db_session):
        create = client.post("/api/v1/diary", json={"entry_date": "2024-01-01", "title": "原标题"})
        entry_id = create.json()["data"]["id"]

        resp = client.put(f"/api/v1/diary/{entry_id}", json={"title": "新标题", "mood": "bearish"})
        assert resp.status_code == 200
        assert resp.json()["data"]["title"] == "新标题"
        assert resp.json()["data"]["mood"] == "bearish"

    def test_delete_entry(self, client, db_session):
        create = client.post("/api/v1/diary", json={"entry_date": "2024-01-01", "title": "删除测试"})
        entry_id = create.json()["data"]["id"]

        resp = client.delete(f"/api/v1/diary/{entry_id}")
        assert resp.status_code == 200

        # Verify deleted
        resp = client.get("/api/v1/diary")
        assert len(resp.json()["data"]) == 0

    def test_delete_nonexistent(self, client, db_session):
        resp = client.delete("/api/v1/diary/999")
        assert resp.status_code == 404
