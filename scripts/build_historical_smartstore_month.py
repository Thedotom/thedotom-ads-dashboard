from __future__ import annotations

import argparse
import json
from calendar import monthrange
from datetime import datetime
from pathlib import Path

import openpyxl


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEFAULT_SOURCE_DIR = Path(r"D:\광고보고서\data\smartstore_sales")
STORE_NAME = "스마트스토어(더도톰스튜디오)"


def number(value):
    return float(value or 0)


def week_index(day: int) -> int:
    return 0 if day <= 5 else 1 if day <= 12 else 2 if day <= 19 else 3 if day <= 26 else 4


def read_rows(path: Path, expected_date: str):
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True)["SALES"]
    values = list(ws.iter_rows(values_only=True))
    if not values:
        raise ValueError(f"Empty workbook: {path}")
    headers = list(values[0])
    required = [
        "날짜", "채널상품명", "채널상품번호", "상품결제건수", "환불건수",
        "판매금액(총)", "판매금액(순)", "환불금액", "결제상품수량", "환불상품수량",
    ]
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
        rows.append({
            "recordId": product_id, "date": expected_date, "store": "thedotom",
            "storeName": STORE_NAME, "productId": product_id, "productName": name,
            "product": name, "adgroup": "", "adSales": 0.0, "adCost": 0.0,
            "impressions": 0.0, "clicks": 0.0, "conversions": 0.0,
            "status": "자연", "memo": "정상 운영", "dailySales": net,
            "orders": number(raw[col["상품결제건수"]]), "refundAmount": refunds,
            "roas": 0.0, "adCostRate": 0.0, "adProfit": 0.0, "source": path.name,
            "grossSales": gross, "quantity": number(raw[col["결제상품수량"]]),
            "refundQuantity": number(raw[col["환불상품수량"]]),
            "refundOrders": number(raw[col["환불건수"]]),
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", required=True)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    args = parser.parse_args()
    year, month_no = map(int, args.month.split("-"))
    days = monthrange(year, month_no)[1]
    all_rows = []
    daily = []
    weeks = [0, 0, 0, 0, 0]
    gross_total = refunds_total = orders_total = 0
    for day in range(1, days + 1):
        date_text = f"{args.month}-{day:02d}"
        source = args.source_dir / f"smartstore_product_sales_thedotom_{date_text}.xlsx"
        if not source.exists():
            raise FileNotFoundError(source)
        rows = read_rows(source, date_text)
        all_rows.extend(rows)
        gross = int(round(sum(row["grossSales"] for row in rows)))
        refunds = int(round(sum(row["refundAmount"] for row in rows)))
        net = int(round(sum(row["dailySales"] for row in rows)))
        orders = int(round(sum(row["orders"] for row in rows)))
        refund_orders = int(round(sum(row["refundOrders"] for row in rows)))
        if gross - refunds != net:
            raise ValueError(f"Daily net mismatch: {date_text}")
        weeks[week_index(day)] += net
        gross_total += gross
        refunds_total += refunds
        orders_total += orders
        daily.append({
            "date": date_text, "weekday": "", "stores": [{
                "name": STORE_NAME, "store": STORE_NAME, "grossSales": gross,
                "refunds": refunds, "netSales": net, "orders": orders,
                "refundOrders": refund_orders, "source": source.name,
                "basis": "스마트스토어 판매성과 상품별 합계의 판매금액(순)",
            }], "totalGrossSales": gross, "totalRefunds": refunds,
            "totalNetSales": net, "netSales": net,
        })

    available = json.loads((DATA_DIR / "months.json").read_text(encoding="utf-8-sig"))["months"]
    if args.month not in available:
        available.append(args.month)
        available.sort(reverse=True)
    month_label = f"{month_no}월"
    week_labels = [
        f"{month_label}1주차(1~5)", f"{month_label}2주차(6~12)",
        f"{month_label}3주차(13~19)", f"{month_label}4주차(20~26)",
        f"{month_label}5주차(27~{days})",
    ]
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    data = {
        "updatedAt": stamp, "month": args.month, "availableMonths": available,
        "reportPath": "", "draftPath": "", "monthly": [], "typePerformance": [],
        "campaigns": [], "adgroups": [], "keywordPerformance": [], "inspection": [],
        "plan": [], "state": {"notes": {}, "planMemo": "", "reportMemo": ""},
        "summary": {"adCost": 0, "revenue": 0, "roas": 0, "clicks": 0,
                    "conversions": 0, "ctr": 0, "cpc": 0, "inspectionCount": 0},
        "dataProfile": {"source": "smartstore-sales-only",
            "period": f"{args.month}-01 - {args.month}-{days:02d}",
            "memo": "더도톰 스마트스토어 판매성과 상품별 순매출을 반영한 월입니다."},
        "brandContract": {}, "rewardMarketing": {"items": [], "activeItems": [], "completedItems": []},
        "shoppingIntegrated": {"adCost": 0, "clicks": 0, "conversions": 0, "revenue": 0,
                               "rewardCost": 0, "blendedRoas": 0},
        "rankTraffic": {"dates": [], "slots": [], "shoppingRows": [],
                        "powerlinkPcRows": [], "powerlinkMobileRows": []},
        "dailyProductCosts": {"dates": [], "items": [], "summary": "광고 원본 데이터가 없습니다."},
        "totalSalesMetrics": {"weeks": week_labels, "availableMonths": [args.month],
            "manualSales": [], "manualSalesTotal": {"name": "수기 매출 합계", "weeks": [0]*5, "total": 0},
            "manualAdCosts": [], "manualAdCostTotal": {"name": "수기 광고비 합계", "weeks": [0]*5, "total": 0},
            "autoSales": [{"name": "더도톰스튜디오", "weeks": weeks, "total": sum(weeks)}],
            "autoSalesTotal": {"name": "자동 매출 합계", "weeks": weeks, "total": sum(weeks)},
            "autoAdCosts": [], "autoAdCostTotal": {"name": "자동 광고비 합계", "weeks": [0]*5, "total": 0},
            "dailySales": daily,
            "dailySalesTotals": [{"date": row["date"], "netSales": row["netSales"]} for row in daily]},
        "dailyProductPerformance": {"rows": all_rows,
            "totals": {"adSales": 0.0, "adCost": 0.0, "dailySales": sum(weeks),
                       "orders": orders_total, "roas": 0, "adCostRate": 0, "adProfit": 0},
            "dateLabel": f"{args.month}-01 ~ {args.month}-{days:02d}",
            "count": len(all_rows), "summary": "스마트스토어 상품별 판매성과 기준입니다.",
            "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        "accountPerformance": [], "displayAdvertising": {}, "slotEfficiency": {},
    }
    target = DATA_DIR / f"monthly-dashboard-{args.month}.json"
    target.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    months_payload = {"months": available, "availableMonths": available, "latest": available[0]}
    (DATA_DIR / "months.json").write_text(json.dumps(months_payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"files": days, "rows": len(all_rows), "grossSales": gross_total,
                      "refunds": refunds_total, "netSales": sum(weeks), "orders": orders_total,
                      "weeks": weeks}, ensure_ascii=False))


if __name__ == "__main__":
    main()
