import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import openpyxl


DEFAULT_SOURCE = Path(r"C:\Users\user\Downloads\sales_20260710-20260710_bb6a8710-cdd2-4fd6-aff8-1a8da56e8759.xlsx")
SOURCE = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
REPORT_ROOT = Path(r"D:\광고보고서")
ARCHIVE_DIR = REPORT_ROOT / "data" / "smartstore_product_performance"
DATA_DIRS = [
    REPORT_ROOT / "public_dashboard" / "data",
    Path(r"C:\Users\user\Documents\New project 4\public_dashboard\data"),
]
TARGET_FILES = ["monthly-dashboard-2026-07.json", "monthly-dashboard-latest.json"]
date_match = re.search(r"sales_(\d{4})(\d{2})(\d{2})-", SOURCE.name)
if not date_match:
    raise ValueError(f"Cannot determine date from source filename: {SOURCE.name}")
DATE = "-".join(date_match.groups())
STORE = "thedotom"
STORE_NAME = "스마트스토어(더도톰스튜디오)"


def number(value):
    return float(value or 0)


def read_product_rows():
    workbook = openpyxl.load_workbook(SOURCE, read_only=True, data_only=True)
    sheet = workbook["SALES"]
    values = list(sheet.iter_rows(values_only=True))
    headers = list(values[0])
    required = [
        "날짜", "채널상품명", "채널상품번호", "상품결제건수", "환불건수",
        "판매금액(총)", "판매금액(순)", "환불금액", "결제상품수량", "환불상품수량",
    ]
    missing = [name for name in required if name not in headers]
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    col = {name: headers.index(name) for name in required}
    rows = []
    for raw in values[1:]:
        product_id = str(raw[col["채널상품번호"]] or "").strip()
        if product_id == "전체":
            continue
        date = str(raw[col["날짜"]])[:10]
        if date != DATE:
            raise ValueError(f"Unexpected date: {date}")
        product_name = str(raw[col["채널상품명"]] or "").strip()
        rows.append({
            "recordId": product_id,
            "date": DATE,
            "store": STORE,
            "storeName": STORE_NAME,
            "productId": product_id,
            "productName": product_name,
            "product": product_name,
            "adgroup": "",
            "adSales": 0.0,
            "adCost": 0.0,
            "impressions": 0.0,
            "clicks": 0.0,
            "conversions": 0.0,
            "status": "자연",
            "memo": "정상 운영",
            "dailySales": number(raw[col["판매금액(순)"]]),
            "orders": number(raw[col["상품결제건수"]]),
            "refundAmount": number(raw[col["환불금액"]]),
            "roas": 0.0,
            "adCostRate": 0.0,
            "adProfit": 0.0,
            "source": SOURCE.name,
            "grossSales": number(raw[col["판매금액(총)"]]),
            "quantity": number(raw[col["결제상품수량"]]),
            "refundQuantity": number(raw[col["환불상품수량"]]),
            "refundOrders": number(raw[col["환불건수"]]),
        })
    if not rows:
        raise ValueError("No product rows found")
    return rows


def refresh_section(section):
    rows = section.get("rows", [])
    section["count"] = len(rows)
    dates = sorted({row.get("date") for row in rows if row.get("date")})
    section["dateLabel"] = f"{dates[0]} ~ {dates[-1]}" if dates else ""
    section["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    totals = {
        "adSales": sum(number(row.get("adSales")) for row in rows),
        "adCost": sum(number(row.get("adCost")) for row in rows),
        "dailySales": sum(number(row.get("dailySales")) for row in rows),
        "orders": sum(number(row.get("orders")) for row in rows),
    }
    totals["roas"] = totals["adSales"] / totals["adCost"] if totals["adCost"] else 0.0
    totals["adCostRate"] = totals["adCost"] / totals["dailySales"] if totals["dailySales"] else 0.0
    totals["adProfit"] = totals["adSales"] - totals["adCost"]
    section["totals"] = totals


def update_dashboard(path, new_rows):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    section = data.setdefault("dailyProductPerformance", {"rows": []})
    kept = [
        row for row in section.get("rows", [])
        if not (row.get("date") == DATE and row.get("store") == STORE)
    ]
    section["rows"] = sorted(
        kept + new_rows,
        key=lambda row: (str(row.get("date", "")), str(row.get("store", "")), -number(row.get("dailySales"))),
    )
    refresh_section(section)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def update_master_file(new_rows):
    path = REPORT_ROOT / "data" / "daily_product_performance.json"
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    existing = payload.get("rows", payload) if isinstance(payload, dict) else payload
    kept = [row for row in existing if not (row.get("date") == DATE and row.get("store") in {STORE, "thedotom_studio"})]
    merged = sorted(kept + new_rows, key=lambda row: (str(row.get("date", "")), str(row.get("store", "")), -number(row.get("dailySales"))))
    if isinstance(payload, dict):
        payload["rows"] = merged
        payload["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        output = payload
    else:
        output = merged
    path.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main():
    rows = read_product_rows()
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archived = ARCHIVE_DIR / SOURCE.name
    shutil.copy2(SOURCE, archived)
    update_master_file(rows)
    updated = []
    for directory in DATA_DIRS:
        for filename in TARGET_FILES:
            path = directory / filename
            update_dashboard(path, rows)
            updated.append(str(path))
    print(json.dumps({
        "source": str(archived),
        "date": DATE,
        "products": len(rows),
        "grossSales": sum(row["grossSales"] for row in rows),
        "refunds": sum(row["refundAmount"] for row in rows),
        "netSales": sum(row["dailySales"] for row in rows),
        "orders": sum(row["orders"] for row in rows),
        "updated": updated,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

