import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import openpyxl


SOURCE = Path(sys.argv[1])
REPORT_ROOT = Path(r"D:\광고보고서")
ARCHIVE_DIR = REPORT_ROOT / "data" / "smartstore_product_performance"
DATA_DIRS = [REPORT_ROOT / "public_dashboard" / "data", Path(r"C:\Users\user\Documents\New project 4\public_dashboard\data")]
TARGET_FILES = ["monthly-dashboard-2026-07.json", "monthly-dashboard-latest.json"]
match = re.search(r"sales_(\d{4})(\d{2})(\d{2})-", SOURCE.name)
if not match:
    raise ValueError(f"Cannot determine date from {SOURCE.name}")
DATE = "-".join(match.groups())
STORE = "mura"
STORE_NAME = "스마트스토어(무라)"


def number(value):
    return float(value or 0)


def read_rows():
    sheet = openpyxl.load_workbook(SOURCE, read_only=True, data_only=True)["SALES"]
    values = list(sheet.iter_rows(values_only=True))
    headers = list(values[0])
    required = ["날짜", "채널상품명", "채널상품번호", "상품결제건수", "환불건수", "판매금액(총)", "판매금액(순)", "환불금액", "결제상품수량", "환불상품수량"]
    missing = [name for name in required if name not in headers]
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    col = {name: headers.index(name) for name in required}
    rows = []
    for raw in values[1:]:
        product_id = str(raw[col["채널상품번호"]] or "").strip()
        if product_id == "전체":
            continue
        if str(raw[col["날짜"]])[:10] != DATE:
            raise ValueError(f"Unexpected date: {raw[col['날짜']]}")
        name = str(raw[col["채널상품명"]] or "").strip()
        rows.append({
            "recordId": product_id, "date": DATE, "store": STORE, "storeName": STORE_NAME,
            "productId": product_id, "productName": name, "product": name, "adgroup": "",
            "adSales": 0.0, "adCost": 0.0, "impressions": 0.0, "clicks": 0.0, "conversions": 0.0,
            "status": "자연", "memo": "정상 운영", "dailySales": number(raw[col["판매금액(순)"]]),
            "orders": number(raw[col["상품결제건수"]]), "refundAmount": number(raw[col["환불금액"]]),
            "roas": 0.0, "adCostRate": 0.0, "adProfit": 0.0, "source": SOURCE.name,
            "grossSales": number(raw[col["판매금액(총)"]]), "quantity": number(raw[col["결제상품수량"]]),
            "refundQuantity": number(raw[col["환불상품수량"]]), "refundOrders": number(raw[col["환불건수"]]),
        })
    if not rows:
        raise ValueError("No product rows found")
    return rows


def refresh(section):
    rows = section.get("rows", [])
    section["count"] = len(rows)
    dates = sorted({row.get("date") for row in rows if row.get("date")})
    section["dateLabel"] = f"{dates[0]} ~ {dates[-1]}" if dates else ""
    section["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    totals = {key: sum(number(row.get(key)) for row in rows) for key in ["adSales", "adCost", "dailySales", "orders"]}
    totals["roas"] = totals["adSales"] / totals["adCost"] if totals["adCost"] else 0.0
    totals["adCostRate"] = totals["adCost"] / totals["dailySales"] if totals["dailySales"] else 0.0
    totals["adProfit"] = totals["adSales"] - totals["adCost"]
    section["totals"] = totals


def merge_rows(existing, new_rows):
    kept = [row for row in existing if not (row.get("date") == DATE and row.get("store") in {STORE, "mura_store"})]
    return sorted(kept + new_rows, key=lambda row: (str(row.get("date", "")), str(row.get("store", "")), -number(row.get("dailySales"))))


def update_dashboard(path, new_rows):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    section = data.setdefault("dailyProductPerformance", {"rows": []})
    section["rows"] = merge_rows(section.get("rows", []), new_rows)
    refresh(section)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main():
    rows = read_rows()
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE, ARCHIVE_DIR / SOURCE.name)
    master = REPORT_ROOT / "data" / "daily_product_performance.json"
    payload = json.loads(master.read_text(encoding="utf-8-sig"))
    existing = payload.get("rows", payload) if isinstance(payload, dict) else payload
    merged = merge_rows(existing, rows)
    if isinstance(payload, dict):
        payload["rows"] = merged
        payload["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        output = payload
    else:
        output = merged
    master.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for directory in DATA_DIRS:
        for filename in TARGET_FILES:
            update_dashboard(directory / filename, rows)
    print(json.dumps({"date": DATE, "products": len(rows), "grossSales": sum(r["grossSales"] for r in rows), "refunds": sum(r["refundAmount"] for r in rows), "netSales": sum(r["dailySales"] for r in rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
