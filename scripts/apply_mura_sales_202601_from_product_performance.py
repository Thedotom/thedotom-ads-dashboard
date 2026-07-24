from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


TARGET = Path(__file__).resolve().parents[1] / "data" / "monthly-dashboard-2026-01.json"
STORE_NAME = "스마트스토어(무라)"
MONTH = "2026-01"


def number(value) -> int:
    return int(round(float(value or 0)))


def week_index(date_text: str) -> int:
    day = int(date_text[-2:])
    return 0 if day <= 5 else 1 if day <= 12 else 2 if day <= 19 else 3 if day <= 26 else 4


def build_rows(data: dict) -> list[dict]:
    product_rows = data.get("dailyProductPerformance", {}).get("rows", [])
    by_date = {
        f"{MONTH}-{day:02d}": {
            "date": f"{MONTH}-{day:02d}",
            "grossSales": 0,
            "refunds": 0,
            "netSales": 0,
            "orders": 0,
            "refundOrders": 0,
            "sources": set(),
        }
        for day in range(1, 32)
    }
    for item in product_rows:
        if str(item.get("store", "")).lower() != "mura":
            continue
        date = str(item.get("date", ""))[:10]
        if date not in by_date:
            raise ValueError(f"unexpected Mura date: {date}")
        row = by_date[date]
        row["grossSales"] += number(item.get("grossSales"))
        row["refunds"] += number(item.get("refundAmount"))
        row["netSales"] += number(item.get("dailySales"))
        row["orders"] += number(item.get("orders"))
        row["refundOrders"] += number(item.get("refundOrders"))
        if item.get("source"):
            row["sources"].add(str(item["source"]))

    result = []
    for date in sorted(by_date):
        row = by_date[date]
        if row["grossSales"] - row["refunds"] != row["netSales"]:
            raise ValueError(f"Mura net sales mismatch on {date}: {row}")
        row["source"] = ", ".join(sorted(row.pop("sources"))) or "dailyProductPerformance"
        result.append(row)
    return result


def update_dashboard(data: dict, mura_rows: list[dict]) -> dict:
    metrics = data.setdefault("totalSalesMetrics", {})
    daily_by_date = {item["date"]: item for item in metrics.get("dailySales", [])}

    for row in mura_rows:
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
                "basis": "일일 제품 성과 무라 합계 기준 순매출",
            }
        )
        day["stores"] = stores
        day["totalGrossSales"] = sum(number(store.get("grossSales")) for store in stores)
        day["totalRefunds"] = sum(number(store.get("refunds")) for store in stores)
        day["totalNetSales"] = sum(number(store.get("netSales")) for store in stores)
        day["netSales"] = day["totalNetSales"]

    metrics["dailySales"] = [daily_by_date[date] for date in sorted(daily_by_date)]
    metrics["dailySalesTotals"] = [
        {"date": day["date"], "netSales": day["totalNetSales"]}
        for day in metrics["dailySales"]
    ]

    mura_weeks = [0, 0, 0, 0, 0]
    for row in mura_rows:
        mura_weeks[week_index(row["date"])] += row["netSales"]

    auto_sales = [
        row
        for row in metrics.get("autoSales", [])
        if "무라" not in str(row.get("name", "")) and "mura" not in str(row.get("name", "")).lower()
    ]
    auto_sales.append({"name": "무라", "weeks": mura_weeks, "total": sum(mura_weeks)})
    metrics["autoSales"] = auto_sales
    combined = [
        sum(number(row.get("weeks", [0] * 5)[index]) for row in auto_sales)
        for index in range(5)
    ]
    metrics["autoSalesTotal"] = {"name": "자동 매출 합계", "weeks": combined, "total": sum(combined)}

    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    metrics["dailySalesUpdatedAt"] = updated_at
    revenue = data.setdefault("revenueMetrics", {})
    revenue["dailySales"] = metrics["dailySales"]
    revenue["dailySalesUpdatedAt"] = updated_at
    revenue["updatedAt"] = updated_at
    return data


def main() -> None:
    data = json.loads(TARGET.read_text(encoding="utf-8-sig"))
    mura_rows = build_rows(data)
    updated = update_dashboard(data, mura_rows)
    TARGET.write_text(json.dumps(updated, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(
        json.dumps(
            {
                "days": len(mura_rows),
                "grossSales": sum(row["grossSales"] for row in mura_rows),
                "refunds": sum(row["refunds"] for row in mura_rows),
                "netSales": sum(row["netSales"] for row in mura_rows),
                "orders": sum(row["orders"] for row in mura_rows),
                "autoSalesTotal": updated["totalSalesMetrics"]["autoSalesTotal"]["total"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()