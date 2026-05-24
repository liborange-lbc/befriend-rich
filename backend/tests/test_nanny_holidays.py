"""Tests for nanny salary holiday CRUD endpoints."""
import pytest
from app.models.wechat_user import WechatUser
from app.models.nanny_salary import NannySalaryHoliday


OPENID = "test-nanny-user"
HEADERS = {"X-OpenID": OPENID}


@pytest.fixture(autouse=True)
def nanny_user(db_session):
    user = WechatUser(openid=OPENID, status="approved", permissions={"nanny": True})
    db_session.add(user)
    db_session.commit()


def test_list_holidays_empty(client):
    resp = client.get("/api/v1/nanny-salary/holidays", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_add_holiday(client):
    resp = client.post(
        "/api/v1/nanny-salary/holidays",
        headers=HEADERS,
        json={"name": "春节", "start_date": "2025-01-28", "end_date": "2025-02-04", "extra_days": 0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["id"] is not None


def test_add_holiday_with_extra_days(client):
    resp = client.post(
        "/api/v1/nanny-salary/holidays",
        headers=HEADERS,
        json={"name": "劳动节", "start_date": "2025-05-01", "end_date": "2025-05-05", "extra_days": 2},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_list_holidays_after_add(client):
    client.post(
        "/api/v1/nanny-salary/holidays",
        headers=HEADERS,
        json={"name": "国庆节", "start_date": "2025-10-01", "end_date": "2025-10-07", "extra_days": 0},
    )
    resp = client.get("/api/v1/nanny-salary/holidays", headers=HEADERS)
    assert resp.status_code == 200
    holidays = resp.json()["data"]
    assert len(holidays) == 1
    assert holidays[0]["name"] == "国庆节"


def test_update_holiday(client):
    add_resp = client.post(
        "/api/v1/nanny-salary/holidays",
        headers=HEADERS,
        json={"name": "春节", "start_date": "2025-01-28", "end_date": "2025-02-04", "extra_days": 0},
    )
    holiday_id = add_resp.json()["data"]["id"]

    update_resp = client.put(
        f"/api/v1/nanny-salary/holidays/{holiday_id}",
        headers=HEADERS,
        json={"name": "春节假期", "start_date": "2025-01-29", "end_date": "2025-02-05", "extra_days": 3},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["success"] is True

    list_resp = client.get("/api/v1/nanny-salary/holidays", headers=HEADERS)
    holidays = list_resp.json()["data"]
    assert holidays[0]["name"] == "春节假期"
    assert holidays[0]["extra_days"] == 3


def test_delete_holiday(client):
    add_resp = client.post(
        "/api/v1/nanny-salary/holidays",
        headers=HEADERS,
        json={"name": "清明节", "start_date": "2025-04-04", "end_date": "2025-04-06", "extra_days": 0},
    )
    holiday_id = add_resp.json()["data"]["id"]

    del_resp = client.delete(f"/api/v1/nanny-salary/holidays/{holiday_id}", headers=HEADERS)
    assert del_resp.status_code == 200

    list_resp = client.get("/api/v1/nanny-salary/holidays", headers=HEADERS)
    assert list_resp.json()["data"] == []


def test_add_holiday_missing_field(client):
    """Missing end_date should return 422."""
    resp = client.post(
        "/api/v1/nanny-salary/holidays",
        headers=HEADERS,
        json={"name": "春节", "start_date": "2025-01-28", "extra_days": 0},
    )
    assert resp.status_code == 422


def test_add_holiday_no_permission(client, db_session):
    """User without nanny permission should get 403."""
    db_session.add(WechatUser(openid="no-perm", status="approved", permissions={}))
    db_session.commit()
    resp = client.post(
        "/api/v1/nanny-salary/holidays",
        headers={"X-OpenID": "no-perm"},
        json={"name": "春节", "start_date": "2025-01-28", "end_date": "2025-02-04", "extra_days": 0},
    )
    assert resp.status_code == 403
