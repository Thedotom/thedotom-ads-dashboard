from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import openpyxl


MONTH = "2026-02"
TARGET = Path(__file__).resolve().parents[1] / "data" / "monthly-dashboard-2026-02.json"
SOURCES = {
    "thedotom": {
        "path": Path(
            r"C:\Users\user\Downloads\sales_20260201-20260228_d23db4bd-1598-4287-a635-8c774efbe5b3.xlsx"
        ),
        "name": "스마트스토어(더도톰스튜디오)",
        "monthlyName": "더도톰스튜디오",
    },
    "mura": {
        "path": Path(
            r"C:\Users\user\Downloads\sales_20260201-20260228_58a0e79e-9ecd-42b1-a132-9797dd7cc17d.xlsx"
        ),
        "name": "스마트스토어(무라)",
        "monthlyName": "무라",
    },
}


def number(value) -> int:
    return int(round(float(value or 0)))


def expected_dates() -> list[str]:
    return [f"{MONTH}-{day:02d}" for day in range(1, 29)]


def week_index(date_text: str) -> int:
    day = int(date_text[-2:])
    if day <= 8:
        return 0
    if day <= 15:
        return 1
    if day <= 22:
        return 2
    return 3


def read_source(path: Path) -> list[dict]:
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = workbook["SALES"]
    rows = sheet.iter_rows(values_only=True)
    headers = list(next(rows))
    required = [
        "날짜",
        "채널",
        "상품결제건수",
        "환불건수",
        "판매금액(총)",
        "판매금액(순)",
        "환불금액",
    ]
    missing = [name for name in required if name not in headers]
    if missing:
        raise ValueError(f"{path.name}: missing columns: {missing}")
    index = {name: headers.index(name) for name in required}

    by_date: dict[str, dict] = {}
    for values in rows:
        if not values or values[index["채널"]] != "전체":
            continue
        date = str(values[index["날짜"]])[:10]
        if not date.startswith(f"{MONTH}-"):
            raise ValueError(f"{path.name}: unexpected date: {date}")
        if date in by_date:
            raise ValueError(f"{path.name}: duplicate overall row: {date}")
        gross = number(values[index["판매금액(총)"]])
        refunds = number(values[index["환불금액"]])
        net = number(values[index["판매금액(순)"]])
        if gross - refunds != net:
            raise ValueError(f"{path.name}: net sales mismatch on {date}")
        by_date[date] = {
            "date": date,
            "grossSales": gross,
            "refunds": refunds,
            "netSales": net,
            "orders": number(values[index["상품결제건수"]]),
            "refundOrders": number(values[index["환불건수"]]),
        }

    unexpected = sorted(set(by_date) - set(expected_dates()))
    if unexpected:
        raise ValueError(f"{path.name}: unexpected February dates: {unexpected}")
    return [
        by_date.get(
            date,
            {
                "date": date,
                "grossSales": 0,
                "refunds": 0,
                "netSales": 0,
                "orders": 0,
                "refundOrders": 0,
            },
        )
        for date in expected_dates()
    ]


def product_totals(data: dict, store: str) -> dict[str, dict]:
    result = {
        date: {"grossSales": 0, "refunds": 0, "netSales": 0, "orders": 0}
        for date in expected_dates()
    }
    for item in data.get("dailyProductPerformance", {}).get("rows", []):
        if str(item.get("store", "")).lower() != store:
            continue
        date = str(item.get("date", ""))[:10]
        if date not in result:
            continue
        result[date]["grossSales"] += number(item.get("grossSales"))
        result[date]["refunds"] += number(item.get("refundAmount"))
        result[date]["netSales"] += number(item.get("dailySales"))
        result[date]["orders"] += number(item.get("orders"))
    return result


def validate_product_reconciliation(data: dict, store: str, source_rows: list[dict]) -> None:
    products = product_totals(data, store)
    mismatches = []
    for row in source_rows:
        date = row["date"]
        for field in ("grossSales", "refunds", "netSales", "orders"):
            if row[field] != products[date][field]:
                mismatches.append(
                    {
                        "date": date,
                        "field": field,
                        "salesFile": row[field],
                        "productPerformance": products[date][field],
                    }
                )
    if mismatches:
        raise ValueError(
            f"{store}: sales file and daily product performance differ: "
            + json.dumps(mismatches[:10], ensure_ascii=False)
        )


def update_dashboard(data: dict, imported: dict[str, list[dict]]) -> None:
    metrics = data.setdefault("totalSalesMetrics", {})
    daily_by_date = {item["date"]: item for item in metrics.get("dailySales", [])}

    for store_key, rows in imported.items():
        config = SOURCES[store_key]
        for row in rows:
            day = daily_by_date.setdefault(
                row["date"], {"date": row["date"], "weekday": "", "stores": []}
            )
            stores = [
                item
                for item in day.get("stores", [])
                if config["name"] not in str(item.get("name") or item.get("store") or "")
                and config["monthlyName"]
                not in str(item.get("name") or item.get("store") or "")
            ]
            stores.append(
                {
                    "name": config["name"],
                    "store": config["name"],
                    "grossSales": row["grossSales"],
                    "refunds": row["refunds"],
                    "netSales": row["netSales"],
                    "orders": row["orders"],
                    "refundOrders": row["refundOrders"],
                    "source": config["path"].name,
                    "basis": "네이버 스마트스토어 판매성과 전체 채널 판매금액(순)",
                }
            )
            day["stores"] = stores
            day["totalGrossSales"] = sum(number(item.get("grossSales")) for item in stores)
            day["totalRefunds"] = sum(number(item.get("refunds")) for item in stores)
            day["totalNetSales"] = sum(number(item.get("netSales")) for item in stores)
            day["netSales"] = day["totalNetSales"]

    metrics["dailySales"] = [daily_by_date[date] for date in sorted(daily_by_date)]
    metrics["dailySalesTotals"] = [
        {"date": day["date"], "netSales": day["totalNetSales"]}
        for day in metrics["dailySales"]
    ]

    existing_auto_sales = metrics.get("autoSales", [])
    if isinstance(existing_auto_sales, dict):
        existing_auto_sales = [existing_auto_sales]
    smartstore_names = {config["monthlyName"] for config in SOURCES.values()}
    auto_sales = [
        row for row in existing_auto_sales if str(row.get("name", "")) not in smartstore_names
    ]
    for store_key, rows in imported.items():
        weeks = [0, 0, 0, 0, 0]
        for row in rows:
            weeks[week_index(row["date"])] += row["netSales"]
        auto_sales.append(
            {
                "name": SOURCES[store_key]["monthlyName"],
                "weeks": weeks,
                "total": sum(weeks),
            }
        )
    metrics["autoSales"] = auto_sales
    combined = [
        sum(number(row.get("weeks", [0] * 5)[index]) for row in auto_sales)
        for index in range(5)
    ]
    metrics["autoSalesTotal"] = {
        "name": "매출 합계",
        "weeks": combined,
        "total": sum(combined),
    }

    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    metrics["dailySalesBasis"] = (
        "자사몰은 Cafe24 일매출 CSV, 스마트스토어는 네이버 판매성과 전체 채널 판매금액(순)"
    )
    metrics["dailySalesUpdatedAt"] = updated_at
    revenue = data.setdefault("revenueMetrics", {})
    revenue["dailySales"] = metrics["dailySales"]
    revenue["basis"] = metrics["dailySalesBasis"]
    revenue["updatedAt"] = updated_at
    revenue["note"] = "자사몰·더도톰스튜디오·무라의 확인된 일별 순매출 합계"


def summary(rows: list[dict]) -> dict:
    return {
        "days": len(rows),
        "grossSales": sum(row["grossSales"] for row in rows),
        "refunds": sum(row["refunds"] for row in rows),
        "netSales": sum(row["netSales"] for row in rows),
        "orders": sum(row["orders"] for row in rows),
        "refundOrders": sum(row["refundOrders"] for row in rows),
    }


def main() -> None:
    data = json.loads(TARGET.read_text(encoding="utf-8-sig"))
    imported = {
        store: read_source(config["path"]) for store, config in SOURCES.items()
    }
    for store, rows in imported.items():
        validate_product_reconciliation(data, store, rows)
    update_dashboard(data, imported)
    TARGET.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "stores": {store: summary(rows) for store, rows in imported.items()},
                "autoSales": data["totalSalesMetrics"]["autoSales"],
                "autoSalesTotal": data["totalSalesMetrics"]["autoSalesTotal"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
