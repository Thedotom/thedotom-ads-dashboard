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
START_DATE = "2026-08-10"
END_DATE = "2026-08-19"
MEMO = "순위 미상승에 따른 업체 무상 AS 연장 기간 (비용 0원)"
PRODUCT_IDS = {"4624494637", "4843121925", "12924495111"}


def update_reward_marketing(data: dict) -> None:
    reward = data.setdefault("rewardMarketing", {})
    items = [
        item
        for item in reward.get("items", [])
        if str(item.get("productId")) in PRODUCT_IDS
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
            "cost": 0,
            "type": "AS",
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
        "동일 상품 3개 리워드 슬롯 2026-08-10~2026-08-19 "
        "업체 무상 AS 연장 운영 (추가 비용 0원)"
    )


def update_slot_efficiency(data: dict) -> None:
    efficiency = data.get("slotEfficiency")
    if not isinstance(efficiency, dict):
        return
    periods = efficiency.setdefault("periods", [])
    previous = {
        str(row.get("productId")): row
        for row in periods
        if row.get("startDate") == "2026-07-31"
        and row.get("endDate") == "2026-08-09"
    }
    for product_id in sorted(PRODUCT_IDS):
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
            "vendor": prior.get("vendor", "아우어마케팅"),
            "startDate": START_DATE,
            "endDate": END_DATE,
            "comparisonStatus": "as_extension",
            "comparisonBasis": "업체 무상 AS 연장",
            "days": 10,
            "sourceStatus": "AS 기간",
            "isComplete": False,
            "slotCost": 0,
            "yearOverYearSales": None,
            "during": {
                "daysWithData": 0,
                "sales": 0,
                "orders": 0,
                "adSales": 0,
                "adCost": 0,
            },
            "incrementalSales": None,
            "salesChangeRate": None,
            "incrementalRoas": None,
            "slotCostRate": None,
            "blendedMarketingCost": 0,
            "blendedSalesRoas": None,
            "rankAverage": None,
            "rankBest": None,
            "rankWorst": None,
            "rankSamples": 0,
            "decision": "AS 기간",
            "memo": MEMO,
        }
        if row is None:
            periods.append(values)
        else:
            row.update(values)
    efficiency["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main() -> None:
    for path in TARGETS:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        update_reward_marketing(data)
        update_slot_efficiency(data)
        path.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        print(f"updated {path.name}")


if __name__ == "__main__":
    main()
