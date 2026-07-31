from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

import openpyxl


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SOURCE_DIR = Path(r"D:\광고보고서\data\smartstore_sales")
STORES = {
    "studio": {
        "file": "thedotom",
        "store": "thedotom",
        "storeName": "스마트스토어(더도톰스튜디오)",
        "aliases": {"thedotom", "thedotom_studio"},
    },
    "mura": {
        "file": "mura",
        "store": "mura",
        "storeName": "스마트스토어(무라)",
        "aliases": {"mura", "mura_store"},
    },
}
REQUIRED_COLUMNS = [
    "날짜",
    "채널상품명",
    "채널상품번호",
    "상품결제건수",
    "환불건수",
    "판매금액(총)",
    "판매금액(순)",
    "환불금액",
    "결제상품수량",
    "환불상품수량",
]


def number(value):
    return float(value or 0)


def dates(start_date, end_date):
    current = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    while current <= end:
        yield current.isoformat()
        current += timedelta(days=1)


def read_rows(path, expected_date, config):
    sheet = openpyxl.load_workbook(path, read_only=True, data_only=True)["SALES"]
    values = list(sheet.iter_rows(values_only=True))
    if not values:
        raise ValueError(f"Empty workbook: {path}")
    headers = list(values[0])
    missing = [name for name in REQUIRED_COLUMNS if name not in headers]
    if missing:
        raise ValueError(f"Missing columns in {path.name}: {missing}")
    col = {name: headers.index(name) for name in REQUIRED_COLUMNS}
    rows = []
    for raw in values[1:]:
        product_id = str(raw[col["채널상품번호"]] or "").strip()
        if not product_id or product_id == "전체":
            continue
        date_text = str(raw[col["날짜"]])[:10]
        if date_text != expected_date:
            raise ValueError(
                f"Unexpected date in {path.name}: {date_text} != {expected_date}"
            )
        name = str(raw[col["채널상품명"]] or "").strip()
        gross_sales = number(raw[col["판매금액(총)"]])
        refunds = number(raw[col["환불금액"]])
        net_sales = number(raw[col["판매금액(순)"]])
        if round(gross_sales - refunds, 6) != round(net_sales, 6):
            raise ValueError(
                f"Net sales mismatch in {path.name} for {product_id}: "
                f"{gross_sales} - {refunds} != {net_sales}"
            )
        rows.append(
            {
                "recordId": product_id,
                "date": expected_date,
                "store": config["store"],
                "storeName": config["storeName"],
                "productId": product_id,
                "productName": name,
                "product": name,
                "adgroup": "",
                "adSales": 0.0,
                "adCost": 0.0,
                "impressions": 0.0,
                "clicks": 0.0,
                "conversions": 0.0,
                "status": "자연",
                "memo": "정상 운영",
                "dailySales": net_sales,
                "orders": number(raw[col["상품결제건수"]]),
                "refundAmount": refunds,
                "roas": 0.0,
                "adCostRate": 0.0,
                "adProfit": 0.0,
                "source": path.name,
                "grossSales": gross_sales,
                "quantity": number(raw[col["결제상품수량"]]),
                "refundQuantity": number(raw[col["환불상품수량"]]),
                "refundOrders": number(raw[col["환불건수"]]),
            }
        )
    return rows


def refresh(section):
    rows = section.get("rows", [])
    section["count"] = len(rows)
    row_dates = sorted({row.get("date") for row in rows if row.get("date")})
    section["dateLabel"] = (
        f"{row_dates[0]} ~ {row_dates[-1]}" if row_dates else ""
    )
    section["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    totals = {
        key: sum(number(row.get(key)) for row in rows)
        for key in ["adSales", "adCost", "dailySales", "orders"]
    }
    totals["roas"] = totals["adSales"] / totals["adCost"] if totals["adCost"] else 0
    totals["adCostRate"] = (
        totals["adCost"] / totals["dailySales"] if totals["dailySales"] else 0
    )
    totals["adProfit"] = totals["adSales"] - totals["adCost"]
    section["totals"] = totals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--store", choices=["studio", "mura", "all"], default="all")
    parser.add_argument("--source-dir", type=Path, default=SOURCE_DIR)
    args = parser.parse_args()

    if args.start_date[:7] != args.end_date[:7]:
        raise ValueError("Date range must stay within one month")
    month = args.start_date[:7]
    target = DATA_DIR / f"monthly-dashboard-{month}.json"
    if not target.exists():
        raise FileNotFoundError(target)

    store_keys = list(STORES) if args.store == "all" else [args.store]
    all_rows = []
    file_counts = {key: 0 for key in store_keys}
    for store_key in store_keys:
        config = STORES[store_key]
        for date_text in dates(args.start_date, args.end_date):
            path = (
                args.source_dir
                / f"smartstore_product_sales_{config['file']}_{date_text}.xlsx"
            )
            if not path.exists():
                raise FileNotFoundError(path)
            file_counts[store_key] += 1
            all_rows.extend(read_rows(path, date_text, config))

    data = json.loads(target.read_text(encoding="utf-8-sig"))
    section = data.setdefault("dailyProductPerformance", {"rows": []})
    target_dates = set(dates(args.start_date, args.end_date))
    aliases = set().union(*(STORES[key]["aliases"] for key in store_keys))
    kept = [
        row
        for row in section.get("rows", [])
        if not (
            str(row.get("date", ""))[:10] in target_dates
            and str(row.get("store", "")).lower() in aliases
        )
    ]
    section["rows"] = sorted(
        kept + all_rows,
        key=lambda row: (
            str(row.get("date", "")),
            str(row.get("store", "")),
            -number(row.get("dailySales")),
        ),
    )
    refresh(section)
    data["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    target.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    summary = {}
    for store_key in store_keys:
        store = STORES[store_key]["store"]
        rows = [row for row in all_rows if row["store"] == store]
        summary[store_key] = {
            "files": file_counts[store_key],
            "rows": len(rows),
            "grossSales": sum(row["grossSales"] for row in rows),
            "refunds": sum(row["refundAmount"] for row in rows),
            "netSales": sum(row["dailySales"] for row in rows),
            "quantity": sum(row["quantity"] for row in rows),
        }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
