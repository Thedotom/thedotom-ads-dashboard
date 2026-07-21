from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
FETCHER = Path(r"C:\Users\user\Documents\New project 4\scripts\fetch_naver_ads_raw.py")


def text(value):
    return "" if value is None else str(value).strip()


def integer(value):
    try:
        return int(round(float(value or 0)))
    except (TypeError, ValueError):
        return 0


def item_key(item):
    return text(item.get("entityId")) or "|".join(text(item.get(key)) for key in ("type", "campaign", "adgroup", "keyword"))


def main():
    spec = importlib.util.spec_from_file_location("naver_fetch", FETCHER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    account = module.load_accounts(module.DEFAULT_CONFIG)[0]
    campaigns = module.ensure_list(module.api_request(account, "GET", "/ncc/campaigns"))
    groups = module.get_all_adgroups(account, campaigns)
    keywords = module.get_all_keywords(account, groups)
    snapshot_path = DATA / "naver-bid-snapshot.json"
    old = json.loads(snapshot_path.read_text(encoding="utf-8")) if snapshot_path.exists() else {}
    prior = {item_key(item): item for item in old.get("items", [])}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    items = []

    def add(item):
        previous = prior.get(item_key(item))
        previous_bid = integer(previous.get("currentBid")) if previous else None
        delta = None if previous_bid is None else item["currentBid"] - previous_bid
        item.update(previousBid=previous_bid, changeAmount=delta, changeStatus="baseline" if previous_bid is None else "up" if delta > 0 else "down" if delta < 0 else "same")
        items.append(item)

    for keyword in keywords:
        group = keyword.get("_adgroup") or {}
        campaign = keyword.get("_campaign") or group.get("_campaign") or {}
        campaign_name = text(campaign.get("name") or campaign.get("campaignName"))
        if "파워링크" not in campaign_name:
            continue
        use_group = bool(keyword.get("useGroupBidAmt"))
        add({"type": "powerlink", "entityId": text(keyword.get("nccKeywordId")), "campaign": campaign_name, "adgroup": text(group.get("name")), "keyword": text(keyword.get("keyword")), "currentBid": integer(group.get("bidAmt") if use_group else keyword.get("bidAmt")), "bidSource": "group" if use_group else "keyword", "status": text(keyword.get("status"))})

    for group in groups:
        campaign = group.get("_campaign") or {}
        campaign_name = text(campaign.get("name") or campaign.get("campaignName"))
        if "쇼핑" not in campaign_name:
            continue
        add({"type": "shopping", "entityId": text(group.get("nccAdgroupId")), "campaign": campaign_name, "adgroup": text(group.get("name")), "keyword": "", "currentBid": integer(group.get("bidAmt")), "bidSource": "group", "status": text(group.get("status"))})

    snapshot_path.write_text(json.dumps({"updatedAt": now, "previousUpdatedAt": old.get("updatedAt"), "items": items}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    power = {(item["campaign"], item["adgroup"], item["keyword"]): item for item in items if item["type"] == "powerlink"}
    shopping = {(item["campaign"], item["adgroup"]): item for item in items if item["type"] == "shopping"}
    labels = {"baseline": "기준수집", "up": "인상", "down": "인하", "same": "유지"}
    sources = {"group": "광고그룹", "keyword": "키워드"}
    month = datetime.now().strftime("%Y-%m")
    for path in (DATA / f"monthly-dashboard-{month}.json", DATA / "monthly-dashboard-latest.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        matched = 0
        for row in data.get("keywordPerformance", []):
            base = (text(row.get("캠페인명")), text(row.get("광고그룹명")))
            bid = power.get((*base, text(row.get("키워드")))) if row.get("광고유형") == "파워링크" else shopping.get(base)
            if not bid:
                continue
            row.update({"현재입찰가": bid["currentBid"], "이전입찰가": bid["previousBid"], "입찰변동액": bid["changeAmount"], "입찰변동": labels[bid["changeStatus"]], "입찰단위": sources[bid["bidSource"]], "입찰상태": bid["status"], "입찰확인시각": now})
            matched += 1
        counts = {labels[status]: sum(item["changeStatus"] == status for item in items) for status in labels}
        data["bidPerformance"] = {"updatedAt": now, "previousUpdatedAt": old.get("updatedAt"), "counts": counts, "items": items, "matchedPerformanceRows": matched}
        data["updatedAt"] = now
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"updatedAt": now, "items": len(items), "matched": matched, "counts": counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
