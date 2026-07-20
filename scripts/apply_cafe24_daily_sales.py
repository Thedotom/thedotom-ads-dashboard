import csv
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path


SOURCE = Path(sys.argv[1])
REPORT_ROOT = Path(r"D:\광고보고서")
ARCHIVE_DIR = REPORT_ROOT / "data" / "cafe24_sales"
DATA_DIRS = [REPORT_ROOT / "public_dashboard" / "data", Path(r"C:\Users\user\Documents\New project 4\public_dashboard\data")]
TARGET_FILES = ["monthly-dashboard-2026-07.json", "monthly-dashboard-latest.json"]
STORE_NAME = "카페24(자사몰)"
AUTO_NAME = "자사몰 자동수집"


def integer(value):
    return int(float(str(value or "0").replace(",", "")))


def read_rows():
    rows = list(csv.reader(SOURCE.read_text(encoding="utf-8-sig").splitlines()))
    header_index = next(i for i, row in enumerate(rows) if row and row[0] == "일자")
    headers = rows[header_index]
    required = ["일자", "주문수", "품목수", "결제합계", "환불합계", "순매출"]
    col = {name: headers.index(name) for name in required}
    result = []
    for raw in rows[header_index + 1:]:
        if not raw:
            continue
        match = re.match(r"(\d{4}-\d{2}-\d{2})", raw[col["일자"]])
        if not match:
            continue
        gross = integer(raw[col["결제합계"]])
        refunds = integer(raw[col["환불합계"]])
        net = integer(raw[col["순매출"]])
        if gross - refunds != net:
            raise ValueError(f"Sales equation mismatch on {match.group(1)}")
        result.append({"date": match.group(1), "grossSales": gross, "refunds": refunds, "netSales": net, "orders": integer(raw[col["주문수"]]), "items": integer(raw[col["품목수"]])})
    if not result:
        raise ValueError("No daily rows found")
    return result


def week_index(date_text):
    day = int(date_text[-2:])
    return 0 if day <= 5 else 1 if day <= 12 else 2 if day <= 19 else 3 if day <= 26 else 4


def update(path, imported):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    metrics = data["totalSalesMetrics"]
    by_date = {item["date"]: item for item in metrics.get("dailySales", [])}
    for row in imported:
        day = by_date.setdefault(row["date"], {"date": row["date"], "weekday": "", "stores": []})
        stores = [item for item in day.get("stores", []) if item.get("name") != STORE_NAME]
        stores.append({"name": STORE_NAME, "store": STORE_NAME, "grossSales": row["grossSales"], "refunds": row["refunds"], "netSales": row["netSales"], "orders": row["orders"], "items": row["items"], "source": SOURCE.name, "basis": "Cafe24 DailyList 결제합계 - 환불합계 = 순매출"})
        day["stores"] = stores
        day["totalGrossSales"] = sum(int(item.get("grossSales", 0)) for item in stores)
        day["totalRefunds"] = sum(int(item.get("refunds", 0)) for item in stores)
        day["totalNetSales"] = sum(int(item.get("netSales", 0)) for item in stores)
        day["netSales"] = day["totalNetSales"]
    metrics["dailySales"] = [by_date[key] for key in sorted(by_date)]
    metrics["dailySalesTotals"] = [{"date": item["date"], "netSales": item["totalNetSales"]} for item in metrics["dailySales"]]
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    metrics["dailySalesUpdatedAt"] = stamp

    weeks = [0, 0, 0, 0, 0]
    for day in metrics["dailySales"]:
        for store in day.get("stores", []):
            if store.get("name") == STORE_NAME:
                weeks[week_index(day["date"])] += int(store.get("netSales", 0))
    auto = metrics.get("autoSales", [])
    target = next((item for item in auto if item.get("name") == AUTO_NAME), None)
    if target is None:
        target = {"name": AUTO_NAME}
        auto.append(target)
    target["weeks"], target["total"] = weeks, sum(weeks)
    metrics["autoSales"] = auto
    combined = [sum(float(item.get("weeks", [0] * 5)[i] or 0) for item in auto if i < len(item.get("weeks", []))) for i in range(5)]
    metrics["autoSalesTotal"] = {"name": "자동 매출 합계", "weeks": combined, "total": sum(combined)}
    revenue = data.setdefault("revenueMetrics", {})
    revenue["dailySales"] = metrics["dailySales"]
    revenue["dailySalesUpdatedAt"] = stamp
    revenue["updatedAt"] = stamp
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main():
    rows = read_rows()
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE, ARCHIVE_DIR / SOURCE.name)
    for directory in DATA_DIRS:
        for filename in TARGET_FILES:
            update(directory / filename, rows)
    print(json.dumps({"dates": [row["date"] for row in rows], "grossSales": sum(row["grossSales"] for row in rows), "refunds": sum(row["refunds"] for row in rows), "netSales": sum(row["netSales"] for row in rows), "orders": sum(row["orders"] for row in rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
