import csv
import json
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


SOURCE = Path(sys.argv[1])
DATE = sys.argv[2]
REPORT_ROOT = Path(r"D:\광고보고서")
ARCHIVE_DIR = REPORT_ROOT / "data" / "cafe24_sales"
DATA_DIRS = [REPORT_ROOT / "public_dashboard" / "data", Path(r"C:\Users\user\Documents\New project 4\public_dashboard\data")]
TARGET_FILES = ["monthly-dashboard-2026-07.json", "monthly-dashboard-latest.json"]


def number(value):
    return float(str(value or "0").replace(",", ""))


def read_rows():
    raw = list(csv.DictReader(SOURCE.read_text(encoding="utf-8-sig").splitlines()))
    unique_items = {}
    for row in raw:
        item_code = row["상품 품목코드"].strip()
        signature = (item_code, row["결제수량"], row["환불수량"], row["판매수량"], row["판매합계"])
        unique_items[signature] = row
    groups = defaultdict(list)
    for row in unique_items.values():
        groups[row["상품코드"].strip()].append(row)
    result = []
    for product_code, items in groups.items():
        name = items[0]["상품명"].strip()
        options = [{
            "itemCode": item["상품 품목코드"].strip(), "option": item["옵션"].strip(),
            "sales": number(item["판매합계"]), "paidQuantity": number(item["결제수량"]),
            "refundQuantity": number(item["환불수량"]), "soldQuantity": number(item["판매수량"]),
        } for item in items]
        sales = sum(item["sales"] for item in options)
        paid = sum(item["paidQuantity"] for item in options)
        refunded = sum(item["refundQuantity"] for item in options)
        result.append({
            "recordId": f"cafe24:{product_code}", "date": DATE, "store": "cafe24", "storeName": "카페24(자사몰)",
            "productId": product_code, "productName": name, "product": name, "adgroup": "",
            "adSales": 0.0, "adCost": 0.0, "impressions": 0.0, "clicks": 0.0, "conversions": 0.0,
            "status": "자연", "memo": "카페24 상품 단위 성과(분류 중복 제거, 판매합계 기준; 쿠폰 할인 미배분)",
            "dailySales": sales, "orders": paid, "refundAmount": 0.0, "roas": 0.0, "adCostRate": 0.0,
            "adProfit": 0.0, "source": SOURCE.name, "grossSales": sales, "quantity": paid,
            "refundQuantity": refunded, "itemCodes": [item["itemCode"] for item in options], "optionBreakdown": options,
        })
    return result, len(unique_items), len(raw)


def merged(existing, rows):
    kept = [row for row in existing if not (row.get("date") == DATE and row.get("store") == "cafe24")]
    return sorted(kept + rows, key=lambda row: (str(row.get("date", "")), str(row.get("store", "")), -number(row.get("dailySales"))))


def refresh(section):
    rows = section["rows"]
    section["count"] = len(rows)
    dates = sorted({row.get("date") for row in rows if row.get("date")})
    section["dateLabel"] = f"{dates[0]} ~ {dates[-1]}" if dates else ""
    section["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    totals = {key: sum(number(row.get(key)) for row in rows) for key in ["adSales", "adCost", "dailySales", "orders"]}
    totals["roas"] = totals["adSales"] / totals["adCost"] if totals["adCost"] else 0.0
    totals["adCostRate"] = totals["adCost"] / totals["dailySales"] if totals["dailySales"] else 0.0
    totals["adProfit"] = totals["adSales"] - totals["adCost"]
    section["totals"] = totals


def update_dashboard(path, rows):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    section = data.setdefault("dailyProductPerformance", {"rows": []})
    section["rows"] = merged(section.get("rows", []), rows)
    refresh(section)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main():
    rows, unique_count, raw_count = read_rows()
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE, ARCHIVE_DIR / SOURCE.name)
    master = REPORT_ROOT / "data" / "daily_product_performance.json"
    payload = json.loads(master.read_text(encoding="utf-8-sig"))
    existing = payload.get("rows", payload) if isinstance(payload, dict) else payload
    output_rows = merged(existing, rows)
    if isinstance(payload, dict):
        payload["rows"] = output_rows
        payload["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        output = payload
    else:
        output = output_rows
    master.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for directory in DATA_DIRS:
        for filename in TARGET_FILES:
            update_dashboard(directory / filename, rows)
    print(json.dumps({"date": DATE, "rawRows": raw_count, "uniqueItems": unique_count, "products": len(rows), "sales": sum(row["dailySales"] for row in rows), "paidQuantity": sum(row["quantity"] for row in rows), "refundQuantity": sum(row["refundQuantity"] for row in rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
