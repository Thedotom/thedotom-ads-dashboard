from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import fetch_cafe24_product_performance_api as cafe24


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
RAW_DIR = Path(r"D:\광고보고서\data\cafe24_product_api")
STORE_NAME = "카페24(자사몰)"


def dates(start: str, end: str):
    current = datetime.strptime(start, "%Y-%m-%d").date()
    last = datetime.strptime(end, "%Y-%m-%d").date()
    while current <= last:
        yield current.isoformat()
        current += timedelta(days=1)


def normalize(row: dict) -> dict:
    row["store"] = "cafe24"
    row["storeName"] = STORE_NAME
    row["status"] = "자연"
    row["memo"] = "카페24 주문상품 API 결제일 기준 상품별 총판매가"
    return row


def refresh(section: dict) -> None:
    rows = section.get("rows", [])
    section["count"] = len(rows)
    row_dates = sorted({row.get("date") for row in rows if row.get("date")})
    section["dateLabel"] = f"{row_dates[0]} ~ {row_dates[-1]}" if row_dates else ""
    totals = {
        key: sum(float(row.get(key) or 0) for row in rows)
        for key in ["adSales", "adCost", "dailySales", "orders"]
    }
    totals["roas"] = totals["adSales"] / totals["adCost"] if totals["adCost"] else 0
    totals["adCostRate"] = totals["adCost"] / totals["dailySales"] if totals["dailySales"] else 0
    totals["adProfit"] = totals["adSales"] - totals["adCost"]
    section["totals"] = totals
    section["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    args = parser.parse_args()
    if args.start_date[:7] != args.end_date[:7]:
        raise ValueError("Date range must stay within one month")

    target = DATA_DIR / f"monthly-dashboard-{args.start_date[:7]}.json"
    data = json.loads(target.read_text(encoding="utf-8-sig"))
    section = data.setdefault("dailyProductPerformance", {"rows": []})
    target_dates = set(dates(args.start_date, args.end_date))
    kept = [
        row for row in section.get("rows", [])
        if not (row.get("store") == "cafe24" and str(row.get("date", ""))[:10] in target_dates)
    ]

    config, headers = cafe24.load_access()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    imported = []
    summaries = []
    for index, date_text in enumerate(sorted(target_dates), start=1):
        rows, orders, raw_items = cafe24.build_rows(date_text, config, headers)
        rows = [normalize(row) for row in rows]
        imported.extend(rows)
        raw_path = RAW_DIR / f"cafe24_orders_api_{date_text}.json"
        raw_path.write_text(
            json.dumps({"date": date_text, "orders": orders, "items": raw_items}, ensure_ascii=False),
            encoding="utf-8",
        )
        summary = {
            "date": date_text, "products": len(rows), "orders": len(orders),
            "items": len(raw_items), "productSales": sum(float(row["dailySales"]) for row in rows),
        }
        summaries.append(summary)
        print(json.dumps(summary, ensure_ascii=False), flush=True)
        if index % 10 == 0:
            time.sleep(2)

    section["rows"] = sorted(
        kept + imported,
        key=lambda row: (str(row.get("date", "")), str(row.get("store", "")), -float(row.get("dailySales") or 0)),
    )
    refresh(section)
    data.setdefault("dataProfile", {})["cafe24ProductMemo"] = (
        f"{args.start_date} ~ {args.end_date} Cafe24 주문상품 API 결제일 기준 상품별 총판매가"
    )
    data["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    target.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({
        "dates": len(summaries), "productRows": len(imported),
        "orders": sum(row["orders"] for row in summaries),
        "items": sum(row["items"] for row in summaries),
        "productSales": sum(row["productSales"] for row in summaries),
        "target": str(target),
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
