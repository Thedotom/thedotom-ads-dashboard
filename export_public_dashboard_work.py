from __future__ import annotations

import importlib.util
import json
import shutil
from datetime import datetime
from pathlib import Path

REPORT_DIR = Path("D:/\uad11\uace0\ubcf4\uace0\uc11c")
PROJECT_DIR = Path("C:/Users/user/Documents/New project 4")
PUBLIC_DIR = PROJECT_DIR / "public_dashboard"
PUBLIC_DATA_DIR = PUBLIC_DIR / "data"
EXISTING_PUBLIC_DIR = REPORT_DIR / "public_dashboard"
LEGACY_SERVER = REPORT_DIR / "_archive" / "legacy_files" / "monthly_naver_ads_dashboard_server.py"
RANK_DATA_FILE = REPORT_DIR / "rank" / "rank_data.json"
CAFE24_SALES_DIR = REPORT_DIR / "data" / "cafe24_sales"


def _week_index_from_date(date_text: str) -> int:
    day = int(str(date_text).split("-")[2])
    if day <= 7:
        return 0
    if day <= 14:
        return 1
    if day <= 21:
        return 2
    if day <= 28:
        return 3
    return 4


def _row_total(row: dict) -> None:
    row["total"] = sum(float(v or 0) for v in row.get("weeks", []))


def _apply_cafe24_sales(data: dict, month: str) -> None:
    metrics = data.setdefault("totalSalesMetrics", {})
    auto_sales = metrics.setdefault("autoSales", [])
    weeks = [0.0, 0.0, 0.0, 0.0, 0.0]

    if CAFE24_SALES_DIR.exists():
        for path in CAFE24_SALES_DIR.glob(f"cafe24_daily_sales_{month}-*.json"):
            try:
                item = json.loads(path.read_text(encoding="utf-8-sig"))
            except Exception:
                continue
            date_text = item.get("date") or path.stem.replace("cafe24_daily_sales_", "")
            if not str(date_text).startswith(month):
                continue
            weeks[_week_index_from_date(date_text)] += float(item.get("revenue") or 0)

    target = None
    for row in auto_sales:
        if row.get("name") == "자사몰 자동수집":
            target = row
            break

    if target is None:
        target = {"name": "자사몰 자동수집", "weeks": weeks, "total": 0.0}
        auto_sales.append(target)
    else:
        target["weeks"] = weeks

    _row_total(target)

    total_weeks = [0.0, 0.0, 0.0, 0.0, 0.0]
    for row in auto_sales:
        for idx, value in enumerate(row.get("weeks", [])[:5]):
            total_weeks[idx] += float(value or 0)

    metrics["autoSalesTotal"] = {
        "name": "자동 매출 합계",
        "weeks": total_weeks,
        "total": sum(total_weeks),
    }


def _sync_manual_into_total_sales(data: dict) -> None:
    metrics = data.setdefault("totalSalesMetrics", {})
    for key in ["manualSource", "manualSales", "manualSalesTotal", "manualAdCosts", "manualAdCostTotal"]:
        if key in data:
            metrics[key] = data[key]


def _refresh_total_sales_metrics(data: dict, month: str) -> None:
    _sync_manual_into_total_sales(data)
    _apply_cafe24_sales(data, month)


POWERLINK_CAMPAIGN_ORDER = {
    "파워링크_더도톰_자사몰": 0,
    "파워링크_더도톰_세부 키워드": 1,
    "파워링크_더도톰스튜디오_스스": 2,
}
POWERLINK_ADGROUP_ORDER = {
    "자사몰": 0,
    "세부키워드": 10,
    "소규모돌잔치": 11,
    "웨딩": 12,
    "스튜디오": 20,
}


def _powerlink_campaign_order(campaign: str) -> int:
    return POWERLINK_CAMPAIGN_ORDER.get(campaign, 999)


def _powerlink_adgroup_order(adgroup: str) -> int:
    return POWERLINK_ADGROUP_ORDER.get(adgroup, 999)


def _classify_powerlink_adgroup(campaign: str, keyword: str) -> str:
    campaign = str(campaign or "")
    keyword = str(keyword or "")
    if "자사몰" in campaign:
        return "자사몰"
    if "스튜디오" in campaign:
        return "스튜디오"
    if "세부" in campaign:
        if "소규모" in keyword or "직계" in keyword:
            return "소규모돌잔치"
        if "웨딩" in keyword or "결혼" in keyword:
            return "웨딩"
        return "세부키워드"
    return campaign or "파워링크"


def _row_rank_sort_value(row: dict) -> int:
    rank = row.get("rank")
    return rank if isinstance(rank, int) else 9999


def _split_powerlink_sections_by_adgroup(rank_traffic: dict) -> None:
    for detail in rank_traffic.get("slotDetails", []):
        grouped = {}
        for section in detail.get("powerlinkSections", []):
            campaign = section.get("campaign", "")
            for device in ["pc", "mobile"]:
                for item in section.get(device, []) or []:
                    adgroup = item.get("adgroup") or _classify_powerlink_adgroup(campaign, item.get("keyword", ""))
                    key = (campaign, adgroup)
                    target = grouped.setdefault(key, {"campaign": campaign, "adgroup": adgroup, "pc": [], "mobile": []})
                    target[device].append(item)
        sections = list(grouped.values())
        for section in sections:
            for device in ["pc", "mobile"]:
                section[device].sort(key=lambda row: (_row_rank_sort_value(row), str(row.get("keyword", ""))))
        sections.sort(key=lambda row: (
            _powerlink_campaign_order(row.get("campaign", "")),
            _powerlink_adgroup_order(row.get("adgroup", "")),
            str(row.get("campaign", "")),
            str(row.get("adgroup", "")),
        ))
        detail["powerlinkSections"] = sections

    for key in ["powerlinkPcRows", "powerlinkMobileRows"]:
        rows = rank_traffic.get(key) or []
        for row in rows:
            row["adgroup"] = row.get("adgroup") or _classify_powerlink_adgroup(row.get("campaign", ""), row.get("keyword", ""))
        rows.sort(key=lambda row: (
            _powerlink_campaign_order(row.get("campaign", "")),
            _powerlink_adgroup_order(row.get("adgroup", "")),
            _row_rank_sort_value(row),
            str(row.get("keyword", "")),
        ))


def copy_existing_public() -> None:
    if EXISTING_PUBLIC_DIR.exists():
        PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
        for item in EXISTING_PUBLIC_DIR.iterdir():
            if item.name == ".git":
                continue
            dest = PUBLIC_DIR / item.name
            if item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest, ignore=shutil.ignore_patterns(".git"))
            else:
                shutil.copy2(item, dest)


def load_legacy_module():
    spec = importlib.util.spec_from_file_location("legacy_dashboard_server", LEGACY_SERVER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load legacy dashboard module: {LEGACY_SERVER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.RANK_DATA_FILE = RANK_DATA_FILE
    return module


def update_dashboard_json(module, json_path: Path) -> bool:
    if not json_path.exists():
        return False
    data = json.loads(json_path.read_text(encoding="utf-8"))
    month = data.get("month") or json_path.stem.replace("monthly-dashboard-", "")
    if not month or month == "latest":
        month = data.get("month", "2026-06")
    data["rankTraffic"] = module.collect_rank_traffic(month)
    _refresh_total_sales_metrics(data, month)
    _split_powerlink_sections_by_adgroup(data["rankTraffic"])
    data["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    json_path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return True


def ensure_rank_month_shell() -> str | None:
    current_month = datetime.now().strftime("%Y-%m")
    if not RANK_DATA_FILE.exists():
        return None
    rank_data = json.loads(RANK_DATA_FILE.read_text(encoding="utf-8-sig"))
    if not any(str(date_key).startswith(current_month) for date_key in rank_data):
        return None

    months_path = PUBLIC_DATA_DIR / "months.json"
    months_data = {"months": [], "availableMonths": [], "latest": current_month}
    if months_path.exists():
        months_data.update(json.loads(months_path.read_text(encoding="utf-8-sig")))

    target = PUBLIC_DATA_DIR / f"monthly-dashboard-{current_month}.json"
    if not target.exists():
        previous_month = months_data.get("latest")
        template = PUBLIC_DATA_DIR / f"monthly-dashboard-{previous_month}.json"
        if not template.exists():
            template = PUBLIC_DATA_DIR / "monthly-dashboard-latest.json"
        if not template.exists():
            return None
        data = json.loads(template.read_text(encoding="utf-8-sig"))
        data["month"] = current_month
        data["reportPath"] = ""
        data["draftPath"] = ""
        for key in ["monthly", "typePerformance", "campaigns", "adgroups", "keywordPerformance", "inspection", "plan", "manualSales", "manualAdCosts", "accountPerformance"]:
            data[key] = []
        for key in ["summary", "dataProfile", "rankObservation", "shoppingIntegrated", "dailyProductCosts", "dailyProductPerformance", "totalSalesMetrics", "manualSalesTotal", "manualAdCostTotal", "revenueMetrics", "bidPerformance", "slotEfficiency"]:
            data[key] = {}
        data["state"] = {"notes": {}, "planMemo": "", "reportMemo": ""}
        data["rewardMarketing"] = {"items": [], "daily": [], "summary": {}}
        target.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    month_list = [current_month] + [month for month in (months_data.get("months") or []) if month != current_month]
    months_data["months"] = month_list
    months_data["availableMonths"] = month_list
    months_data["latest"] = current_month
    months_path.write_text(json.dumps(months_data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return current_month

def main() -> None:
    copy_existing_public()
    PUBLIC_DATA_DIR.mkdir(parents=True, exist_ok=True)
    module = load_legacy_module()

    ensure_rank_month_shell()

    months_path = PUBLIC_DATA_DIR / "months.json"
    latest_month = "2026-06"
    if months_path.exists():
        months = json.loads(months_path.read_text(encoding="utf-8"))
        latest_month = months.get("latest") or latest_month

    updated = []
    for path in [
        PUBLIC_DATA_DIR / f"monthly-dashboard-{latest_month}.json",
        PUBLIC_DATA_DIR / "monthly-dashboard-latest.json",
    ]:
        if update_dashboard_json(module, path):
            updated.append(str(path))

    print(f"public_dashboard_created={PUBLIC_DIR}")
    print(f"latest={latest_month}")
    print(f"rank_data={RANK_DATA_FILE}")
    print("updated=" + ", ".join(updated))


if __name__ == "__main__":
    main()


