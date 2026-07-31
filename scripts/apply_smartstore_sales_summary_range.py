from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
STORES = {
    "thedotom": {
        "name": "스마트스토어(더도톰스튜디오)",
        "autoName": "더도톰스튜디오",
        "aliases": {"thedotom", "thedotom_studio"},
    },
    "mura": {
        "name": "스마트스토어(무라)",
        "autoName": "무라",
        "aliases": {"mura", "mura_store"},
    },
}


def number(value):
    return int(round(float(value or 0)))


def dates(start_date, end_date):
    current = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    while current <= end:
        yield current.isoformat()
        current += timedelta(days=1)


def week_index(date_text):
    day = int(date_text[-2:])
    return 0 if day <= 5 else 1 if day <= 12 else 2 if day <= 19 else 3 if day <= 26 else 4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    args = parser.parse_args()
    if args.start_date[:7] != args.end_date[:7]:
        raise ValueError("Date range must stay within one month")

    month = args.start_date[:7]
    target = DATA_DIR / f"monthly-dashboard-{month}.json"
    data = json.loads(target.read_text(encoding="utf-8-sig"))
    product_rows = data.get("dailyProductPerformance", {}).get("rows", [])
    target_dates = list(dates(args.start_date, args.end_date))
    metrics = data.setdefault("totalSalesMetrics", {})
    daily_by_date = {
        item["date"]: item for item in metrics.get("dailySales", [])
    }

    summaries = {}
    for store_key, config in STORES.items():
        rows = [
            row
            for row in product_rows
            if str(row.get("store", "")).lower() in config["aliases"]
            and str(row.get("date", ""))[:10] in target_dates
        ]
        by_date = {date_text: [] for date_text in target_dates}
        for row in rows:
            by_date[str(row["date"])[:10]].append(row)

        for date_text in target_dates:
            day = daily_by_date.setdefault(
                date_text, {"date": date_text, "weekday": "", "stores": []}
            )
            stores = [
                store
                for store in day.get("stores", [])
                if store.get("name") != config["name"]
            ]
            day_rows = by_date[date_text]
            gross = sum(number(row.get("grossSales")) for row in day_rows)
            refunds = sum(number(row.get("refundAmount")) for row in day_rows)
            net = sum(number(row.get("dailySales")) for row in day_rows)
            if gross - refunds != net:
                raise ValueError(
                    f"{store_key} net sales mismatch on {date_text}: "
                    f"{gross} - {refunds} != {net}"
                )
            sources = sorted(
                {str(row.get("source")) for row in day_rows if row.get("source")}
            )
            stores.append(
                {
                    "name": config["name"],
                    "store": config["name"],
                    "grossSales": gross,
                    "refunds": refunds,
                    "netSales": net,
                    "orders": sum(number(row.get("orders")) for row in day_rows),
                    "refundOrders": sum(
                        number(row.get("refundOrders")) for row in day_rows
                    ),
                    "source": ", ".join(sources)
                    or f"자동 조회 확인: {date_text} 매출 없음",
                    "basis": "스마트스토어 판매성과 상품별 합계의 판매금액(순)",
                }
            )
            day["stores"] = stores
            day["totalGrossSales"] = sum(
                number(store.get("grossSales")) for store in stores
            )
            day["totalRefunds"] = sum(
                number(store.get("refunds")) for store in stores
            )
            day["totalNetSales"] = sum(
                number(store.get("netSales")) for store in stores
            )
            day["netSales"] = day["totalNetSales"]

        summaries[store_key] = {
            "grossSales": sum(number(row.get("grossSales")) for row in rows),
            "refunds": sum(number(row.get("refundAmount")) for row in rows),
            "netSales": sum(number(row.get("dailySales")) for row in rows),
        }

    metrics["dailySales"] = [daily_by_date[key] for key in sorted(daily_by_date)]
    metrics["dailySalesTotals"] = [
        {"date": day["date"], "netSales": day["totalNetSales"]}
        for day in metrics["dailySales"]
    ]

    store_auto_names = {config["autoName"] for config in STORES.values()}
    auto_sales = [
        item
        for item in metrics.get("autoSales", [])
        if item.get("name") not in store_auto_names
    ]
    for store_key, config in STORES.items():
        weeks = [0, 0, 0, 0, 0]
        for day in metrics["dailySales"]:
            store = next(
                (
                    item
                    for item in day.get("stores", [])
                    if item.get("name") == config["name"]
                ),
                None,
            )
            if store:
                weeks[week_index(day["date"])] += number(store.get("netSales"))
        auto_sales.append(
            {
                "name": config["autoName"],
                "weeks": weeks,
                "total": sum(weeks),
            }
        )
    metrics["autoSales"] = auto_sales
    total_weeks = [
        sum(number(item.get("weeks", [0] * 5)[index]) for item in auto_sales)
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
    target.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(json.dumps(summaries, ensure_ascii=False))


if __name__ == "__main__":
    main()
