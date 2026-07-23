from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "powerlink-creative-config.json"
FETCHER = Path(r"C:\Users\user\Documents\New project 4\scripts\fetch_naver_ads_raw.py")

def text(value) -> str:
    return "" if value is None else str(value).strip()

def status_label(row: dict) -> str:
    if row.get("delFlag"):
        return "삭제"
    if row.get("userLock") or row.get("enable") is False:
        return "중지"
    if text(row.get("inspectStatus")).upper() not in {"", "APPROVED"}:
        return "검수중"
    if text(row.get("status")).upper() in {"ELIGIBLE", "ACTIVE"}:
        return "운영 가능"
    return text(row.get("statusReason") or row.get("status")) or "상태 미확인"

def device_label(campaign: str, adgroup: str) -> str:
    value = f"{campaign} {adgroup}".lower()
    if "모바일" in value or "(m)" in value:
        return "모바일"
    if "(pc)" in value:
        return "PC"
    return "PC·모바일"

def normalize_creative(ad: dict, device: str) -> dict:
    payload = ad.get("ad") or {}
    selected = payload.get("mobile" if device == "모바일" else "pc") or payload.get("mobile") or payload.get("pc") or {}
    return {
        "id": text(ad.get("nccAdId")),
        "type": text(ad.get("type")),
        "title": text(payload.get("headline") or payload.get("title") or payload.get("name")),
        "description": text(payload.get("description")),
        "displayUrl": text(selected.get("display")),
        "finalUrl": text(selected.get("final")),
        "status": status_label(ad),
        "inspectStatus": text(ad.get("inspectStatus")),
        "updatedAt": text(ad.get("editTm")),
    }

def extension_type_label(value: str) -> str:
    return {
        "HEADLINE": "추가제목",
        "DESCRIPTION_EXTRA": "추가설명",
        "SUB_LINKS": "서브링크",
        "IMAGE_SUB_LINKS": "이미지형 서브링크",
        "IMAGE": "이미지형",
    }.get(value, value or "확장소재")

def normalize_extension(extension: dict) -> dict:
    extension_type = text(extension.get("type"))
    payload = extension.get("adExtension")
    raw_items = payload if isinstance(payload, list) else [payload or {}]
    items = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        name = text(item.get("name") or item.get("headline") or item.get("description") or item.get("text"))
        items.append({
            "name": name or extension_type_label(extension_type),
            "finalUrl": text(item.get("final")),
            "imagePath": text(item.get("imagePath")),
        })
    return {
        "id": text(extension.get("nccAdExtensionId")),
        "type": extension_type,
        "typeLabel": extension_type_label(extension_type),
        "status": status_label(extension),
        "inspectStatus": text(extension.get("inspectStatus")),
        "items": items,
        "updatedAt": text(extension.get("editTm")),
    }

def main() -> None:
    spec = importlib.util.spec_from_file_location("naver_fetch_creatives", FETCHER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    account = module.load_accounts(module.DEFAULT_CONFIG)[0]
    campaigns = module.ensure_list(module.api_request(account, "GET", "/ncc/campaigns"))
    groups = module.get_all_adgroups(account, campaigns)
    keywords = module.get_all_keywords(account, groups)
    ads = module.get_all_ads(account, groups)
    keywords_by_group: dict[str, list[dict]] = {}
    ads_by_group: dict[str, list[dict]] = {}
    for keyword in keywords:
        keywords_by_group.setdefault(text(keyword.get("nccAdgroupId")), []).append(keyword)
    for ad in ads:
        ads_by_group.setdefault(text(ad.get("nccAdgroupId")), []).append(ad)
    result_groups = []
    for group in groups:
        campaign = group.get("_campaign") or {}
        campaign_name = text(campaign.get("name") or campaign.get("campaignName"))
        if not campaign_name.startswith("파워링크"):
            continue
        group_id = text(group.get("nccAdgroupId"))
        group_name = text(group.get("name") or group.get("adgroupName"))
        device = device_label(campaign_name, group_name)
        extension_rows = module.ensure_list(module.api_request(account, "GET", "/ncc/ad-extensions", {"ownerId": group_id}))
        extensions = [normalize_extension(row) for row in extension_rows if not row.get("delFlag")]
        group_keywords = [{
            "id": text(row.get("nccKeywordId")),
            "keyword": text(row.get("keyword") or row.get("keywordText")),
            "status": status_label(row),
            "bidAmount": int(round(float(row.get("bidAmt") or group.get("bidAmt") or 0))),
            "usesGroupBid": bool(row.get("useGroupBidAmt")),
        } for row in keywords_by_group.get(group_id, []) if not row.get("delFlag")]
        creatives = [normalize_creative(row, device) for row in ads_by_group.get(group_id, []) if not row.get("delFlag")]
        result_groups.append({
            "campaignId": text(campaign.get("nccCampaignId")),
            "campaign": campaign_name,
            "campaignStatus": status_label(campaign),
            "adgroupId": group_id,
            "adgroup": group_name,
            "adgroupStatus": status_label(group),
            "device": device,
            "keywords": sorted(group_keywords, key=lambda row: row["keyword"]),
            "creatives": creatives,
            "extensions": extensions,
            "extensionItemCount": sum(len(row["items"]) for row in extensions),
        })
    result_groups.sort(key=lambda row: (row["campaign"], row["adgroup"]))
    output = {
        "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "Naver SearchAd API",
        "account": account.name,
        "groupCount": len(result_groups),
        "groups": result_groups,
    }
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({
        "updatedAt": output["updatedAt"],
        "groups": len(result_groups),
        "keywords": sum(len(row["keywords"]) for row in result_groups),
        "creatives": sum(len(row["creatives"]) for row in result_groups),
        "extensions": sum(len(row["extensions"]) for row in result_groups),
        "extensionItems": sum(row["extensionItemCount"] for row in result_groups),
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
