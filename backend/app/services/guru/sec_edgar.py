"""从 SEC EDGAR 获取 13F 机构持仓数据。

数据来源：美国证券交易委员会（SEC）EDGAR 系统，机构投资者季度 13F-HR 文件。
API 文档：https://www.sec.gov/search#/q=13F-HR
"""

import logging
import time
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# slug → SEC EDGAR CIK（机构编号）
GURU_CIK_MAP: dict[str, str] = {
    # 亚洲机构
    "hhlr-advisors-ltd-": "0001762304",          # 高瓴资本 HHLR Advisors
    "hsg-holding-ltd": "0001279329",             # 红杉资本 (Shen Neil Nanpeng)
    "li-lu": "0001709323",                       # 李录 Himalaya Capital
    "perseverance-asset-management-international": "0001802695",  # 高毅资产
    "greenwoods-asset-management-hong-kong-ltd-": "0001848138",   # 景林资产
    "pinpoint-asset-management-ltd": "0001803237",                # 保银投资
    "matthews-china-fund": "0001028074",          # 马修斯中国基金
    # 北美大师
    "warren-buffett": "0001067983",              # 伯克希尔·哈撒韦
    "bill-gates": "0001681490",                  # 盖茨 Cascade Investment
    "carl-icahn": "0000921669",                  # 卡尔·伊坎
    "george-soros": "0001029160",                # 索罗斯基金
    "david-tepper": "0001656456",                # Appaloosa LP
    "seth-klarman": "0001061768",                # Baupost Group
    "chase-coleman": "0001167483",               # Tiger Global
    "catherine-wood": "0001730815",              # ARK Investment Management
    "bill-ackman": "0001336528",                 # Pershing Square Capital
    "joel-greenblatt": "0001510387",             # Gotham Asset Management
    "daily-journal-corp": "0000783412",          # Daily Journal Corp
    "ray-dalio": "0001350694",                   # Bridgewater Associates
    "michael-price": "0001009207",               # MFP Investors
    "tiger-management": "0001027451",            # Tiger Management
    "mohnish-pabrai": "0001549575",              # Dalal Street (Pabrai)
}

_HEADERS = {
    "User-Agent": "BeFriend-FundAsset admin@example.com",
    "Accept-Encoding": "gzip, deflate",
}


def _find_latest_13f(cik: str) -> tuple[str, str] | None:
    """查找 CIK 最新的 13F-HR 文件。

    Returns:
        (accession_number, filing_date) or None
    """
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    try:
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch EDGAR submissions for CIK {cik}: {e}")
        return None

    data = r.json()
    filings = data.get("filings", {}).get("recent", {})
    forms = filings.get("form", [])
    dates = filings.get("filingDate", [])
    accessions = filings.get("accessionNumber", [])

    for i, form in enumerate(forms):
        if "13F" in form:
            return accessions[i], dates[i]
    return None


def _find_infotable_url(cik: str, accession: str) -> str | None:
    """从 13F 文件索引页找到 infotable XML 链接。"""
    cik_num = cik.lstrip("0")
    index_url = f"https://www.sec.gov/Archives/edgar/data/{cik_num}/{accession}-index.htm"
    try:
        r = requests.get(index_url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch 13F index page: {e}")
        return None

    soup = BeautifulSoup(r.text, "lxml")
    for a in soup.find_all("a"):
        href = a.get("href", "")
        text = a.get_text(strip=True).lower()
        # infotable XML is the holdings detail file
        if ("infotable" in href.lower() or "infotable" in text) and not href.endswith("/primary_doc.xml"):
            if href.startswith("/"):
                return f"https://www.sec.gov{href}"
            return href

    # Fallback: look for any XML that's not the primary doc
    acc_clean = accession.replace("-", "")
    for a in soup.find_all("a"):
        href = a.get("href", "")
        if href.endswith(".xml") and "primary_doc" not in href and acc_clean in href:
            if href.startswith("/"):
                return f"https://www.sec.gov{href}"
            return href

    return None


def _parse_infotable_xml(xml_text: str) -> list[dict]:
    """解析 13F infotable XML，提取持仓列表。"""
    # Try raw XML first (without XSLT transform)
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        # May have XSLT — try extracting from HTML
        return _parse_infotable_html(xml_text)

    # Find namespace
    ns = ""
    for elem in root.iter():
        if "infotable" in elem.tag.lower():
            if "}" in elem.tag:
                ns = elem.tag.split("}")[0] + "}"
            break

    entries = root.findall(f".//{ns}infoTable")
    if not entries:
        # Try without namespace
        entries = root.findall(".//infoTable")

    holdings: list[dict] = []
    # Aggregate by issuer name (multiple entries per stock for different managers)
    agg: dict[str, dict] = {}
    for e in entries:
        def _get(tag: str) -> str:
            el = e.find(f"{ns}{tag}")
            if el is None:
                el = e.find(tag)
            return el.text.strip() if el is not None and el.text else ""

        name = _get("nameOfIssuer")
        cusip = _get("cusip")
        value_str = _get("value")
        shares_el = e.find(f"{ns}shrsOrPrnAmt")
        if shares_el is None:
            shares_el = e.find("shrsOrPrnAmt")
        shares = ""
        if shares_el is not None:
            amt_el = shares_el.find(f"{ns}sshPrnamt")
            if amt_el is None:
                amt_el = shares_el.find("sshPrnamt")
            shares = amt_el.text.strip() if amt_el is not None and amt_el.text else ""

        key = cusip or name
        if key in agg:
            agg[key]["value"] = str(int(agg[key]["value"]) + int(value_str)) if value_str.isdigit() else agg[key]["value"]
            agg[key]["shares"] = str(int(agg[key]["shares"]) + int(shares)) if shares.isdigit() else agg[key]["shares"]
        else:
            agg[key] = {
                "stock_code": cusip,
                "stock_name": name,
                "value": value_str,
                "shares": shares,
            }

    # Sort by value descending
    sorted_items = sorted(agg.values(), key=lambda x: int(x["value"]) if x["value"].isdigit() else 0, reverse=True)

    # Calculate total value for weight
    total_value = sum(int(x["value"]) for x in sorted_items if x["value"].isdigit())

    for item in sorted_items:
        val = int(item["value"]) if item["value"].isdigit() else 0
        weight = f"{val / total_value * 100:.2f}%" if total_value > 0 else ""
        # Format value: in thousands (SEC reports in thousands)
        value_fmt = f"${val / 1000:.2f}M" if val >= 1000 else f"${val}K"
        holdings.append({
            "stock_code": item["stock_code"],
            "stock_name": item["stock_name"],
            "weight_pct": weight,
            "shares": f"{int(item['shares']):,}" if item["shares"].isdigit() else item["shares"],
            "value": value_fmt,
        })

    return holdings


def _parse_infotable_html(html_text: str) -> list[dict]:
    """Fallback: 从 XSLT-rendered HTML 中解析持仓表格。"""
    soup = BeautifulSoup(html_text, "lxml")
    tables = soup.find_all("table")
    if not tables:
        return []

    holdings = []
    for table in tables:
        rows = table.find_all("tr")
        for row in rows[1:]:  # skip header
            tds = row.find_all("td")
            if len(tds) >= 4:
                holdings.append({
                    "stock_code": tds[2].get_text(strip=True) if len(tds) > 2 else "",
                    "stock_name": tds[0].get_text(strip=True),
                    "value": tds[3].get_text(strip=True) if len(tds) > 3 else "",
                    "shares": tds[4].get_text(strip=True) if len(tds) > 4 else "",
                    "weight_pct": "",
                })
    return holdings


def fetch_13f_holdings(slug: str) -> list[dict]:
    """获取指定 guru 的最新 13F 持仓。"""
    cik = GURU_CIK_MAP.get(slug)
    if not cik:
        logger.warning(f"No CIK mapping for {slug}")
        return []

    filing = _find_latest_13f(cik)
    if not filing:
        logger.warning(f"No 13F filing found for {slug} (CIK={cik})")
        return []

    accession, filing_date = filing
    logger.info(f"Found 13F for {slug}: accession={accession}, date={filing_date}")

    infotable_url = _find_infotable_url(cik, accession)
    if not infotable_url:
        logger.warning(f"No infotable URL found for {slug}")
        return []

    # Get raw XML (without XSLT transform)
    raw_url = infotable_url
    if "/xslForm13F_X02/" in raw_url:
        # Strip the XSLT prefix to get raw XML
        parts = raw_url.split("/xslForm13F_X02/")
        raw_url = parts[0] + "/" + parts[1]

    try:
        r = requests.get(raw_url, headers=_HEADERS, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch infotable XML: {e}")
        return []

    return _parse_infotable_xml(r.text)


def fetch_all_13f_gurus(delay: float = 1.0) -> dict[str, list[dict]]:
    """获取所有有 CIK 的 guru 的最新 13F 持仓。

    Returns:
        dict: slug → holdings list
    """
    results: dict[str, list[dict]] = {}
    for slug in GURU_CIK_MAP:
        logger.info(f"Fetching 13F for {slug}")
        holdings = fetch_13f_holdings(slug)
        if holdings:
            results[slug] = holdings
            logger.info(f"  → {len(holdings)} holdings")
        else:
            logger.warning(f"  → no holdings returned")
        time.sleep(delay)
    return results
