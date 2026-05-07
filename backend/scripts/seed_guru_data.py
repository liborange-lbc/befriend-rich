"""Read all-guru-data.json and seed the guru tables in BeFriend database."""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base, SessionLocal, engine
from app.models.guru import Guru, GuruHolding, GuruStock, GuruTrade

JSON_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "all-guru-data.json"

SKIP_SLUGS = {"aggregated-portfolio", "realtime-picks", "summary"}

CHINA_FUND_SLUGS = {
    "hua-xia-hui-bao-er-hao-hun-he",
    "fu-guo-tian-rui-qiang-shi-hun-he",
    "yi-fang-da-zhong-xiao-pan-hun-he",
    "yi-fang-da-ke-xiang-hun-he",
    "yi-fang-da-xiao-fei-xing-ye-gu-piao",
    "guo-tou-rui-yin-wen-jian-zeng-zhang-hun-he",
    "yin-he-wen-jian-hun-he",
    "peng-hua-jia-zhi-you-shi-hun-he",
    "fu-guo-tian-hui-cheng-zhang-hun-he",
    "tai-da-hong-li-shou-xuan-qi-ye-gu-piao",
    "jing-shun-zhang-cheng-ding-yi-hun-he",
    "xing-quan-qu-shi-tou-zi-hun-he",
    "xing-quan-he-run-hun-he",
    "tian-hong-wen-hua-xin-xing-chan-ye",
    "zhong-ou-xin-lan-chou-hun-he",
}

ASIA_SLUGS = {
    "duan-yongping",
    "perseverance-asset-management-international",
    "greenwoods-asset-management-hong-kong-ltd-",
    "pinpoint-asset-management-ltd",
    "hhlr-advisors-ltd-",
    "hsg-holding-ltd",
    "li-lu",
    "matthews-china-fund",
    "value-partners-group",
    "fountaincap-research-investment-hong-kong-co-ltd-",
    "taikang-asset-management-hong-kong-co-ltd",
    "tybourne-capital-management-hk-ltd",
    "myriad-asset-management-ltd-",
    "tb-alternative-assets-ltd-",
}


def classify_guru(slug: str) -> str:
    if slug in CHINA_FUND_SLUGS:
        return "china_fund"
    if slug in ASIA_SLUGS:
        return "asia"
    return "north_america"


def detect_market(code: str) -> str:
    if code.startswith("TPE:"):
        return "TW"
    if code.startswith("HKG:") or code.endswith(".HK"):
        return "HK"
    if re.match(r"^\d{6}$", code):
        return "A"
    return "US"


def parse_holding(row: list[str]) -> dict:
    n = len(row)
    if n == 14:
        return {
            "stock_code": row[0], "stock_name": row[1],
            "position_change": row[3], "trade_impact_pct": row[5],
            "shares": row[6], "value": row[7], "weight_pct": row[8],
            "ownership_pct": row[9], "sector": row[10], "market_cap": row[11],
            "return_3m_pct": row[12], "return_ytd_pct": row[13],
        }
    if n == 13:
        return {
            "stock_code": row[0], "stock_name": row[1],
            "position_change": row[3], "trade_impact_pct": row[4],
            "shares": row[5], "value": row[6], "weight_pct": row[7],
            "ownership_pct": row[8], "sector": row[9], "market_cap": row[10],
            "return_3m_pct": row[11], "return_ytd_pct": row[12],
        }
    return {
        "stock_code": row[0], "stock_name": row[1],
        "position_change": row[2], "trade_impact_pct": row[3],
        "shares": row[4], "value": row[5], "weight_pct": row[6],
        "ownership_pct": row[7], "sector": row[8], "market_cap": row[9],
        "return_3m_pct": row[10], "return_ytd_pct": row[11],
    }


def parse_trade(row: list[str]) -> dict | None:
    if len(row) < 12:
        return None
    return {
        "stock_code": row[0], "stock_name": row[1],
        "action": row[3], "shares_changed": row[6],
        "price": row[7], "value": row[11],
        "trade_date": row[4], "report_date": row[4],
        "current_shares": row[6],
    }


def main():
    print(f"Reading {JSON_PATH} ...")
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    print(f"Loaded {len(data)} entries")

    # Drop only guru-related tables, then recreate
    for table in [GuruTrade.__table__, GuruHolding.__table__, Guru.__table__, GuruStock.__table__]:
        table.drop(bind=engine, checkfirst=True)
    for table in [Guru.__table__, GuruHolding.__table__, GuruTrade.__table__, GuruStock.__table__]:
        table.create(bind=engine, checkfirst=True)

    db = SessionLocal()
    stock_map: dict[str, dict] = {}
    guru_count = holding_count = trade_count = 0

    for entry in data:
        slug = entry["slug"]
        if slug in SKIP_SLUGS:
            continue

        category = classify_guru(slug)
        profile = entry.get("profile", {})
        description = profile.get("description", "")

        guru = Guru(
            name=entry["name"], slug=slug, category=category,
            description=description,
            num_holdings=len(entry.get("holdings", [])),
            num_trades=len(entry.get("trades", [])),
        )
        db.add(guru)
        db.flush()

        for row in entry.get("holdings", []):
            if len(row) < 12:
                continue
            h = parse_holding(row)
            db.add(GuruHolding(guru_id=guru.id, **h))
            holding_count += 1
            code = h["stock_code"]
            if code and code not in stock_map:
                stock_map[code] = {
                    "name": h["stock_name"], "sector": h.get("sector", ""),
                    "market": detect_market(code), "guru_slugs": set(),
                }
            if code:
                stock_map[code]["guru_slugs"].add(slug)

        for row in entry.get("trades", []):
            t = parse_trade(row)
            if not t:
                continue
            db.add(GuruTrade(guru_id=guru.id, **t))
            trade_count += 1
            code = t["stock_code"]
            if code and code not in stock_map:
                stock_map[code] = {
                    "name": t["stock_name"], "sector": "",
                    "market": detect_market(code), "guru_slugs": set(),
                }
            if code:
                stock_map[code]["guru_slugs"].add(slug)

        guru_count += 1

    stock_count = 0
    for code, info in stock_map.items():
        db.add(GuruStock(
            code=code, name=info["name"], market=info["market"],
            sector=info["sector"], guru_count=len(info["guru_slugs"]),
        ))
        stock_count += 1

    db.commit()
    db.close()

    print(f"Seeded: {guru_count} gurus, {holding_count} holdings, "
          f"{trade_count} trades, {stock_count} stocks")


if __name__ == "__main__":
    main()
