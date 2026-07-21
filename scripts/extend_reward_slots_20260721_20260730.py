from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TARGET_FILES = (
    DATA / "monthly-dashboard-2026-07.json",
    DATA / "monthly-dashboard-latest.json",
)
START_DATE = "2026-07-21"
END_DATE = "2026-07-30"
COST_PER_PRODUCT = 1_320_000
SLOT_WEEKLY_COSTS = [1_320_000, 1_320_000, 1_320_000, 0, 0]


def update(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    reward = data["rewardMarketing"]
    items = reward["items"]

    for item in items:
        periods = item.setdefault("slotPeriods", [])
        matching = [
            period
            for period in periods
            if period.get("startDate") == START_DATE
            and period.get("endDate") == END_DATE
        ]
        if matching:
            matching[0]["cost"] = COST_PER_PRODUCT
        else:
            periods.append(
                {
                    "startDate": START_DATE,
                    "endDate": END_DATE,
                    "cost": COST_PER_PRODUCT,
                }
            )
        item["endDate"] = END_DATE
        item["status"] = "active"
        item["memo"] = "리워드 슬롯 운영중"

    reward["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    reward["note"] = "2026-07-01~2026-07-30 리워드 슬롯 연장 운영"

    metrics = data["totalSalesMetrics"]
    ad_cost_rows = metrics["autoAdCosts"]
    slot_row = next(
        (
            row
            for row in ad_cost_rows
            if list(row.get("weeks", []))[:2] == SLOT_WEEKLY_COSTS[:2]
            and int(row.get("total", 0)) == sum(SLOT_WEEKLY_COSTS[:2])
        ),
        None,
    )
    if slot_row is None:
        raise RuntimeError(f"slot cost row not found in {path.name}")
    slot_row["weeks"] = SLOT_WEEKLY_COSTS
    slot_row["total"] = sum(SLOT_WEEKLY_COSTS)

    combined = [
        sum(float(row.get("weeks", [0] * 5)[index] or 0) for row in ad_cost_rows)
        for index in range(5)
    ]
    metrics["autoAdCostTotal"] = {
        "name": metrics.get("autoAdCostTotal", {}).get("name", "광고비 합계"),
        "weeks": [int(value) for value in combined],
        "total": int(sum(combined)),
    }
    path.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"updated {path.name}: {len(items)} products")


def main() -> None:
    for path in TARGET_FILES:
        update(path)


if __name__ == "__main__":
    main()
