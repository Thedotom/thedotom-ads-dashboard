from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import fetch_cafe24_product_performance_api as cafe24


SOURCE_DIR = Path(r"D:\광고보고서\data\cafe24_sales")


def number(value):
    return int(round(float(value or 0)))


def dates(start_date, end_date):
    current = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    while current <= end:
        yield current.isoformat()
        current += timedelta(days=1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--output-dir", type=Path, default=SOURCE_DIR)
    args = parser.parse_args()
    if args.start_date[:7] != args.end_date[:7]:
        raise ValueError("Date range must stay within one month")

    config, headers = cafe24.load_access()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summaries = []
    for index, date_text in enumerate(dates(args.start_date, args.end_date), start=1):
        if index > 1 and index % 20 == 0:
            time.sleep(2)
        orders = [
            order
            for order in cafe24.fetch_orders(config, headers, date_text)
            if not cafe24.is_canceled(order)
        ]
        revenue = sum(number(order.get("payment_amount")) for order in orders)
        payload = {
            "date": date_text,
            "revenue": revenue,
            "orderCount": len(orders),
            "basis": "Cafe24 Admin API pay_date/payment_amount, canceled orders excluded",
        }
        path = args.output_dir / f"cafe24_daily_sales_{date_text}.json"
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        summaries.append(payload)
        print(json.dumps(payload, ensure_ascii=False), flush=True)

    print(
        json.dumps(
            {
                "dates": len(summaries),
                "orders": sum(item["orderCount"] for item in summaries),
                "netSales": sum(item["revenue"] for item in summaries),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
