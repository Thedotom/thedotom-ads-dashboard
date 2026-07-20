import json
from datetime import datetime
from pathlib import Path


DATE = "2026-07-19"
STORE_NAME = "스마트스토어(무라)"
DATA_DIRS = [
    Path(r"D:\광고보고서\public_dashboard\data"),
    Path(r"C:\Users\user\Documents\New project 4\public_dashboard\data"),
]
TARGET_FILES = ["monthly-dashboard-2026-07.json", "monthly-dashboard-latest.json"]


def update(path):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    metrics = data["totalSalesMetrics"]
    by_date = {item["date"]: item for item in metrics.get("dailySales", [])}
    day = by_date.setdefault(DATE, {"date": DATE, "weekday": "", "stores": []})
    stores = [item for item in day.get("stores", []) if item.get("name") != STORE_NAME]
    stores.append({
        "name": STORE_NAME,
        "store": STORE_NAME,
        "grossSales": 0,
        "refunds": 0,
        "netSales": 0,
        "orders": 0,
        "refundOrders": 0,
        "source": "사용자 확인: 2026-07-19 무라 매출 없음",
        "basis": "실제 무매출로 확인하여 0원 명시",
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
    revenue = data.setdefault("revenueMetrics", {})
    revenue["dailySales"] = metrics["dailySales"]
    revenue["dailySalesUpdatedAt"] = stamp
    revenue["updatedAt"] = stamp
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


for directory in DATA_DIRS:
    for filename in TARGET_FILES:
        update(directory / filename)
