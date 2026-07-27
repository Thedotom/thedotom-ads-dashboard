import json
import sys
from datetime import datetime, timedelta
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
STORE_NAME = "스마트스토어(무라)"


def number(value):
    return int(round(float(value or 0)))


def week_index(date_text):
    day = int(date_text[-2:])
    return 0 if day <= 5 else 1 if day <= 12 else 2 if day <= 19 else 3 if day <= 26 else 4


def date_range(start_date, end_date):
    current = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    while current <= end:
        yield current.isoformat()
        current += timedelta(days=1)


def build_rows(data, start_date, end_date):
    target_dates = set(date_range(start_date, end_date))
    by_date = {
        date_text: {
            "date": date_text,
            "grossSales": 0,
            "refunds": 0,
            "netSales": 0,
            "orders": 0,
            "refundOrders": 0,
            "sources": set(),
        }
        for date_text in target_dates
    }

    for item in data.get("dailyProductPerformance", {}).get("rows", []):
        if str(item.get("store", "")).lower() != "mura":
            continue
        date_text = str(item.get("date", ""))[:10]
        if date_text not in by_date:
            continue
        row = by_date[date_text]
        row["grossSales"] += number(item.get("grossSales"))
        row["refunds"] += number(item.get("refundAmount"))
        row["netSales"] += number(item.get("dailySales"))
        row["orders"] += number(item.get("orders"))
        row["refundOrders"] += number(item.get("refundOrders"))
        if item.get("source"):
            row["sources"].add(str(item["source"]))

    result = []
    for date_text in sorted(by_date):
        row = by_date[date_text]
        if row["grossSales"] - row["refunds"] != row["netSales"]:
            raise ValueError(f"Mura net sales mismatch on {date_text}: {row}")
        row["source"] = ", ".join(sorted(row.pop("sources"))) or f"자동 조회 확인: {date_text} 무라 매출 없음"
        result.append(row)
    return result


def update(path, start_date, end_date):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    metrics = data.setdefault("totalSalesMetrics", {})
    rows = build_rows(data, start_date, end_date)
    daily_by_date = {item["date"]: item for item in metrics.get("dailySales", [])}

    for row in rows:
        day = daily_by_date.setdefault(row["date"], {"date": row["date"], "weekday": "", "stores": []})
        stores = [
            store
            for store in day.get("stores", [])
            if "무라" not in str(store.get("name") or store.get("store") or "")
            and "mura" not in str(store.get("name") or store.get("store") or "").lower()
        ]
        stores.append(
            {
                "name": STORE_NAME,
                "store": STORE_NAME,
                "grossSales": row["grossSales"],
                "refunds": row["refunds"],
                "netSales": row["netSales"],
                "orders": row["orders"],
                "refundOrders": row["refundOrders"],
                "source": row["source"],
                "basis": "스마트스토어 판매성과 상품별 합계의 판매금액(순)",
            }
        )
        day["stores"] = stores
        day["totalGrossSales"] = sum(number(store.get("grossSales")) for store in stores)
        day["totalRefunds"] = sum(number(store.get("refunds")) for store in stores)
        day["totalNetSales"] = sum(number(store.get("netSales")) for store in stores)
        day["netSales"] = day["totalNetSales"]

    metrics["dailySales"] = [daily_by_date[key] for key in sorted(daily_by_date)]
    metrics["dailySalesTotals"] = [
        {"date": day["date"], "netSales": day["totalNetSales"]} for day in metrics["dailySales"]
    ]

    mura_weeks = [0, 0, 0, 0, 0]
    for day in metrics["dailySales"]:
        for store in day.get("stores", []):
            if "무라" in str(store.get("name") or store.get("store") or ""):
                mura_weeks[week_index(day["date"])] += number(store.get("netSales"))

    auto_sales = [
        row for row in metrics.get("autoSales", [])
        if "무라" not in str(row.get("name", ""))
        and "mura" not in str(row.get("name", "")).lower()
        and row.get("name") != "자사몰"
    ]
    auto_sales.append({"name": "무라", "weeks": mura_weeks, "total": sum(mura_weeks)})
    metrics["autoSales"] = auto_sales
    total_weeks = [
        sum(number(row.get("weeks", [0] * 5)[index]) for row in auto_sales)
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
    return rows


def main():
    start_date = sys.argv[1]
    end_date = sys.argv[2]
    month = start_date[:7]
    targets = [
        DATA_DIR / f"monthly-dashboard-{month}.json",
        DATA_DIR / "monthly-dashboard-latest.json",
    ]
    results = []
    for path in targets:
        results = update(path, start_date, end_date)
    print(
        json.dumps(
            {
                "dates": [row["date"] for row in results],
                "grossSales": sum(row["grossSales"] for row in results),
                "refunds": sum(row["refunds"] for row in results),
                "netSales": sum(row["netSales"] for row in results),
                "orders": sum(row["orders"] for row in results),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
