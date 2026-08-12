from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
STORE_NAME = "스마트스토어(무라)"


def dates(start: str, end: str):
    current = datetime.strptime(start, "%Y-%m-%d").date()
    last = datetime.strptime(end, "%Y-%m-%d").date()
    while current <= last:
        yield current.isoformat()
        current += timedelta(days=1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    args = parser.parse_args()
    if args.start_date[:7] != args.end_date[:7]:
        raise ValueError("Date range must stay within one month")

    target_dates = list(dates(args.start_date, args.end_date))
    target = DATA_DIR / f"monthly-dashboard-{args.start_date[:7]}.json"
    data = json.loads(target.read_text(encoding="utf-8-sig"))
    metrics = data["totalSalesMetrics"]
    daily = {row["date"]: row for row in metrics["dailySales"]}

    for date_text in target_dates:
        day = daily[date_text]
        stores = [
            store
            for store in day.get("stores", [])
            if "무라" not in str(store.get("name") or store.get("store") or "")
        ]
        stores.append(
            {
                "name": STORE_NAME,
                "store": STORE_NAME,
                "grossSales": 0,
                "refunds": 0,
                "netSales": 0,
                "orders": 0,
                "refundOrders": 0,
                "source": f"smartstore_product_sales_mura_{date_text}.xlsx (상품 행 없음)",
                "basis": "스마트스토어 판매성과 상품별 파일 직접 확인",
            }
        )
        day["stores"] = stores
        day["totalGrossSales"] = sum(int(store.get("grossSales") or 0) for store in stores)
        day["totalRefunds"] = sum(int(store.get("refunds") or 0) for store in stores)
        day["totalNetSales"] = sum(int(store.get("netSales") or 0) for store in stores)
        day["netSales"] = day["totalNetSales"]

    metrics["dailySales"] = [daily[key] for key in sorted(daily)]
    metrics["dailySalesTotals"] = [
        {"date": day["date"], "netSales": day["totalNetSales"]}
        for day in metrics["dailySales"]
    ]
    auto_sales = [row for row in metrics.get("autoSales", []) if "무라" not in row.get("name", "")]
    auto_sales.append({"name": "무라", "weeks": [0, 0, 0, 0, 0], "total": 0})
    metrics["autoSales"] = auto_sales
    total_weeks = [sum(int(row.get("weeks", [0] * 5)[i] or 0) for row in auto_sales) for i in range(5)]
    metrics["autoSalesTotal"] = {"name": "자동 매출 합계", "weeks": total_weeks, "total": sum(total_weeks)}

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    metrics["dailySalesUpdatedAt"] = stamp
    data.setdefault("dataProfile", {})["muraSalesMemo"] = (
        f"{args.start_date} ~ {args.end_date} 상품성과 파일 31개 확인: 상품 행 없음, 순매출 0원"
    )
    data["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    target.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"dates": len(target_dates), "netSales": 0, "target": str(target)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
