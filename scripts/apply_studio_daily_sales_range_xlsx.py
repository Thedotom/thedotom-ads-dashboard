from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

import openpyxl


SOURCE = Path(sys.argv[1])
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
STORE_NAME = "스마트스토어(더도톰스튜디오)"
AUTO_NAME = "더도톰스튜디오"
STORE_MARKER = "더도톰스튜디오"


def number(value):
    return int(round(float(value or 0)))


def repair_text(value):
    if not isinstance(value, str):
        return value
    try:
        return value.encode("latin1").decode("cp949")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


def read_daily_rows():
    workbook = openpyxl.load_workbook(SOURCE, read_only=True, data_only=True)
    sheet = workbook["SALES"]
    values = list(sheet.iter_rows(values_only=True))
    headers = [repair_text(value) for value in values[0]]
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
        raise ValueError(f"Missing columns: {missing}")
    col = {name: headers.index(name) for name in required}

    rows = []
    all_rows = {}
    for raw in values[1:]:
        date_text = str(raw[col["날짜"]])[:10]
        channel = str(repair_text(raw[col["채널"]]) or "")
        payload = {
            "date": date_text,
            "grossSales": number(raw[col["판매금액(총)"]]),
            "refunds": number(raw[col["환불금액"]]),
            "netSales": number(raw[col["판매금액(순)"]]),
            "orders": number(raw[col["상품결제건수"]]),
            "refundOrders": number(raw[col["환불건수"]]),
        }
        if channel == "전체":
            all_rows[date_text] = payload
        elif STORE_MARKER in channel:
            rows.append(payload)

    if len(rows) != 31 or len({row["date"] for row in rows}) != 31:
        raise ValueError(f"Expected 31 unique Studio dates, found {len(rows)} rows")
    for row in rows:
        if row["grossSales"] - row["refunds"] != row["netSales"]:
            raise ValueError(f"Net sales mismatch: {row}")
        total = all_rows.get(row["date"])
        if total and any(total[key] != row[key] for key in ("grossSales", "refunds", "netSales")):
            raise ValueError(f"Store row does not match total row on {row['date']}")
    return sorted(rows, key=lambda row: row["date"])


def week_index(day, week_labels):
    for index, label in enumerate(week_labels):
        match = re.search(r"\((\d+)~(\d+)\)", str(label))
        if match and int(match.group(1)) <= day <= int(match.group(2)):
            return index
    raise ValueError(f"No weekly bucket for day {day}")


def update_dashboard(rows):
    month = rows[0]["date"][:7]
    path = DATA_DIR / f"monthly-dashboard-{month}.json"
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    metrics = data.setdefault("totalSalesMetrics", {})
    daily_by_date = {item["date"]: item for item in metrics.get("dailySales", [])}

    for row in rows:
        day = daily_by_date.setdefault(
            row["date"], {"date": row["date"], "weekday": "", "stores": []}
        )
        stores = [
            store
            for store in day.get("stores", [])
            if str(store.get("name", "")).lower()
            not in {STORE_NAME.lower(), "더도톰스튜디오", "thedotom", "studio"}
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
                "basis": "스마트스토어 판매 리포트 채널 일별 판매금액(순)",
            }
        )
        day["stores"] = stores
        day["totalGrossSales"] = sum(number(store.get("grossSales")) for store in stores)
        day["totalRefunds"] = sum(number(store.get("refunds")) for store in stores)
        day["totalNetSales"] = sum(number(store.get("netSales")) for store in stores)
        day["netSales"] = day["totalNetSales"]

    metrics["dailySales"] = [daily_by_date[key] for key in sorted(daily_by_date)]
    metrics["dailySalesTotals"] = [
        {"date": day["date"], "netSales": day["totalNetSales"]}
        for day in metrics["dailySales"]
    ]

    weeks = [0] * len(metrics.get("weeks", []))
    for row in rows:
        weeks[week_index(int(row["date"][-2:]), metrics["weeks"])] += row["netSales"]
    auto_sales = [
        item for item in metrics.get("autoSales", []) if item.get("name") != AUTO_NAME
    ]
    auto_sales.append({"name": AUTO_NAME, "weeks": weeks, "total": sum(weeks)})
    metrics["autoSales"] = auto_sales
    total_weeks = [
        sum(number(item.get("weeks", [0] * len(weeks))[index]) for item in auto_sales)
        for index in range(len(weeks))
    ]
    metrics["autoSalesTotal"] = {
        "name": "자동 매출 합계",
        "weeks": total_weeks,
        "total": sum(total_weeks),
    }

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    metrics["dailySalesBasis"] = "채널별 일일 판매금액(순), 확인된 원본 기준"
    metrics["dailySalesUpdatedAt"] = stamp
    revenue = data.setdefault("revenueMetrics", {})
    revenue["dailySales"] = metrics["dailySales"]
    revenue["basis"] = metrics["dailySalesBasis"]
    revenue["updatedAt"] = stamp
    data["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    path.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    return path


def main():
    rows = read_daily_rows()
    target = update_dashboard(rows)
    print(
        json.dumps(
            {
                "source": str(SOURCE),
                "target": str(target),
                "dates": len(rows),
                "grossSales": sum(row["grossSales"] for row in rows),
                "refunds": sum(row["refunds"] for row in rows),
                "netSales": sum(row["netSales"] for row in rows),
                "orders": sum(row["orders"] for row in rows),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
