from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEFAULT_SOURCE_DIR = Path(r"D:\광고보고서\data\cafe24_sales")
STORE_NAME = "카페24(자사몰)"
AUTO_NAME = "자사몰 자동수집"


def dates(start: str, end: str):
    current = datetime.strptime(start, "%Y-%m-%d").date()
    last = datetime.strptime(end, "%Y-%m-%d").date()
    while current <= last:
        yield current.isoformat()
        current += timedelta(days=1)


def week_index(date_text: str) -> int:
    day = int(date_text[-2:])
    return 0 if day <= 5 else 1 if day <= 12 else 2 if day <= 19 else 3 if day <= 26 else 4


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    args = parser.parse_args()
    if args.start_date[:7] != args.end_date[:7]:
        raise ValueError("Date range must stay within one month")

    target_dates = list(dates(args.start_date, args.end_date))
    imported = []
    for date_text in target_dates:
        source = args.source_dir / f"cafe24_daily_sales_{date_text}.json"
        if not source.exists():
            raise FileNotFoundError(source)
        item = json.loads(source.read_text(encoding="utf-8-sig"))
        if item.get("date") != date_text:
            raise ValueError(f"Unexpected date in {source.name}: {item.get('date')}")
        imported.append(
            {
                "date": date_text,
                "grossSales": int(item.get("revenue") or 0),
                "refunds": 0,
                "netSales": int(item.get("revenue") or 0),
                "orders": int(item.get("orderCount") or 0),
                "source": source.name,
            }
        )

    target = DATA_DIR / f"monthly-dashboard-{args.start_date[:7]}.json"
    data = json.loads(target.read_text(encoding="utf-8-sig"))
    metrics = data["totalSalesMetrics"]
    daily = {row["date"]: row for row in metrics["dailySales"]}

    for row in imported:
        day = daily[row["date"]]
        stores = [
            store
            for store in day.get("stores", [])
            if store.get("name") != STORE_NAME and store.get("store") != STORE_NAME
        ]
        stores.append(
            {
                "name": STORE_NAME,
                "store": STORE_NAME,
                "grossSales": row["grossSales"],
                "refunds": 0,
                "netSales": row["netSales"],
                "orders": row["orders"],
                "items": row["orders"],
                "source": row["source"],
                "basis": "Cafe24 Admin API 결제일 payment_amount, 취소 주문 제외",
            }
        )
        day["stores"] = stores
        day["totalGrossSales"] = sum(int(store.get("grossSales") or 0) for store in stores)
        day["totalRefunds"] = sum(int(store.get("refunds") or 0) for store in stores)
        day["totalNetSales"] = sum(int(store.get("netSales") or 0) for store in stores)
        day["netSales"] = day["totalNetSales"]

    metrics["dailySales"] = [daily[key] for key in sorted(daily)]
    metrics["dailySalesTotals"] = [
        {"date": row["date"], "netSales": row["totalNetSales"]}
        for row in metrics["dailySales"]
    ]

    weeks = [0, 0, 0, 0, 0]
    for row in imported:
        weeks[week_index(row["date"])] += row["netSales"]
    auto_sales = [
        row
        for row in metrics.get("autoSales", [])
        if row.get("name") not in {"자사몰", AUTO_NAME}
    ]
    auto_sales.append({"name": AUTO_NAME, "weeks": weeks, "total": sum(weeks)})
    metrics["autoSales"] = auto_sales
    total_weeks = [
        sum(int(row.get("weeks", [0] * 5)[index] or 0) for row in auto_sales)
        for index in range(5)
    ]
    metrics["autoSalesTotal"] = {
        "name": "자동 매출 합계",
        "weeks": total_weeks,
        "total": sum(total_weeks),
    }

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    metrics["dailySalesUpdatedAt"] = stamp
    profile = data.setdefault("dataProfile", {})
    profile["cafe24SalesMemo"] = (
        f"{args.start_date} ~ {args.end_date} Cafe24 Admin API 결제일 기준, "
        f"취소 주문 제외: {len(imported)}일, {sum(row['orders'] for row in imported):,}건, "
        f"{sum(row['netSales'] for row in imported):,}원"
    )
    data["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    target.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(
        json.dumps(
            {
                "dates": len(imported),
                "orders": sum(row["orders"] for row in imported),
                "netSales": sum(row["netSales"] for row in imported),
                "weeks": weeks,
                "target": str(target),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
