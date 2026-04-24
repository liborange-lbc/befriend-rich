"""Tests for valuation metrics feature."""

from app.services.valuation_service import (
    compute_percentile,
    compute_valuation_from_kline,
    get_dca_coefficient_table,
)


class TestPercentile:
    def test_median_value(self):
        values = list(range(100))
        assert compute_percentile(values, 50) == 50.0

    def test_lowest_value(self):
        values = list(range(100))
        assert compute_percentile(values, 0) == 0.0

    def test_highest_value(self):
        values = list(range(100))
        assert compute_percentile(values, 99) == 99.0

    def test_empty_values(self):
        assert compute_percentile([], 10) == 50.0


class TestComputeValuation:
    def test_basic_valuation(self):
        # Generate 200 data points with rising PE
        kline = [
            {"date": f"2024-01-{str(i + 1).zfill(2)}", "close": 100 + i, "pe": 10 + i * 0.1}
            for i in range(200)
        ]
        result = compute_valuation_from_kline(kline)
        assert result is not None
        assert result["current_pe"] > 0
        assert 0 <= result["pe_percentile"] <= 100
        assert 0 <= result["temperature"] <= 100
        assert result["dca_coefficient"] in [0.5, 0.8, 1.0, 1.2, 1.5]
        assert result["pe_min"] <= result["pe_max"]
        assert result["data_points"] == 200

    def test_low_pe_gives_high_coefficient(self):
        # All PEs are 20, current is 10 → very low percentile
        kline = [
            {"date": f"2024-{str(i // 28 + 1).zfill(2)}-{str(i % 28 + 1).zfill(2)}", "close": 100, "pe": 20}
            for i in range(100)
        ]
        kline.append({"date": "2025-01-01", "close": 100, "pe": 10})
        result = compute_valuation_from_kline(kline)
        assert result is not None
        assert result["pe_percentile"] == 0.0  # lowest
        assert result["dca_coefficient"] == 1.5  # highest coefficient

    def test_high_pe_gives_low_coefficient(self):
        # All PEs are 10, current is 30 → very high percentile
        kline = [
            {"date": f"2024-{str(i // 28 + 1).zfill(2)}-{str(i % 28 + 1).zfill(2)}", "close": 100, "pe": 10}
            for i in range(100)
        ]
        kline.append({"date": "2025-01-01", "close": 100, "pe": 30})
        result = compute_valuation_from_kline(kline)
        assert result is not None
        assert result["pe_percentile"] > 95  # near top
        assert result["dca_coefficient"] == 0.5

    def test_insufficient_data(self):
        kline = [{"date": "2024-01-01", "close": 100, "pe": 10}] * 10
        result = compute_valuation_from_kline(kline)
        assert result is None

    def test_no_pe_data(self):
        kline = [{"date": f"2024-01-{str(i + 1).zfill(2)}", "close": 100, "pe": None} for i in range(100)]
        result = compute_valuation_from_kline(kline)
        assert result is None


class TestDCATable:
    def test_table_structure(self):
        table = get_dca_coefficient_table()
        assert len(table) == 5
        assert table[0]["coefficient"] == 1.5  # lowest temp = highest coeff
        assert table[-1]["coefficient"] == 0.5  # highest temp = lowest coeff


class TestValuationAPI:
    def test_indices_list(self, client):
        resp = client.get("/api/v1/valuation/indices")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) > 0
        assert "code" in data[0]
        assert "name" in data[0]

    def test_dca_coefficient_api(self, client):
        resp = client.get("/api/v1/valuation/dca-coefficient")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 5
