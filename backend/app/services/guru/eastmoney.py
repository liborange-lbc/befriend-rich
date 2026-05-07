"""从天天基金网（eastmoney）获取中国公募基金持仓数据。

数据来源：官方季度持仓披露（来自基金年报/季报）。
API 地址：https://fundf10.eastmoney.com/FundArchivesDatas.aspx
"""

import logging
import re
import time

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# slug → 天天基金代码（A 类主力份额）
CHINA_FUND_CODES: dict[str, str] = {
    "hua-xia-hui-bao-er-hao-hun-he": "002021",       # 华夏回报二号混合
    "fu-guo-tian-rui-qiang-shi-hun-he": "100022",     # 富国天瑞强势混合
    "yi-fang-da-zhong-xiao-pan-hun-he": "110011",     # 易方达中小盘混合
    "yi-fang-da-ke-xiang-hun-he": "110013",           # 易方达科翔混合
    "yi-fang-da-xiao-fei-xing-ye-gu-piao": "110022",  # 易方达消费行业股票
    "guo-tou-rui-yin-wen-jian-zeng-zhang-hun-he": "121006",  # 国投瑞银稳健增长混合
    "yin-he-wen-jian-hun-he": "151001",               # 银河稳健混合
    "peng-hua-jia-zhi-you-shi-hun-he": "160607",      # 鹏华价值优势混合(LOF)
    "fu-guo-tian-hui-cheng-zhang-hun-he": "161005",   # 富国天惠成长混合(LOF)A
    "tai-da-hong-li-shou-xuan-qi-ye-gu-piao": "162208",  # 泰达宏利首选企业股票
    "jing-shun-zhang-cheng-ding-yi-hun-he": "162605",  # 景顺长城鼎益混合(LOF)
    "xing-quan-qu-shi-tou-zi-hun-he": "163402",       # 兴全趋势投资混合(LOF)
    "xing-quan-he-run-hun-he": "163406",              # 兴全合润混合(LOF)A
    "tian-hong-wen-hua-xin-xing-chan-ye": "164205",   # 天弘文化新兴产业
    "zhong-ou-xin-lan-chou-hun-he": "166002",         # 中欧新蓝筹混合A
}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://fundf10.eastmoney.com/",
}


def fetch_fund_holdings(fund_code: str, top: int = 30) -> list[dict]:
    """从天天基金获取最新一期持仓前 N 大重仓股。

    Returns:
        list of dict with keys: stock_code, stock_name, weight_pct, shares, value
    """
    url = (
        f"https://fundf10.eastmoney.com/FundArchivesDatas.aspx"
        f"?type=jjcc&code={fund_code}&topline={top}&year=&month=&rt=0.123"
    )
    try:
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch holdings for {fund_code}: {e}")
        return []

    soup = BeautifulSoup(r.text, "lxml")
    table = soup.find("table")
    if not table:
        logger.warning(f"No holdings table found for {fund_code}")
        return []

    rows = table.find_all("tr")
    holdings = []
    for row in rows[1:]:  # skip header
        tds = row.find_all("td")
        if len(tds) < 9:
            continue
        holdings.append({
            "stock_code": tds[1].get_text(strip=True),
            "stock_name": tds[2].get_text(strip=True),
            "weight_pct": tds[6].get_text(strip=True),
            "shares": tds[7].get_text(strip=True),
            "value": tds[8].get_text(strip=True),
        })

    return holdings


def fetch_all_china_funds(delay: float = 0.5) -> dict[str, list[dict]]:
    """获取所有中国公募基金的最新持仓。

    Returns:
        dict: slug → holdings list
    """
    results: dict[str, list[dict]] = {}
    for slug, code in CHINA_FUND_CODES.items():
        logger.info(f"Fetching holdings for {slug} (code={code})")
        holdings = fetch_fund_holdings(code)
        if holdings:
            results[slug] = holdings
            logger.info(f"  → {len(holdings)} holdings")
        else:
            logger.warning(f"  → no holdings returned")
        time.sleep(delay)
    return results
