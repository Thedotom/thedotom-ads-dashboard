import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import openpyxl


SOURCE = Path(r"C:\Users\user\Downloads\sales_20260710-20260718_d05cca3a-3b14-4b9f-a0df-200688e83085.xlsx")
REPORT_ROOT = Path(r"D:\광고보고서")
ARCHIVE_DIR = REPORT_ROOT / "data" / "smartstore_sales_summary"
DATA_DIRS = [
    REPORT_ROOT / "public_dashboard" / "data",
    Path(r"C:\Users\user\Documents\New project 4\public_dashboard\data"),
]
TARGET_FILES = ["monthly-dashboard-2026-07.json", "monthly-dashboard-latest.json"]
STORE_NAME = "스마트스토어(무라)"
AUTO_NAME = "무라스토어"
START_DATE = "2026-07-10"
END_DATE = "2026-07-18"


def repair_text(value):
    text = str(value or "")
    try:
        return text.encode("latin1").decode("euc-kr")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def all_dates():
    current = datetime.strptime(START_DATE, "%Y-%m-%d")
    end = datetime.strptime(END_DATE, "%Y-%m-%d")
    result = []
    while current <= end:
        result.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return result


def read_rows():
    workbook = openpyxl.load_workbook(SOURCE, read_only=True, data_only=True)
    sheet = workbook["SALES"]
    raw_rows = list(sheet.iter_rows(values_only=True))
    headers = [repair_text(value) for value in raw_rows[0]]
    required = [
        "날짜", "대 카테고리", "중 카테고리", "소 카테고리",
        "상품결제건수", "환불건수", "판매금액(총)", "판매금액(순)", "환불금액",
    ]
    missing = [name for name in required if name not in headers]
    if missing:
        raise ValueError(f"Missing columns after encoding repair: {missing}")
    col = {name: headers.index(name) for name in required}
    by_date = {date: {"date": date, "grossSales": 0, "refunds": 0, "netSales": 0, "orders": 0, "refundOrders": 0} for date in all_dates()}
    for raw in raw_rows[1:]:
        categories = [repair_text(raw[col[name]]) for name in ["대 카테고리", "중 카테고리", "소 카테고리"]]
        if categories != ["전체", "전체", "전체"]:
            continue
        date = str(raw[col["날짜"]])[:10]
        if date not in by_date:
            raise ValueError(f"Unexpected date: {date}")
        by_date[date] = {
            "date": date,
            "grossSales": int(raw[col["판매금액(총)"]] or 0),
            "refunds": int(raw[col["환불금액"]] or 0),
            "netSales": int(raw[col["판매금액(순)"]] or 0),
            "orders": int(raw[col["상품결제건수"]] or 0),
            "refundOrders": int(raw[col["환불건수"]] or 0),
        }
    return [by_date[date] for date in all_dates()]


def week_index(date_text):
    day = int(date_text[-2:])
    if day <= 5:
        return 0
    if day <= 12:
        return 1
    if day <= 19:
        return 2
    if day <= 26:
        return 3
    return 4


def is_mura_store_name(name):
    text = str(name or "")
    return text == STORE_NAME or "무라" in text or "ë¬´ë¼" in text


def is_mura_auto_name(name):
    text = str(name or "")
    return text == AUTO_NAME or "무라" in text or "ë¬´ë¼" in text


def update_dashboard(path, imported_rows):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    metrics = data["totalSalesMetrics"]
    daily_by_date = {item["date"]: item for item in metrics.get("dailySales", [])}
    for row in imported_rows:
        day = daily_by_date.setdefault(row["date"], {"date": row["date"], "weekday": "", "stores": []})
        stores = [store for store in day.get("stores", []) if not is_mura_store_name(store.get("name") or store.get("store"))]
        stores.append({
            "name": STORE_NAME,
            "store": STORE_NAME,
            "grossSales": row["grossSales"],
            "refunds": row["refunds"],
            "netSales": row["netSales"],
            "orders": row["orders"],
            "refundOrders": row["refundOrders"],
            "source": SOURCE.name,
            "basis": "스마트스토어 카테고리 판매성과 전체/전체/전체 행 기준 판매금액(순); 미표시 날짜는 0원",
        })
        day["stores"] = stores
        day["totalGrossSales"] = sum(int(store.get("grossSales", 0)) for store in stores)
        day["totalRefunds"] = sum(int(store.get("refunds", 0)) for store in stores)
        day["totalNetSales"] = sum(int(store.get("netSales", 0)) for store in stores)
        day["netSales"] = day["totalNetSales"]

    metrics["dailySales"] = [daily_by_date[key] for key in sorted(daily_by_date)]
    metrics["dailySalesTotals"] = [{"date": day["date"], "netSales": day["totalNetSales"]} for day in metrics["dailySales"]]
    metrics["dailySalesUpdatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    mura_weeks = [0, 0, 0, 0, 0]
    for day in metrics["dailySales"]:
        for store in day.get("stores", []):
            if is_mura_store_name(store.get("name") or store.get("store")):
                store["name"] = STORE_NAME
                store["store"] = STORE_NAME
                mura_weeks[week_index(day["date"])] += int(store.get("netSales", 0))

    auto_sales = metrics.get("autoSales", [])
    auto_sales = [item for item in auto_sales if not is_mura_auto_name(item.get("name"))]
    auto_sales.append({"name": AUTO_NAME, "weeks": mura_weeks, "total": sum(mura_weeks)})
    metrics["autoSales"] = auto_sales
    combined_weeks = [0, 0, 0, 0, 0]
    for item in auto_sales:
        for index, value in enumerate(item.get("weeks", [])[:5]):
            combined_weeks[index] += float(value or 0)
    metrics["autoSalesTotal"] = {"name": "자동 매출 합계", "weeks": combined_weeks, "total": sum(combined_weeks)}
    revenue = data.setdefault("revenueMetrics", {})
    revenue["dailySales"] = metrics["dailySales"]
    revenue["dailySalesUpdatedAt"] = metrics["dailySalesUpdatedAt"]
    revenue["updatedAt"] = metrics["dailySalesUpdatedAt"]
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main():
    rows = read_rows()
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archived = ARCHIVE_DIR / SOURCE.name
    shutil.copy2(SOURCE, archived)
    updated = []
    for directory in DATA_DIRS:
        for filename in TARGET_FILES:
            path = directory / filename
            update_dashboard(path, rows)
            updated.append(str(path))
    print(json.dumps({
        "source": str(archived),
        "dates": [row["date"] for row in rows],
        "salesDates": [row["date"] for row in rows if row["netSales"]],
        "grossSales": sum(row["grossSales"] for row in rows),
        "refunds": sum(row["refunds"] for row in rows),
        "netSales": sum(row["netSales"] for row in rows),
        "orders": sum(row["orders"] for row in rows),
        "refundOrders": sum(row["refundOrders"] for row in rows),
        "updated": updated,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()


