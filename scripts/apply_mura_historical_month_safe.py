from __future__ import annotations

import argparse
import json
from calendar import monthrange
from datetime import datetime
from pathlib import Path

import openpyxl


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEFAULT_SOURCE_DIR = Path(r"D:\광고보고서\data\smartstore_sales")
STORE_NAME = "스마트스토어(무라)"


def number(value):
    return float(value or 0)


def week_index(day: int) -> int:
    return 0 if day <= 5 else 1 if day <= 12 else 2 if day <= 19 else 3 if day <= 26 else 4


def read_rows(path: Path, expected_date: str):
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True)["SALES"]
    values = list(ws.iter_rows(values_only=True))
    headers = list(values[0])
    required = ["날짜", "채널상품명", "채널상품번호", "상품결제건수", "환불건수",
                "판매금액(총)", "판매금액(순)", "환불금액", "결제상품수량", "환불상품수량"]
    missing = [name for name in required if name not in headers]
    if missing:
        raise ValueError(f"Missing columns in {path.name}: {missing}")
    col = {name: headers.index(name) for name in required}
    rows = []
    for raw in values[1:]:
        product_id = str(raw[col["채널상품번호"]] or "").strip()
        if not product_id or product_id == "전체":
            continue
        date_text = str(raw[col["날짜"]])[:10]
        if date_text != expected_date:
            raise ValueError(f"Unexpected date in {path.name}: {date_text}")
        gross = number(raw[col["판매금액(총)"]])
        refunds = number(raw[col["환불금액"]])
        net = number(raw[col["판매금액(순)"]])
        if round(gross - refunds, 6) != round(net, 6):
            raise ValueError(f"Net mismatch in {path.name}: {product_id}")
        name = str(raw[col["채널상품명"]] or "").strip()
        rows.append({"recordId": product_id, "date": expected_date, "store": "mura",
            "storeName": STORE_NAME, "productId": product_id, "productName": name,
            "product": name, "adgroup": "", "adSales": 0.0, "adCost": 0.0,
            "impressions": 0.0, "clicks": 0.0, "conversions": 0.0, "status": "자연",
            "memo": "정상 운영", "dailySales": net,
            "orders": number(raw[col["상품결제건수"]]), "refundAmount": refunds,
            "roas": 0.0, "adCostRate": 0.0, "adProfit": 0.0, "source": path.name,
            "grossSales": gross, "quantity": number(raw[col["결제상품수량"]]),
            "refundQuantity": number(raw[col["환불상품수량"]]),
            "refundOrders": number(raw[col["환불건수"]])})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", required=True)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    args = parser.parse_args()
    year, month_no = map(int, args.month.split("-"))
    day_count = monthrange(year, month_no)[1]
    target = DATA_DIR / f"monthly-dashboard-{args.month}.json"
    data = json.loads(target.read_text(encoding="utf-8-sig"))
    section = data["dailyProductPerformance"]
    kept = [row for row in section["rows"] if row.get("store") != "mura"]
    imported = []
    daily_by_date = {row["date"]: row for row in data["totalSalesMetrics"]["dailySales"]}
    weeks = [0, 0, 0, 0, 0]
    gross_total = refunds_total = orders_total = 0
    for day in range(1, day_count + 1):
        date_text = f"{args.month}-{day:02d}"
        source = args.source_dir / f"smartstore_product_sales_mura_{date_text}.xlsx"
        if not source.exists():
            raise FileNotFoundError(source)
        rows = read_rows(source, date_text)
        imported.extend(rows)
        gross = int(round(sum(row["grossSales"] for row in rows)))
        refunds = int(round(sum(row["refundAmount"] for row in rows)))
        net = int(round(sum(row["dailySales"] for row in rows)))
        orders = int(round(sum(row["orders"] for row in rows)))
        refund_orders = int(round(sum(row["refundOrders"] for row in rows)))
        weeks[week_index(day)] += net
        gross_total += gross; refunds_total += refunds; orders_total += orders
        dashboard_day = daily_by_date[date_text]
        stores = [store for store in dashboard_day["stores"] if "무라" not in (store.get("name") or "")]
        stores.append({"name": STORE_NAME, "store": STORE_NAME, "grossSales": gross,
            "refunds": refunds, "netSales": net, "orders": orders, "refundOrders": refund_orders,
            "source": source.name, "basis": "스마트스토어 판매성과 상품별 합계의 판매금액(순)"})
        dashboard_day["stores"] = stores
        dashboard_day["totalGrossSales"] = sum(int(s.get("grossSales") or 0) for s in stores)
        dashboard_day["totalRefunds"] = sum(int(s.get("refunds") or 0) for s in stores)
        dashboard_day["totalNetSales"] = sum(int(s.get("netSales") or 0) for s in stores)
        dashboard_day["netSales"] = dashboard_day["totalNetSales"]
    section["rows"] = sorted(kept + imported,
        key=lambda row: (row["date"], row["store"], -number(row["dailySales"])))
    section["count"] = len(section["rows"])
    section["totals"] = {"adSales": 0.0, "adCost": 0.0,
        "dailySales": sum(number(row["dailySales"]) for row in section["rows"]),
        "orders": sum(number(row["orders"]) for row in section["rows"]),
        "roas": 0, "adCostRate": 0, "adProfit": 0}
    section["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    metrics = data["totalSalesMetrics"]
    metrics["dailySales"] = [daily_by_date[key] for key in sorted(daily_by_date)]
    metrics["dailySalesTotals"] = [{"date": row["date"], "netSales": row["totalNetSales"]} for row in metrics["dailySales"]]
    auto = [row for row in metrics["autoSales"] if "무라" not in row.get("name", "")]
    auto.append({"name": "무라", "weeks": weeks, "total": sum(weeks)})
    metrics["autoSales"] = auto
    total_weeks = [sum(int(row["weeks"][i] or 0) for row in auto) for i in range(5)]
    metrics["autoSalesTotal"] = {"name": "자동 매출 합계", "weeks": total_weeks, "total": sum(total_weeks)}
    data.setdefault("dataProfile", {})["muraSalesMemo"] = f"{args.month}-01 ~ {args.month}-{day_count:02d} 스마트스토어 상품성과 기준"
    data["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    target.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"files": day_count, "rows": len(imported), "grossSales": gross_total,
        "refunds": refunds_total, "netSales": sum(weeks), "orders": orders_total,
        "weeks": weeks}, ensure_ascii=False))


if __name__ == "__main__":
    main()
