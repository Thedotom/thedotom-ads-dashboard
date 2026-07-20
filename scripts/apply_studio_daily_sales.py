import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import openpyxl


SOURCE = Path(sys.argv[1])
REPORT_ROOT = Path(r"D:\광고보고서")
ARCHIVE_DIR = REPORT_ROOT / "data" / "smartstore_sales_summary"
DATA_DIRS = [REPORT_ROOT / "public_dashboard" / "data", Path(r"C:\Users\user\Documents\New project 4\public_dashboard\data")]
TARGET_FILES = ["monthly-dashboard-2026-07.json", "monthly-dashboard-latest.json"]
STORE_NAME = "스마트스토어(더도톰스튜디오)"
match = re.search(r"sales_(\d{4})(\d{2})(\d{2})-", SOURCE.name)
if not match:
    raise ValueError(f"Cannot determine date from {SOURCE.name}")
DATE = "-".join(match.groups())


def read_row():
    sheet = openpyxl.load_workbook(SOURCE, read_only=True, data_only=True)["SALES"]
    values = list(sheet.iter_rows(values_only=True))
    headers = list(values[0])
    required = ["날짜", "채널", "상품결제건수", "환불건수", "판매금액(총)", "판매금액(순)", "환불금액"]
    col = {name: headers.index(name) for name in required}
    candidates = [row for row in values[1:] if "더도톰스튜디오" in str(row[col["채널"]] or "")]
    if len(candidates) != 1:
        raise ValueError(f"Expected one studio row, found {len(candidates)}")
    row = candidates[0]
    if str(row[col["날짜"]])[:10] != DATE:
        raise ValueError(f"Unexpected date: {row[col['날짜']]}")
    return {
        "date": DATE,
        "grossSales": int(row[col["판매금액(총)"]] or 0),
        "refunds": int(row[col["환불금액"]] or 0),
        "netSales": int(row[col["판매금액(순)"]] or 0),
        "orders": int(row[col["상품결제건수"]] or 0),
        "refundOrders": int(row[col["환불건수"]] or 0),
    }


def week_index(date_text):
    day = int(date_text[-2:])
    return 0 if day <= 5 else 1 if day <= 12 else 2 if day <= 19 else 3 if day <= 26 else 4


def update(path, row):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    metrics = data["totalSalesMetrics"]
    by_date = {item["date"]: item for item in metrics.get("dailySales", [])}
    day = by_date.setdefault(DATE, {"date": DATE, "weekday": "", "stores": []})
    stores = [item for item in day.get("stores", []) if item.get("name") != STORE_NAME]
    stores.append({
        "name": STORE_NAME, "store": STORE_NAME,
        "grossSales": row["grossSales"], "refunds": row["refunds"], "netSales": row["netSales"],
        "orders": row["orders"], "refundOrders": row["refundOrders"], "source": SOURCE.name,
        "basis": "스마트스토어 판매성과 스토어 행 기준 판매금액(순)",
    })
    day["stores"] = stores
    day["totalGrossSales"] = sum(int(item.get("grossSales", 0)) for item in stores)
    day["totalRefunds"] = sum(int(item.get("refunds", 0)) for item in stores)
    day["totalNetSales"] = sum(int(item.get("netSales", 0)) for item in stores)
    day["netSales"] = day["totalNetSales"]
    metrics["dailySales"] = [by_date[key] for key in sorted(by_date)]
    metrics["dailySalesTotals"] = [{"date": item["date"], "netSales": item["totalNetSales"]} for item in metrics["dailySales"]]
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    metrics["dailySalesUpdatedAt"] = stamp

    weeks = [0, 0, 0, 0, 0]
    for item in metrics["dailySales"]:
        for store in item.get("stores", []):
            if store.get("name") == STORE_NAME:
                weeks[week_index(item["date"])] += int(store.get("netSales", 0))
    auto = metrics.get("autoSales", [])
    studio = next((item for item in auto if item.get("name") == "더도톰스튜디오"), None)
    if studio is None:
        studio = {"name": "더도톰스튜디오"}
        auto.append(studio)
    studio["weeks"], studio["total"] = weeks, sum(weeks)
    metrics["autoSales"] = auto
    combined = [sum(float(item.get("weeks", [0] * 5)[i] or 0) for item in auto if i < len(item.get("weeks", []))) for i in range(5)]
    metrics["autoSalesTotal"] = {"name": "자동 매출 합계", "weeks": combined, "total": sum(combined)}

    revenue = data.setdefault("revenueMetrics", {})
    revenue["dailySales"] = metrics["dailySales"]
    revenue["dailySalesUpdatedAt"] = stamp
    revenue["updatedAt"] = stamp
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main():
    row = read_row()
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE, ARCHIVE_DIR / SOURCE.name)
    for directory in DATA_DIRS:
        for filename in TARGET_FILES:
            update(directory / filename, row)
    print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
