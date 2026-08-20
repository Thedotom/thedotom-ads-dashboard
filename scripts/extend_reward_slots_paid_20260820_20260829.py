from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TARGETS = (
    DATA / "monthly-dashboard-2026-08.json",
    DATA / "monthly-dashboard-latest.json",
)
START_DATE = "2026-08-20"
END_DATE = "2026-08-29"
TOTAL_COST = 1_320_000
PRODUCT_COSTS = {
    "4624494637": 440_000,
    "4843121925": 660_000,
    "12924495111": 220_000,
}
MEMO = "동일 상품 3개 리워드 슬롯 유료 연장 (2026-08-19 결제 요청)"


def update_reward_marketing(data: dict) -> None:
    reward = data.setdefault("rewardMarketing", {})
    items = [
        item
        for item in reward.get("items", [])
        if str(item.get("productId")) in PRODUCT_COSTS
    ]
    if len(items) != 3:
        raise RuntimeError(f"expected 3 reward products, found {len(items)}")

    for item in items:
        periods = item.setdefault("slotPeriods", [])
        period = next(
            (
                row
                for row in periods
                if row.get("startDate") == START_DATE
                and row.get("endDate") == END_DATE
            ),
            None,
        )
        values = {
            "startDate": START_DATE,
            "endDate": END_DATE,
            "cost": TOTAL_COST,
            "type": "paid",
            "memo": MEMO,
        }
        if period is None:
            periods.append(values)
        else:
            period.update(values)
        item["endDate"] = END_DATE
        item["status"] = "active"
        item["memo"] = MEMO

    reward["items"] = items
    reward["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    reward["note"] = (
        "동일 상품 3개 리워드 슬롯 2026-08-20~2026-08-29 유료 연장 운영 "
        "(2026-08-19 요청, 총 1,320,000원)"
    )


def update_slot_efficiency(data: dict) -> None:
    efficiency = data.get("slotEfficiency")
    if not isinstance(efficiency, dict):
        return
    periods = efficiency.setdefault("periods", [])
    previous = {
        str(row.get("productId")): row
        for row in periods
        if row.get("startDate") == "2026-08-10"
        and row.get("endDate") == "2026-08-19"
    }
    for product_id, cost in PRODUCT_COSTS.items():
        prior = previous.get(product_id, {})
        row = next(
            (
                value
                for value in periods
                if str(value.get("productId")) == product_id
                and value.get("startDate") == START_DATE
                and value.get("endDate") == END_DATE
            ),
            None,
        )
        values = {
            "product": prior.get("product", ""),
            "productId": product_id,
            "keyword": prior.get("keyword", ""),
            "link": prior.get("link", ""),
            "vendor": prior.get("vendor", "파워마케팅"),
            "startDate": START_DATE,
            "endDate": END_DATE,
            "comparisonStatus": "pending_2025_data",
            "comparisonBasis": "전년 동기간 매출",
            "days": 10,
            "sourceStatus": "유료 연장",
            "isComplete": False,
            "slotCost": cost,
            "yearOverYearSales": None,
            "during": {"daysWithData": 0, "sales": 0, "orders": 0, "adSales": 0, "adCost": 0},
            "incrementalSales": None,
            "salesChangeRate": None,
            "incrementalRoas": None,
            "slotCostRate": None,
            "blendedMarketingCost": cost,
            "blendedSalesRoas": None,
            "rankAverage": None,
            "rankBest": None,
            "rankWorst": None,
            "rankSamples": 0,
            "decision": "관찰중",
            "memo": MEMO,
        }
        if row is None:
            periods.append(values)
        else:
            row.update(values)

    summary = efficiency.setdefault("summary", {})
    completed = [row for row in periods if row.get("isComplete")]
    summary["periodCount"] = len(periods)
    summary["completedCount"] = len(completed)
    summary["activeCount"] = len(periods) - len(completed)
    efficiency["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def update_august_payment(data: dict) -> None:
    metrics = data.setdefault("totalSalesMetrics", {})
    rows = metrics.setdefault("autoAdCosts", [])
    slot = next((row for row in rows if "슬롯/리워드" in str(row.get("name", ""))), None)
    if slot is None:
        slot = {"name": "슬롯/리워드 결제 기준(VAT 포함)", "weeks": [0, 0, 0, 0, 0], "total": 0}
        rows.append(slot)
    weeks = list(slot.get("weeks") or [])[:5]
    weeks += [0] * (5 - len(weeks))
    weeks[2] = TOTAL_COST
    slot["weeks"] = weeks
    slot["total"] = sum(weeks)

    combined = [
        sum(float(row.get("weeks", [0] * 5)[index] or 0) for row in rows)
        for index in range(5)
    ]
    metrics["autoAdCostTotal"] = {
        "name": metrics.get("autoAdCostTotal", {}).get("name", "광고비 합계"),
        "weeks": [int(value) for value in combined],
        "total": int(sum(combined)),
    }


def update_invoice(data: dict) -> None:
    invoices = data.setdefault("slotInvoices", [])
    values = {
        "issueDate": "2026-08-19", "approvalNumber": "20260819-10260819-43955418",
        "supplier": "주식회사 아우어마케팅", "servicePeriod": "2026-08-20 ~ 2026-08-29",
        "invoiceItem": "8.10~8.19 온라인서비스", "quantity": 30, "unitPrice": 40_000,
        "supplyAmount": 1_200_000, "vat": 120_000, "totalAmount": 1_320_000,
        "assetPath": "assets/slots/tax-invoice-2026-08-19.png", "note": "스테이 10일 30개 유료 연장 증빙",
        "products": [
            {"product": "돌잔치답례품(수건)", "quantity": 10, "amount": 400_000},
            {"product": "돌잔치답례품(핸드워시)", "quantity": 15, "amount": 600_000},
            {"product": "어린이집수건", "quantity": 5, "amount": 200_000},
        ],
    }
    invoice = next((row for row in invoices if row.get("approvalNumber") == values["approvalNumber"]), None)
    invoices.append(values) if invoice is None else invoice.update(values)

def main() -> None:
    for path in TARGETS:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        update_reward_marketing(data)
        update_slot_efficiency(data)
        update_august_payment(data)
        update_invoice(data)
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"updated {path.name}")


if __name__ == "__main__":
    main()
