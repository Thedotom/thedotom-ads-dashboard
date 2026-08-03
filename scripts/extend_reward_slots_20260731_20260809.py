from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
JULY = DATA / "monthly-dashboard-2026-07.json"
AUGUST = DATA / "monthly-dashboard-2026-08.json"
LATEST = DATA / "monthly-dashboard-latest.json"
START_DATE = "2026-07-31"
END_DATE = "2026-08-09"
COST = 1_320_000
PRODUCT_IDS = {"4624494637", "4843121925", "12924495111"}


def add_period(item: dict) -> None:
    periods = item.setdefault("slotPeriods", [])
    period = next(
        (
            row
            for row in periods
            if row.get("startDate") == START_DATE and row.get("endDate") == END_DATE
        ),
        None,
    )
    if period is None:
        periods.append({"startDate": START_DATE, "endDate": END_DATE, "cost": COST})
    else:
        period["cost"] = COST
    item["endDate"] = END_DATE
    item["status"] = "active"
    item["memo"] = "리워드 슬롯 운영중"


def update_reward(data: dict, source_items: list[dict]) -> None:
    reward = data.setdefault("rewardMarketing", {})
    items = reward.get("items") or copy.deepcopy(source_items)
    items = [item for item in items if str(item.get("productId")) in PRODUCT_IDS]
    for item in items:
        add_period(item)
    reward["items"] = items
    reward["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    reward["note"] = "동일 상품 3개 리워드 슬롯 2026-07-31~2026-08-09 연장 운영"


def update_july_cost(data: dict) -> None:
    metrics = data.setdefault("totalSalesMetrics", {})
    rows = metrics.setdefault("autoAdCosts", [])
    slot = next((row for row in rows if "슬롯/리워드" in str(row.get("name", ""))), None)
    if slot is None:
        slot = {"name": "슬롯/리워드 결제 기준(VAT 포함)", "weeks": [0, 0, 0, 0, 0], "total": 0}
        rows.append(slot)
    weeks = list(slot.get("weeks") or [])[:5]
    weeks += [0] * (5 - len(weeks))
    weeks[4] = COST
    slot["weeks"] = weeks
    slot["total"] = sum(weeks)
    combined = [sum(float(row.get("weeks", [0] * 5)[i] or 0) for row in rows) for i in range(5)]
    metrics["autoAdCostTotal"] = {
        "name": metrics.get("autoAdCostTotal", {}).get("name", "광고비 합계"),
        "weeks": [int(value) for value in combined],
        "total": int(sum(combined)),
    }


def main() -> None:
    july = json.loads(JULY.read_text(encoding="utf-8"))
    source_items = [
        copy.deepcopy(item)
        for item in july.get("rewardMarketing", {}).get("items", [])
        if str(item.get("productId")) in PRODUCT_IDS
    ]
    if len(source_items) != 3:
        raise RuntimeError(f"expected 3 reward products, found {len(source_items)}")

    update_reward(july, source_items)
    update_july_cost(july)
    JULY.write_text(json.dumps(july, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    for path in (AUGUST, LATEST):
        data = json.loads(path.read_text(encoding="utf-8"))
        update_reward(data, source_items)
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("extended reward slots for 3 products: 2026-07-31~2026-08-09")


if __name__ == "__main__":
    main()
