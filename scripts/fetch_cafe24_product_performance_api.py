from __future__ import annotations

import argparse
import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path


REPORT_ROOT = Path(r"D:\광고보고서")
CONFIG_PATH = REPORT_ROOT / "state" / "cafe24_dashboard_api_config.json"
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
RAW_DIR = REPORT_ROOT / "data" / "cafe24_product_api"
STORE = "cafe24"
STORE_NAME = "카페24(자사몰)"


def number(value):
    return float(value or 0)


def request_json(method, url, headers=None, body=None):
    data = urllib.parse.urlencode(body).encode("utf-8") if body else None
    request = urllib.request.Request(url, data=data, method=method)
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    for attempt in range(6):
        try:
            # Cafe24 limits this endpoint to 40 requests per minute.
            time.sleep(1.6)
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            if error.code == 429 and attempt < 5:
                time.sleep(65)
                continue
            raise RuntimeError(f"HTTP {error.code}: {detail}") from error


def load_access():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    pair = f"{config['client_id']}:{config['client_secret']}"
    basic = base64.b64encode(pair.encode("ascii")).decode("ascii")
    token = request_json(
        "POST",
        f"https://{config['mall_id']}.cafe24api.com/api/v2/oauth/token",
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        body={
            "grant_type": "refresh_token",
            "refresh_token": config["refresh_token"],
        },
    )
    if token.get("refresh_token"):
        config["refresh_token"] = token["refresh_token"]
        config["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        CONFIG_PATH.write_text(
            json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    headers = {
        "Authorization": f"Bearer {token['access_token']}",
        "Content-Type": "application/json",
        "X-Cafe24-Api-Version": config.get("api_version", "2025-12-01"),
    }
    return config, headers


def fetch_orders(config, headers, target_date):
    rows = []
    offset = 0
    while True:
        query = urllib.parse.urlencode(
            {
                "start_date": target_date,
                "end_date": target_date,
                "date_type": "pay_date",
                "limit": 100,
                "offset": offset,
            }
        )
        payload = request_json(
            "GET",
            f"https://{config['mall_id']}.cafe24api.com/api/v2/admin/orders?{query}",
            headers=headers,
        )
        batch = payload.get("orders") or []
        rows.extend(batch)
        if len(batch) < 100:
            return rows
        offset += 100


def is_canceled(order):
    return str(order.get("canceled", "")).upper() in {"T", "TRUE", "Y", "1"}


def fetch_items(config, headers, order_id):
    url = (
        f"https://{config['mall_id']}.cafe24api.com/api/v2/admin/orders/"
        f"{urllib.parse.quote(str(order_id))}/items"
    )
    return request_json("GET", url, headers=headers).get("items") or []


def build_rows(target_date, config, headers):
    orders = [
        order
        for order in fetch_orders(config, headers, target_date)
        if not is_canceled(order)
    ]
    groups = defaultdict(
        lambda: {
            "productName": "",
            "grossSales": 0.0,
            "quantity": 0.0,
            "orders": set(),
            "itemCodes": set(),
        }
    )
    raw_items = []
    for order in orders:
        for item in fetch_items(config, headers, order["order_id"]):
            raw_items.append(item)
            product_code = str(item.get("product_code") or item.get("product_no") or "")
            if not product_code:
                continue
            quantity = number(item.get("quantity"))
            unit_price = number(item.get("product_price")) + number(
                item.get("option_price")
            )
            group = groups[product_code]
            group["productName"] = str(
                item.get("product_name") or item.get("product_name_default") or ""
            )
            group["grossSales"] += unit_price * quantity
            group["quantity"] += quantity
            group["orders"].add(str(order["order_id"]))
            if item.get("variant_code"):
                group["itemCodes"].add(str(item["variant_code"]))

    rows = []
    for product_code, group in groups.items():
        name = group["productName"]
        sales = group["grossSales"]
        rows.append(
            {
                "recordId": f"cafe24:{product_code}",
                "date": target_date,
                "store": STORE,
                "storeName": STORE_NAME,
                "productId": product_code,
                "productName": name,
                "product": name,
                "adgroup": "",
                "adSales": 0.0,
                "adCost": 0.0,
                "impressions": 0.0,
                "clicks": 0.0,
                "conversions": 0.0,
                "status": "자연",
                "memo": "카페24 주문상품 API 결제일 기준 상품별 총판매가",
                "dailySales": sales,
                "orders": len(group["orders"]),
                "refundAmount": 0.0,
                "roas": 0.0,
                "adCostRate": 0.0,
                "adProfit": 0.0,
                "source": f"cafe24_orders_api_{target_date}.json",
                "grossSales": sales,
                "quantity": group["quantity"],
                "refundQuantity": 0.0,
                "itemCodes": sorted(group["itemCodes"]),
            }
        )
    return sorted(rows, key=lambda row: -row["dailySales"]), orders, raw_items


def refresh(section):
    rows = section["rows"]
    section["count"] = len(rows)
    dates = sorted({row.get("date") for row in rows if row.get("date")})
    section["dateLabel"] = f"{dates[0]} ~ {dates[-1]}" if dates else ""
    section["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    totals = {
        key: sum(number(row.get(key)) for row in rows)
        for key in ["adSales", "adCost", "dailySales", "orders"]
    }
    totals["roas"] = totals["adSales"] / totals["adCost"] if totals["adCost"] else 0
    totals["adCostRate"] = (
        totals["adCost"] / totals["dailySales"] if totals["dailySales"] else 0
    )
    totals["adProfit"] = totals["adSales"] - totals["adCost"]
    section["totals"] = totals


def update_dashboard(path, target_date, rows):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    section = data.setdefault("dailyProductPerformance", {"rows": []})
    kept = [
        row
        for row in section.get("rows", [])
        if not (row.get("date") == target_date and row.get("store") == STORE)
    ]
    section["rows"] = sorted(
        kept + rows,
        key=lambda row: (
            str(row.get("date", "")),
            str(row.get("store", "")),
            -number(row.get("dailySales")),
        ),
    )
    refresh(section)
    path.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "date", nargs="?", default=(date.today() - timedelta(days=1)).isoformat()
    )
    args = parser.parse_args()
    config, headers = load_access()
    rows, orders, raw_items = build_rows(args.date, config, headers)
    if not rows:
        raise ValueError(f"No Cafe24 product rows for {args.date}")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DIR / f"cafe24_orders_api_{args.date}.json"
    raw_path.write_text(
        json.dumps(
            {"date": args.date, "orders": orders, "items": raw_items},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    month = args.date[:7]
    targets = [DATA_DIR / f"monthly-dashboard-{month}.json"]
    latest = DATA_DIR / "monthly-dashboard-latest.json"
    if latest.exists():
        latest_data = json.loads(latest.read_text(encoding="utf-8-sig"))
        if latest_data.get("month") == month:
            targets.append(latest)
    for target in targets:
        update_dashboard(target, args.date, rows)

    print(
        json.dumps(
            {
                "date": args.date,
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


if __name__ == "__main__":
    main()
