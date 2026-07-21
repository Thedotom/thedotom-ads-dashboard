from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import openpyxl


SOURCE = Path(
    r"C:\Users\user\Downloads\sales_20260101-20260131_dbb571bd-80a1-424c-a5f1-51bd4d18bfef.xlsx"
)
TARGET = Path(__file__).resolve().parents[1] / "data" / "monthly-dashboard-2026-01.json"
STORE_NAME = "스마트스토어(더도톰스튜디오)"


def number(value) -> int:
    return int(round(float(value or 0)))


def week_index(date_text: str) -> int:
    day = int(date_text[-2:])
    return 0 if day <= 5 else 1 if day <= 12 else 2 if day <= 19 else 3 if day <= 26 else 4


def read_source() -> list[dict]:
    workbook = openpyxl.load_workbook(SOURCE, read_only=True, data_only=True)
    sheet = workbook["SALES"]
    rows = list(sheet.iter_rows(values_only=True))
    headers = list(rows[0])
    required = [
        "날짜",
        "대 카테고리",
        "상품결제건수",
        "환불건수",
        "판매금액(총)",
        "판매금액(순)",
        "환불금액",
    ]
    missing = [name for name in required if name not in headers]
    if missing:
        raise ValueError(f"missing columns: {missing}")
    index = {name: headers.index(name) for name in required}

    result = []
    for values in rows[1:]:
        if not values or values[index["대 카테고리"]] != "전체":
            continue
        date = str(values[index["날짜"]])[:10]
        if not date.startswith("2026-01-"):
            raise ValueError(f"unexpected date: {date}")
        gross = number(values[index["판매금액(총)"]])
        refunds = number(values[index["환불금액"]])
        net = number(values[index["판매금액(순)"]])
        if gross - refunds != net:
            raise ValueError(f"net sales mismatch on {date}")
        result.append(
            {
                "date": date,
                "grossSales": gross,
                "refunds": refunds,
                "netSales": net,
                "orders": number(values[index["상품결제건수"]]),
                "refundOrders": number(values[index["환불건수"]]),
            }
        )

    expected_dates = {f"2026-01-{day:02d}" for day in range(1, 32)}
    actual_dates = {row["date"] for row in result}
    if len(result) != 31 or actual_dates != expected_dates:
        raise ValueError("expected exactly one overall row for every day in January")
    return sorted(result, key=lambda row: row["date"])


def update_dashboard(imported_rows: list[dict]) -> None:
    data = json.loads(TARGET.read_text(encoding="utf-8-sig"))
    metrics = data["totalSalesMetrics"]
    daily_by_date = {item["date"]: item for item in metrics.get("dailySales", [])}

    for row in imported_rows:
        day = daily_by_date.setdefault(row["date"], {"date": row["date"], "weekday": "", "stores": []})
        stores = [
            store
            for store in day.get("stores", [])
            if "더도톰스튜디오" not in str(store.get("name") or store.get("store") or "")
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
                "source": SOURCE.name,
                "basis": "스마트스토어 판매성과 전체 행 기준 판매금액(순)",
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
    metrics["dailySalesUpdatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    studio_weeks = [0, 0, 0, 0, 0]
    for row in imported_rows:
        studio_weeks[week_index(row["date"])] += row["netSales"]

    auto_sales = [
        row for row in metrics.get("autoSales", []) if "더도톰스튜디오" not in str(row.get("name", ""))
    ]
    auto_sales.insert(0, {"name": "더도톰스튜디오", "weeks": studio_weeks, "total": sum(studio_weeks)})
    metrics["autoSales"] = auto_sales

    combined = [
        sum(float(row.get("weeks", [0] * 5)[index] or 0) for row in auto_sales)
        for index in range(5)
    ]
    metrics["autoSalesTotal"] = {
        "name": "자동 매출 합계",
        "weeks": combined,
        "total": sum(combined),
    }

    revenue = data.setdefault("revenueMetrics", {})
    revenue["dailySales"] = metrics["dailySales"]
    revenue["dailySalesUpdatedAt"] = metrics["dailySalesUpdatedAt"]
    revenue["updatedAt"] = metrics["dailySalesUpdatedAt"]
    TARGET.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main() -> None:
    rows = read_source()
    update_dashboard(rows)
    print(
        json.dumps(
            {
                "dates": [rows[0]["date"], rows[-1]["date"]],
                "days": len(rows),
                "grossSales": sum(row["grossSales"] for row in rows),
                "refunds": sum(row["refunds"] for row in rows),
                "netSales": sum(row["netSales"] for row in rows),
                "orders": sum(row["orders"] for row in rows),
                "refundOrders": sum(row["refundOrders"] for row in rows),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
