import json
import sys
from datetime import datetime
from pathlib import Path


SOURCE_DIR = Path(r"D:\광고보고서\data\cafe24_sales")
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
STORE_NAME = "카페24(자사몰)"
AUTO_NAME = "자사몰 자동수집"
TARGET_FILES = [
    DATA_DIR / "monthly-dashboard-2026-07.json",
    DATA_DIR / "monthly-dashboard-latest.json",
]


def week_index(date_text):
    day = int(date_text[-2:])
    return 0 if day <= 5 else 1 if day <= 12 else 2 if day <= 19 else 3 if day <= 26 else 4


def read_rows(start_date, end_date):
    rows = []
    for path in sorted(SOURCE_DIR.glob("cafe24_daily_sales_2026-07-*.json")):
        item = json.loads(path.read_text(encoding="utf-8-sig"))
        date_text = item.get("date") or path.stem.replace("cafe24_daily_sales_", "")
        if not start_date <= date_text <= end_date:
            continue
        revenue = int(round(float(item.get("revenue") or 0)))
        rows.append(
            {
                "date": date_text,
                "grossSales": revenue,
                "refunds": 0,
                "netSales": revenue,
                "orders": int(item.get("orderCount") or 0),
                "items": int(item.get("orderCount") or 0),
                "source": path.name,
            }
        )
    expected = {f"2026-07-{day:02d}" for day in range(int(start_date[-2:]), int(end_date[-2:]) + 1)}
    actual = {row["date"] for row in rows}
    if actual != expected:
        raise ValueError(f"Missing Cafe24 API dates: {sorted(expected - actual)}")
    return rows


def update(path, imported):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    metrics = data["totalSalesMetrics"]
    by_date = {item["date"]: item for item in metrics.get("dailySales", [])}

    for row in imported:
        day = by_date.setdefault(row["date"], {"date": row["date"], "weekday": "", "stores": []})
        stores = [item for item in day.get("stores", []) if item.get("name") != STORE_NAME]
        stores.append(
            {
                "name": STORE_NAME,
                "store": STORE_NAME,
                "grossSales": row["grossSales"],
                "refunds": row["refunds"],
                "netSales": row["netSales"],
                "orders": row["orders"],
                "items": row["items"],
                "source": row["source"],
                "basis": "Cafe24 Admin API 결제일/payment_amount, 취소 주문 제외",
            }
        )
        day["stores"] = stores
        day["totalGrossSales"] = sum(int(item.get("grossSales", 0)) for item in stores)
        day["totalRefunds"] = sum(int(item.get("refunds", 0)) for item in stores)
        day["totalNetSales"] = sum(int(item.get("netSales", 0)) for item in stores)
        day["netSales"] = day["totalNetSales"]

    metrics["dailySales"] = [by_date[key] for key in sorted(by_date)]
    metrics["dailySalesTotals"] = [
        {"date": item["date"], "netSales": item["totalNetSales"]} for item in metrics["dailySales"]
    ]

    weeks = [0, 0, 0, 0, 0]
    for day in metrics["dailySales"]:
        for store in day.get("stores", []):
            if store.get("name") == STORE_NAME:
                weeks[week_index(day["date"])] += int(store.get("netSales", 0))

    auto_sales = metrics.get("autoSales", [])
    target = next((item for item in auto_sales if item.get("name") == AUTO_NAME), None)
    if target is None:
        target = {"name": AUTO_NAME}
        auto_sales.append(target)
    target["weeks"] = weeks
    target["total"] = sum(weeks)
    metrics["autoSales"] = auto_sales

    total_weeks = [
        sum(float(item.get("weeks", [0] * 5)[index] or 0) for item in auto_sales)
        for index in range(5)
    ]
    metrics["autoSalesTotal"] = {
        "name": "자동 매출 합계",
        "weeks": total_weeks,
        "total": sum(total_weeks),
    }

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    metrics["dailySalesUpdatedAt"] = stamp
    revenue = data.setdefault("revenueMetrics", {})
    revenue["dailySales"] = metrics["dailySales"]
    revenue["dailySalesUpdatedAt"] = stamp
    revenue["updatedAt"] = stamp
    data["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main():
    start_date = sys.argv[1] if len(sys.argv) > 1 else "2026-07-20"
    end_date = sys.argv[2] if len(sys.argv) > 2 else "2026-07-26"
    rows = read_rows(start_date, end_date)
    for path in TARGET_FILES:
        update(path, rows)
    print(
        json.dumps(
            {
                "dates": [row["date"] for row in rows],
                "orders": sum(row["orders"] for row in rows),
                "netSales": sum(row["netSales"] for row in rows),
                "targets": [str(path) for path in TARGET_FILES],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
