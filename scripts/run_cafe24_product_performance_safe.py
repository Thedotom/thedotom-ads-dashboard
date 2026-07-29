from __future__ import annotations

import json
import sys
import time

import fetch_cafe24_product_performance_api as fetcher


target_date = sys.argv[1]
original_fetch_items = fetcher.fetch_items
request_count = 0


def rate_limited_fetch_items(config, headers, order_id):
    global request_count
    request_count += 1
    if request_count % 30 == 0:
        time.sleep(2)
    for attempt in range(4):
        try:
            return original_fetch_items(config, headers, order_id)
        except RuntimeError as error:
            if "HTTP 429" not in str(error) or attempt == 3:
                raise
            time.sleep(2)


fetcher.fetch_items = rate_limited_fetch_items
config, headers = fetcher.load_access()
rows, orders, raw_items = fetcher.build_rows(target_date, config, headers)
if not rows:
    raise ValueError(f"No Cafe24 product rows for {target_date}")

month = target_date[:7]
targets = [fetcher.DATA_DIR / f"monthly-dashboard-{month}.json"]
latest = fetcher.DATA_DIR / "monthly-dashboard-latest.json"
if latest.exists():
    latest_data = json.loads(latest.read_text(encoding="utf-8-sig"))
    if latest_data.get("month") == month:
        targets.append(latest)
for target in targets:
    fetcher.update_dashboard(target, target_date, rows)

print(
    json.dumps(
        {
            "date": target_date,
            "products": len(rows),
            "orders": len(orders),
            "items": len(raw_items),
            "grossProductSales": sum(row["dailySales"] for row in rows),
            "quantity": sum(row["quantity"] for row in rows),
            "targets": [str(target) for target in targets],
        },
        ensure_ascii=False,
    )
)
