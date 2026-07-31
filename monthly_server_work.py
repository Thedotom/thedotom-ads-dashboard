from __future__ import annotations

import json
import math
import subprocess
import sys
from datetime import datetime
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
D_REPORT_DIR = Path("D:/광고보고서")
REPORT_PATTERN = "naver_ads_monthly_report_*.xlsx"
DEFAULT_MONTH = "2026-05"
HTML_FILE = PROJECT_ROOT / "dashboard" / "monthly_naver_ads_dashboard.html"
RANK_DASHBOARD_FILE = Path("D:/자동화/naver_dashboard_v3.html")
RANK_DATA_FILE = Path("D:/자동화/rank_data.json")
CORE_POWERLINK_KEYWORDS = {"답례품", "돌답례품", "돌잔치답례품"}
FIRST_PAGE_RANK_LIMIT = 5
BRAND_SEARCH_CONTRACT = {
    "startDate": "2026-05-19",
    "endDate": "2026-08-18",
    "pcAmount": 1_980_000,
    "mobileAmount": 2_640_000,
    "payment": "계약시 광고비 선차감",
    "areas": "모바일 브랜드검색, PC 브랜드검색",
    "memo": "5월부터 3개월 계약. 브랜드 키워드 세팅",
}
REWARD_MARKETING_ITEMS = [
    {
        "productName": "답례품 돌잔치 돌 수건 웨딩 환갑 칠순 개업 소규모 더도톰 150g 화이트",
        "link": "https://smartstore.naver.com/thedotomshop/products/4624494637",
        "productId": "4624494637",
        "keyword": "돌잔치답례품",
        "purpose": "순위 트래픽 (상단 순위 확보)",
        "startDate": "2026-06-11",
        "endDate": "2026-06-20",
        "days": 10,
        "totalAmount": 400_000,
        "unitAmount": 40_000,
        "vat": "VAT 별도",
        "quantity": "리워드 10개 (정확한 수량 모름)",
        "status": "진행중",
        "metric": "네이버 쇼핑 순위 변화",
    },
    {
        "productName": "답례품 돌잔치 돌 핸드워시 세트 칠순 개업 프리미엄 더도톰 150g 화이트",
        "link": "https://smartstore.naver.com/thedotomshop/products/4843121925",
        "productId": "4843121925",
        "keyword": "돌잔치답례품",
        "purpose": "순위 트래픽 (상단 순위 확보)",
        "startDate": "2026-06-11",
        "endDate": "2026-06-20",
        "days": 10,
        "totalAmount": 600_000,
        "unitAmount": 40_000,
        "vat": "VAT 별도",
        "quantity": "리워드 15개 (정확한 수량 모름)",
        "status": "진행중",
        "metric": "네이버 쇼핑 순위 변화",
    },
    {
        "productName": "어린이집 수건 고리 유치원 조구만 자수 국산 5장 해피데이",
        "link": "https://smartstore.naver.com/thedotomshop/products/12924495111",
        "productId": "12924495111",
        "keyword": "어린이집수건",
        "purpose": "순위 트래픽 (상단 순위 확보)",
        "startDate": "2026-06-11",
        "endDate": "2026-06-20",
        "days": 10,
        "totalAmount": 200_000,
        "unitAmount": 40_000,
        "vat": "VAT 별도",
        "quantity": "리워드 5개 (정확한 수량 모름)",
        "status": "진행중",
        "metric": "네이버 쇼핑 순위 변화",
    }
]
SHOPPING_KEYWORD_ORDER = {
    "12924495111": ["어린이집수건"],
    "4624494637": ["돌잔치답례품", "돌답례품", "답례품", "돌잔치수건", "수건답례품", "돌수건답례품", "돌잔치선물", "답례품수건", "돌답례품수건", "돌수건", "돌잔치답례품수건"],
    "4843121925": ["돌잔치답례품", "돌답례품", "답례품", "돌잔치기념품", "답례품세트", "답례품핸드워시", "답례품프리미엄세트", "돌답례품세트", "돌잔치답레품세트", "핸드워시세트", "돌답례품핸드워시세트"],
    "13471936380": ["모바일돌잔치초대장", "돌잔치초대장", "돌초대장", "돌잔치모바일초대장", "모바일돌초대장"],
}


def safe_number(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, float) and math.isnan(value):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def safe_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value)


def safe_value(value):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.strftime("%Y-%m-%d")
    return value


def parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def period_dates(month: str) -> tuple[datetime, datetime]:
    year, month_text = month.split("-", 1)
    import calendar

    today = datetime.now()
    last_day = calendar.monthrange(int(year), int(month_text))[1]
    end_day = last_day
    if int(year) == today.year and int(month_text) == today.month and today.day > 1:
        end_day = today.day - 1
    return parse_date(f"{year}-{month_text}-01"), parse_date(f"{year}-{month_text}-{end_day:02d}")


def overlap_days(start: str, end: str, period_start: datetime, period_end: datetime) -> int:
    item_start = parse_date(start)
    item_end = parse_date(end)
    overlap_start = max(item_start, period_start)
    overlap_end = min(item_end, period_end)
    if overlap_end < overlap_start:
        return 0
    return (overlap_end - overlap_start).days + 1


def records(df: pd.DataFrame) -> list[dict]:
    return [
        {key: safe_value(value) for key, value in row.items()}
        for row in df.where(pd.notna(df), None).to_dict("records")
    ]


def available_months() -> list[str]:
    months = set()
    for folder in [D_REPORT_DIR, PROJECT_ROOT / "output" / "monthly_reports"]:
        if not folder.exists():
            continue
        for path in folder.glob(REPORT_PATTERN):
            month = month_from_report_path(path)
            if month:
                months.add(month)
    return sorted(months, reverse=True)


def month_from_report_path(path: Path) -> str:
    stem = path.stem
    prefix = "naver_ads_monthly_report_"
    return stem.replace(prefix, "") if stem.startswith(prefix) else ""


def normalize_month(month: str | None = None) -> str:
    months = available_months()
    if month and month in months:
        return month
    if months:
        return months[0]
    return DEFAULT_MONTH


def report_path(month: str | None = None) -> Path:
    selected = normalize_month(month)
    d_path = D_REPORT_DIR / f"naver_ads_monthly_report_{selected}.xlsx"
    if d_path.exists():
        return d_path
    return PROJECT_ROOT / "output" / "monthly_reports" / f"naver_ads_monthly_report_{selected}.xlsx"


def state_file(month: str) -> Path:
    return PROJECT_ROOT / "output" / "monthly_reports" / f"dashboard_notes_{month}.json"


def draft_file(month: str) -> Path:
    return D_REPORT_DIR / f"naver_ads_report_draft_{month}.md"


def designed_report_file(month: str) -> Path:
    return D_REPORT_DIR / f"naver_ads_report_design_{month}.html"


def search_rank_file(month: str) -> Path:
    return D_REPORT_DIR / f"naver_search_ranks_{month}.json"


def read_sheet(path: Path, sheet_name: str) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=sheet_name)


def load_state(month: str) -> dict:
    path = state_file(month)
    if not path.exists():
        return {"notes": {}, "planMemo": "", "reportMemo": ""}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(state: dict, month: str) -> None:
    path = state_file(month)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def load_dashboard(month: str | None = None) -> dict:
    selected_month = normalize_month(month)
    path = report_path(selected_month)
    if not path.exists():
        raise FileNotFoundError(f"월간 보고서 파일을 찾을 수 없습니다: {path}")

    monthly = read_sheet(path, "월간요약")
    by_type = read_sheet(path, "유형별성과")
    campaigns = read_sheet(path, "캠페인별성과")
    adgroups = read_sheet(path, "광고그룹별성과")
    inspection = read_sheet(path, "점검대상")
    plan = read_sheet(path, "다음달계획")
    raw = read_sheet(path, "원천데이터")
    search_ranks = load_search_ranks(selected_month)
    keyword_performance = build_keyword_performance(raw, search_ranks)
    state = load_state(selected_month)

    inspection_records = records(inspection)
    for index, row in enumerate(inspection_records):
        key = inspection_key(row, index)
        saved = state.get("notes", {}).get(key, {})
        row["대시보드키"] = key
        row["결정"] = saved.get("decision", "검토중")
        row["담당자메모"] = saved.get("memo", "")

    return {
        "updatedAt": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
        "month": selected_month,
        "availableMonths": available_months(),
        "reportPath": str(path),
        "draftPath": str(draft_file(selected_month)),
        "monthly": records(monthly),
        "typePerformance": records(by_type),
        "campaigns": records(campaigns),
        "adgroups": records(adgroups),
        "keywordPerformance": records(keyword_performance),
        "inspection": inspection_records,
        "plan": records(plan),
        "state": state,
        "summary": summarize(by_type, inspection),
        "dataProfile": data_profile(raw, keyword_performance, selected_month),
        "brandContract": brand_contract(raw, by_type, selected_month),
        "rewardMarketing": reward_marketing(selected_month),
        "shoppingIntegrated": shopping_integrated(keyword_performance, selected_month),
        "rankTraffic": collect_rank_traffic(selected_month),
    }


def load_search_ranks(month: str) -> dict:
    path = search_rank_file(month)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_rank_data() -> dict:
    if not RANK_DATA_FILE.exists():
        return {}
    return json.loads(RANK_DATA_FILE.read_text(encoding="utf-8"))


def slot_label(slot: str) -> str:
    return "오전" if slot == "morning" else "오후" if slot == "afternoon" else slot


def rank_status(rank) -> str:
    if rank in [None, ""]:
        return "미노출"
    if rank == "error":
        return "수집 오류"
    if rank == "blocked":
        return "접속 차단"
    if rank == "outside_top4":
        return "4위 밖"
    try:
        number = int(rank)
    except (TypeError, ValueError):
        return safe_text(rank)
    if number <= 5:
        return "1~5위"
    if number <= 10:
        return "6~10위"
    return "10위권 밖"


def rank_text(rank) -> str:
    if isinstance(rank, int):
        return f"{rank}위"
    return {
        "error": "수집 오류",
        "blocked": "접속 차단",
        "outside_top4": "4위 밖",
    }.get(rank, "미노출")


def rank_bucket(rank) -> str:
    if rank in [None, ""]:
        return "none"
    if rank == "error":
        return "out"
    try:
        number = int(rank)
    except (TypeError, ValueError):
        return "none"
    if number == 1:
        return "one"
    if number <= 3:
        return "top3"
    if number <= 5:
        return "top5"
    if number <= 10:
        return "top10"
    return "out"


def rank_delta(current, previous) -> dict:
    if current in [None, ""] or previous in [None, ""]:
        return {"value": None, "text": "-", "direction": "none"}
    try:
        current_rank = int(current)
        previous_rank = int(previous)
    except (TypeError, ValueError):
        return {"value": None, "text": "-", "direction": "none"}
    change = previous_rank - current_rank
    if change > 0:
        return {"value": change, "text": f"▲{change}", "direction": "up"}
    if change < 0:
        return {"value": change, "text": f"▼{abs(change)}", "direction": "down"}
    return {"value": 0, "text": "-", "direction": "same"}


def shopping_keyword_sort_key(product_id: object, keyword: object) -> tuple[int, str]:
    product_text = safe_text(product_id)
    keyword_text = safe_text(keyword)
    priority = SHOPPING_KEYWORD_ORDER.get(product_text, [])
    if keyword_text in priority:
        return priority.index(keyword_text), keyword_text
    return 100, keyword_text


def collect_rank_traffic(month: str) -> dict:
    data = load_rank_data()
    month_dates = sorted([date_key for date_key in data if date_key.startswith(month)], reverse=True)
    if not month_dates:
        return {
            "sourcePath": str(RANK_DATA_FILE),
            "updatedAt": "",
            "dates": [],
            "slots": [],
            "summaryColumns": [],
            "shoppingRows": [],
            "powerlinkPcRows": [],
            "powerlinkMobileRows": [],
            "latestShopping": [],
            "latestPowerlink": [],
            "slotDetails": [],
        }

    columns = []
    chronological_columns = []
    slots_seen = []
    for date_key in sorted(month_dates):
        slots = data.get(date_key, {})
        for slot in ["morning", "afternoon"]:
            if slot in slots:
                chronological_columns.append({"date": date_key, "slot": slot, "label": f"{date_key[5:]} {slot_label(slot)}"})
    for date_key in month_dates:
        slots = data.get(date_key, {})
        for slot in ["morning", "afternoon"]:
            if slot in slots:
                columns.append({"date": date_key, "slot": slot, "label": f"{date_key[5:]} {slot_label(slot)}"})
                if slot not in slots_seen:
                    slots_seen.append(slot)

    shopping_items = {}
    powerlink_items: dict[str, dict[str, set[str]]] = {}
    for column in columns:
        slot_data = data.get(column["date"], {}).get(column["slot"], {})
        for key, value in slot_data.get("shopping", {}).items():
            shopping_items.setdefault(
                key,
                {
                    "key": key,
                    "keyword": safe_text(value.get("keyword")) or key,
                    "productId": safe_text(value.get("product_id")),
                    "title": safe_text(value.get("title")),
                    "image": safe_text(value.get("image")),
                },
            )
            if value.get("title") and not shopping_items[key].get("title"):
                shopping_items[key]["title"] = safe_text(value.get("title"))
            if value.get("image") and not shopping_items[key].get("image"):
                shopping_items[key]["image"] = safe_text(value.get("image"))
        for campaign, devices in slot_data.get("powerlink", {}).items():
            entry = powerlink_items.setdefault(campaign, {"pc": set(), "mobile": set()})
            for device in ["pc", "mobile"]:
                entry[device].update((devices.get(device) or {}).keys())

    def rank_cell(column: dict, area: str, key: str, campaign: str = "", device: str = "") -> dict:
        slot_data = data.get(column["date"], {}).get(column["slot"], {})
        if area == "shopping":
            value = slot_data.get("shopping", {}).get(key, {})
        else:
            value = slot_data.get("powerlink", {}).get(campaign, {}).get(device, {}).get(key, {})
        rank = value.get("rank") if isinstance(value, dict) else None
        return {
            "rank": rank,
            "text": rank_text(rank),
            "bucket": rank_bucket(rank),
            "status": rank_status(rank),
            "collectedAt": safe_text(value.get("collected_at")) if isinstance(value, dict) else "",
        }

    shopping_rows = []
    for item in shopping_items.values():
        cells = [rank_cell(column, "shopping", item["key"]) for column in columns]
        latest = next((cell for cell in cells if cell["rank"] not in [None, ""]), cells[0] if cells else {})
        shopping_rows.append({**item, "cells": cells, "latestRank": latest.get("rank"), "latestStatus": latest.get("status")})
    shopping_rows.sort(key=lambda row: (row["productId"], *shopping_keyword_sort_key(row["productId"], row["keyword"])))

    def build_powerlink_rows(device: str) -> list[dict]:
        rows = []
        for campaign, devices in powerlink_items.items():
            for keyword in sorted(devices[device]):
                cells = [rank_cell(column, "powerlink", keyword, campaign, device) for column in columns]
                latest = next((cell for cell in cells if cell["rank"] not in [None, ""]), cells[0] if cells else {})
                rows.append({"campaign": campaign, "device": device, "keyword": keyword, "cells": cells, "latestRank": latest.get("rank"), "latestStatus": latest.get("status")})
        rows.sort(key=lambda row: (row["campaign"], safe_number(row.get("latestRank")) or 9999, row["keyword"]))
        return rows

    latest_date = month_dates[0]
    latest_slot = next((slot for slot in ["afternoon", "morning"] if slot in data.get(latest_date, {})), "")
    latest_slot_data = data.get(latest_date, {}).get(latest_slot, {})
    latest_shopping = []
    for key, value in latest_slot_data.get("shopping", {}).items():
        latest_shopping.append(
            {
                "key": key,
                "keyword": safe_text(value.get("keyword")) or key,
                "productId": safe_text(value.get("product_id")),
                "title": safe_text(value.get("title")),
                "image": safe_text(value.get("image")),
                "rank": value.get("rank"),
                "status": rank_status(value.get("rank")),
                "bucket": rank_bucket(value.get("rank")),
                "collectedAt": safe_text(value.get("collected_at")),
            }
        )
    latest_shopping.sort(key=lambda row: (row["productId"], *shopping_keyword_sort_key(row["productId"], row["keyword"])))

    return {
        "sourcePath": str(RANK_DATA_FILE),
        "updatedAt": datetime.fromtimestamp(RANK_DATA_FILE.stat().st_mtime).strftime("%Y-%m-%d %H:%M") if RANK_DATA_FILE.exists() else "",
        "dates": month_dates,
        "slots": slots_seen,
        "summaryColumns": columns,
        "chronologicalColumns": chronological_columns,
        "shoppingRows": shopping_rows,
        "powerlinkPcRows": build_powerlink_rows("pc"),
        "powerlinkMobileRows": build_powerlink_rows("mobile"),
        "latestShopping": latest_shopping,
        "slotDetails": build_rank_slot_details(data, chronological_columns),
        "latestDate": latest_date,
        "latestSlot": latest_slot,
        "latestLabel": f"{latest_date} {slot_label(latest_slot)}" if latest_slot else latest_date,
        "shoppingCount": len(shopping_rows),
    }


def build_rank_slot_details(data: dict, chronological_columns: list[dict]) -> list[dict]:
    details = []

    def previous_column(index: int) -> dict | None:
        return chronological_columns[index - 1] if index > 0 else None

    def shopping_previous_rank(prev: dict | None, key: str):
        if not prev:
            return None
        return data.get(prev["date"], {}).get(prev["slot"], {}).get("shopping", {}).get(key, {}).get("rank")

    def powerlink_previous_rank(prev: dict | None, campaign: str, device: str, keyword: str):
        if not prev:
            return None
        return data.get(prev["date"], {}).get(prev["slot"], {}).get("powerlink", {}).get(campaign, {}).get(device, {}).get(keyword, {}).get("rank")

    for index, column in enumerate(chronological_columns):
        prev = previous_column(index)
        slot_data = data.get(column["date"], {}).get(column["slot"], {})
        by_product: dict[str, dict] = {}
        for key, value in slot_data.get("shopping", {}).items():
            product_id = safe_text(value.get("product_id"))
            product = by_product.setdefault(
                product_id,
                {
                    "productId": product_id,
                    "title": safe_text(value.get("title")) or "더도톰",
                    "image": safe_text(value.get("image")),
                    "items": [],
                },
            )
            if value.get("title") and product["title"] == "더도톰":
                product["title"] = safe_text(value.get("title"))
            if value.get("image") and not product["image"]:
                product["image"] = safe_text(value.get("image"))
            rank = value.get("rank")
            prev_rank = shopping_previous_rank(prev, key)
            product["items"].append(
                {
                    "key": key,
                    "keyword": safe_text(value.get("keyword")) or key,
                    "rank": rank,
                    "bucket": rank_bucket(rank),
                    "text": rank_text(rank),
                    "delta": rank_delta(rank, prev_rank),
                    "collectedAt": safe_text(value.get("collected_at")),
                }
            )
        shopping_products = list(by_product.values())
        for product in shopping_products:
            product["items"].sort(key=lambda row: shopping_keyword_sort_key(product["productId"], row["keyword"]))
        shopping_products.sort(key=lambda row: row["productId"])

        powerlink_sections = []
        for campaign, devices in slot_data.get("powerlink", {}).items():
            section = {"campaign": campaign, "pc": [], "mobile": []}
            for device in ["pc", "mobile"]:
                for keyword, value in (devices.get(device) or {}).items():
                    rank = value.get("rank")
                    prev_rank = powerlink_previous_rank(prev, campaign, device, keyword)
                    section[device].append(
                        {
                            "keyword": keyword,
                            "rank": rank,
                            "bucket": rank_bucket(rank),
                            "text": rank_text(rank),
                            "delta": rank_delta(rank, prev_rank),
                            "collectedAt": safe_text(value.get("collected_at")),
                        }
                    )
                section[device].sort(key=lambda row: (safe_number(row.get("rank")) or 9999, row["keyword"]))
            powerlink_sections.append(section)
        powerlink_sections.sort(key=lambda row: row["campaign"])

        details.append(
            {
                "date": column["date"],
                "slot": column["slot"],
                "slotLabel": slot_label(column["slot"]),
                "label": f"{column['date']} {slot_label(column['slot'])}",
                "previousLabel": f"{prev['date']} {slot_label(prev['slot'])}" if prev else "",
                "shoppingProducts": shopping_products,
                "powerlinkSections": powerlink_sections,
            }
        )
    return details


def build_keyword_performance(raw: pd.DataFrame, search_ranks: dict) -> pd.DataFrame:
    source = raw.copy()
    if "광고유형" not in source.columns:
        source["광고유형"] = source["캠페인명"].map(classify_campaign)

    numeric_columns = ["노출수", "클릭수", "총비용", "전환수", "전환매출"]
    for column in numeric_columns:
        source[column] = pd.to_numeric(source.get(column, 0), errors="coerce").fillna(0)

    group_columns = ["광고유형", "캠페인명", "광고그룹명", "키워드", "상품명"]
    grouped = source.groupby(group_columns, dropna=False)[numeric_columns].sum().reset_index()
    grouped["검색기기"] = grouped["광고그룹명"].map(search_device)
    grouped["실제검색순위"] = grouped.apply(lambda row: actual_search_rank(row, search_ranks), axis=1)
    grouped["순위확인시각"] = grouped.apply(lambda row: rank_checked_at(row, search_ranks), axis=1)
    grouped["순위메모"] = grouped.apply(lambda row: rank_note(row, search_ranks), axis=1)
    grouped["CTR"] = divide(grouped["클릭수"], grouped["노출수"])
    grouped["CPC"] = divide(grouped["총비용"], grouped["클릭수"])
    grouped["CVR"] = divide(grouped["전환수"], grouped["클릭수"])
    grouped["CPA"] = divide(grouped["총비용"], grouped["전환수"])
    grouped["ROAS"] = divide(grouped["전환매출"], grouped["총비용"])
    grouped["판단"] = grouped.apply(keyword_judgement, axis=1)
    grouped["권장조치"] = grouped.apply(keyword_action, axis=1)
    return grouped.sort_values(["총비용", "CPC"], ascending=[False, False])


def search_device(adgroup_name: object) -> str:
    text = safe_text(adgroup_name)
    if "(M)" in text:
        return "모바일"
    if "(PC)" in text:
        return "PC"
    return "공통"


def rank_key(keyword: object, device: object) -> str:
    return f"{safe_text(device)}|{safe_text(keyword).strip()}"


def actual_search_rank(row: pd.Series, search_ranks: dict):
    key = rank_key(row.get("키워드"), row.get("검색기기"))
    rank = search_ranks.get(key, {}).get("rank")
    return rank if rank not in ["", None] else None


def rank_checked_at(row: pd.Series, search_ranks: dict) -> str:
    key = rank_key(row.get("키워드"), row.get("검색기기"))
    return safe_text(search_ranks.get(key, {}).get("checkedAt"))


def rank_note(row: pd.Series, search_ranks: dict) -> str:
    key = rank_key(row.get("키워드"), row.get("검색기기"))
    return safe_text(search_ranks.get(key, {}).get("note"))


def classify_campaign(name: object) -> str:
    text = str(name)
    if text.startswith("파워링크"):
        return "파워링크"
    if text.startswith("쇼핑검색"):
        return "쇼핑검색"
    if text.startswith("브랜드검색"):
        return "브랜드검색"
    return "기타"


def divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator = denominator.replace(0, pd.NA)
    return (numerator / denominator).fillna(0)


def keyword_judgement(row: pd.Series) -> str:
    cost = safe_number(row.get("총비용"))
    clicks = safe_number(row.get("클릭수"))
    conversions = safe_number(row.get("전환수"))
    cpc = safe_number(row.get("CPC"))
    roas = safe_number(row.get("ROAS"))
    keyword = safe_text(row.get("키워드"))
    ad_type = safe_text(row.get("광고유형"))
    actual_rank = safe_number(row.get("실제검색순위"))
    if ad_type == "파워링크" and keyword in CORE_POWERLINK_KEYWORDS:
        if actual_rank == 0:
            return "핵심키워드 순위확인"
        if actual_rank > FIRST_PAGE_RANK_LIMIT:
            return "핵심키워드 입찰상향"
        return "핵심키워드 순위유지"
    if cost >= 100_000 and conversions == 0:
        return "무전환 고비용"
    if clicks >= 50 and conversions == 0:
        return "무전환 클릭누적"
    if cpc >= 3_000 and roas < 3:
        return "고CPC 저효율"
    if cost >= 100_000 and 0 < roas < 3:
        return "저ROAS"
    if roas >= 5 and conversions > 0:
        return "확대후보"
    return "관찰"


def keyword_action(row: pd.Series) -> str:
    judgement = safe_text(row.get("판단"))
    actual_rank = safe_number(row.get("실제검색순위"))
    cpc = safe_number(row.get("CPC"))
    if judgement == "핵심키워드 입찰상향":
        return f"1페이지 기준 밖 실제순위 {actual_rank:.0f}위; CPC {cpc:,.0f}원 확인 후 입찰가 상향"
    if judgement == "핵심키워드 순위확인":
        device = safe_text(row.get("검색기기"))
        note = safe_text(row.get("순위메모"))
        suffix = f" ({note})" if note else ""
        return f"{device} 실제 검색에서 순위 미확인; 수동 확인 또는 다시 갱신 필요{suffix}"
    if judgement == "핵심키워드 순위유지":
        return f"핵심 키워드 실제순위 {actual_rank:.0f}위; 현재 순위 유지, 이탈 시 입찰가 상향"
    if judgement == "무전환 고비용":
        return "검색어/상품 연결 확인 후 입찰가 인하 또는 제외 검토"
    if judgement == "무전환 클릭누적":
        return "전환 없는 클릭 누적; 랜딩/상품 적합성 확인"
    if judgement == "고CPC 저효율":
        return "CPC 대비 성과 낮음; 입찰가 인하 또는 소재/키워드 조정"
    if judgement == "저ROAS":
        return "전환은 있으나 수익성 낮음; 입찰가 인하와 예산 이동 검토"
    if judgement == "확대후보":
        return "효율 유지 시 예산 또는 입찰 소폭 확대"
    return "추이 관찰"


def summarize(by_type: pd.DataFrame, inspection: pd.DataFrame) -> dict:
    target = by_type[by_type["광고유형"].isin(["파워링크", "쇼핑검색"])]
    cost = safe_number(target["총비용"].sum())
    clicks = safe_number(target["클릭수"].sum())
    conversions = safe_number(target["전환수"].sum())
    revenue = safe_number(target["전환매출"].sum())
    impressions = safe_number(target["노출수"].sum())
    return {
        "cost": cost,
        "clicks": clicks,
        "conversions": conversions,
        "revenue": revenue,
        "ctr": clicks / impressions if impressions else 0,
        "cpc": cost / clicks if clicks else 0,
        "cvr": conversions / clicks if clicks else 0,
        "roas": revenue / cost if cost else 0,
        "inspectionCount": int(len(inspection)),
    }


def data_profile(raw: pd.DataFrame, keyword_performance: pd.DataFrame, month: str) -> dict:
    dates = pd.to_datetime(raw.get("날짜"), errors="coerce").dropna()
    period = ""
    if "-" in month:
        year, month_text = month.split("-", 1)
        import calendar

        last_day = calendar.monthrange(int(year), int(month_text))[1]
        today = datetime.now()
        end_day = last_day
        if int(year) == today.year and int(month_text) == today.month and today.day > 1:
            end_day = today.day - 1
        period = f"{year}-{month_text}-01 ~ {year}-{month_text}-{end_day:02d}"
    return {
        "period": period or month,
        "granularity": "월 누적 성과를 광고/키워드 단위로 집계",
        "rawRows": int(len(raw)),
        "detailRows": int(len(keyword_performance)),
        "campaigns": int(raw["캠페인명"].nunique()) if "캠페인명" in raw else 0,
        "adgroups": int(raw["광고그룹명"].nunique()) if "광고그룹명" in raw else 0,
        "sourceDateLabels": [value.strftime("%Y-%m-%d") for value in sorted(dates.unique())],
    }


def brand_contract(raw: pd.DataFrame, by_type: pd.DataFrame, month: str) -> dict:
    brand = raw[raw["캠페인명"].astype(str).str.startswith("브랜드검색")].copy()
    if brand.empty:
        return {
            "status": "계약 정보 없음",
            "period": "",
            "startDate": BRAND_SEARCH_CONTRACT["startDate"],
            "endDate": BRAND_SEARCH_CONTRACT["endDate"],
            "pcAmount": BRAND_SEARCH_CONTRACT["pcAmount"],
            "mobileAmount": BRAND_SEARCH_CONTRACT["mobileAmount"],
            "totalAmount": BRAND_SEARCH_CONTRACT["pcAmount"] + BRAND_SEARCH_CONTRACT["mobileAmount"],
            "monthlyAmount": (BRAND_SEARCH_CONTRACT["pcAmount"] + BRAND_SEARCH_CONTRACT["mobileAmount"]) / 3,
            "payment": BRAND_SEARCH_CONTRACT["payment"],
            "areas": BRAND_SEARCH_CONTRACT["areas"],
            "memo": BRAND_SEARCH_CONTRACT["memo"],
            "checkPoint": "브랜드명/브랜드 연관 키워드 검색 시 상단 브랜드 영역 노출 여부와 노출 추이 확인",
            "impressions": 0,
            "clicks": 0,
            "conversions": 0,
            "revenue": 0,
            "keywords": [],
        }
    for column in ["노출수", "클릭수", "전환수", "전환매출"]:
        brand[column] = pd.to_numeric(brand.get(column, 0), errors="coerce").fillna(0)
    keyword_summary = (
        brand.groupby("키워드", dropna=False)[["노출수", "클릭수"]]
        .sum()
        .reset_index()
        .sort_values("노출수", ascending=False)
        .head(8)
    )
    status = "2026년 5월 시작 3개월 계약"
    period = "2026년 5월 ~ 3개월"
    if month < "2026-05":
        status = "2026년 5월 시작 예정 계약"
        period = "2026년 5월 ~ 3개월 예정"
    return {
        "status": status,
        "period": period,
        "checkPoint": "브랜드명/브랜드 연관 키워드 검색 시 상단 브랜드 영역 노출 여부와 노출 추이 확인",
        "startDate": BRAND_SEARCH_CONTRACT["startDate"],
        "endDate": BRAND_SEARCH_CONTRACT["endDate"],
        "pcAmount": BRAND_SEARCH_CONTRACT["pcAmount"],
        "mobileAmount": BRAND_SEARCH_CONTRACT["mobileAmount"],
        "totalAmount": BRAND_SEARCH_CONTRACT["pcAmount"] + BRAND_SEARCH_CONTRACT["mobileAmount"],
        "monthlyAmount": (BRAND_SEARCH_CONTRACT["pcAmount"] + BRAND_SEARCH_CONTRACT["mobileAmount"]) / 3,
        "payment": BRAND_SEARCH_CONTRACT["payment"],
        "areas": BRAND_SEARCH_CONTRACT["areas"],
        "memo": BRAND_SEARCH_CONTRACT["memo"],
        "impressions": int(brand["노출수"].sum()),
        "clicks": int(brand["클릭수"].sum()),
        "conversions": int(brand["전환수"].sum()),
        "revenue": float(brand["전환매출"].sum()),
        "keywords": records(keyword_summary),
    }


def reward_marketing(month: str) -> dict:
    period_start, period_end = period_dates(month)
    rank_images = rank_product_assets(month)
    items = []
    active_cost = 0
    total_cost = 0
    for item in REWARD_MARKETING_ITEMS:
        days = item.get("days") or max(overlap_days(item["startDate"], item["endDate"], parse_date(item["startDate"]), parse_date(item["endDate"])), 1)
        item_overlap = overlap_days(item["startDate"], item["endDate"], period_start, period_end)
        daily_amount = safe_number(item["totalAmount"]) / max(safe_number(days), 1)
        recognized_amount = daily_amount * item_overlap
        total_cost += safe_number(item["totalAmount"])
        active_cost += recognized_amount
        row = dict(item)
        row.update(
            {
                "overlapDays": item_overlap,
                "recognizedAmount": recognized_amount,
                "dailyAmount": daily_amount,
                "isActiveInPeriod": item_overlap > 0,
                "image": rank_images.get(safe_text(item.get("productId")), {}).get("image", ""),
                "rankTitle": rank_images.get(safe_text(item.get("productId")), {}).get("title", ""),
            }
        )
        items.append(row)
    return {
        "period": f"{period_start.strftime('%Y-%m-%d')} ~ {period_end.strftime('%Y-%m-%d')}",
        "items": items,
        "activeAmount": active_cost,
        "contractAmount": total_cost,
        "activeCount": sum(1 for item in items if item["isActiveInPeriod"]),
        "memo": "쇼핑검색 상품 순위 트래픽 보강 비용으로 광고비와 분리해 관리",
    }


def rank_product_assets(month: str) -> dict:
    data = load_rank_data()
    assets: dict[str, dict[str, str]] = {}
    for date_key in sorted([key for key in data if key.startswith(month)], reverse=True):
        for slot in ["afternoon", "morning"]:
            shopping = data.get(date_key, {}).get(slot, {}).get("shopping", {})
            for value in shopping.values():
                product_id = safe_text(value.get("product_id"))
                if not product_id:
                    continue
                current = assets.setdefault(product_id, {"image": "", "title": ""})
                if value.get("image") and not current["image"]:
                    current["image"] = safe_text(value.get("image"))
                if value.get("title") and not current["title"]:
                    current["title"] = safe_text(value.get("title"))
    return assets


def shopping_integrated(keyword_performance: pd.DataFrame, month: str) -> dict:
    shopping = keyword_performance[keyword_performance["광고유형"] == "쇼핑검색"].copy()
    reward = reward_marketing(month)
    ad_cost = float(pd.to_numeric(shopping.get("총비용", 0), errors="coerce").fillna(0).sum()) if not shopping.empty else 0
    clicks = float(pd.to_numeric(shopping.get("클릭수", 0), errors="coerce").fillna(0).sum()) if not shopping.empty else 0
    conversions = float(pd.to_numeric(shopping.get("전환수", 0), errors="coerce").fillna(0).sum()) if not shopping.empty else 0
    revenue = float(pd.to_numeric(shopping.get("전환매출", 0), errors="coerce").fillna(0).sum()) if not shopping.empty else 0
    assist_cost = reward["activeAmount"]
    blended_cost = ad_cost + assist_cost
    return {
        "adCost": ad_cost,
        "rewardCost": assist_cost,
        "blendedCost": blended_cost,
        "clicks": clicks,
        "conversions": conversions,
        "revenue": revenue,
        "adRoas": revenue / ad_cost if ad_cost else 0,
        "blendedRoas": revenue / blended_cost if blended_cost else 0,
        "rewardMemo": "리워드/슬롯 비용은 네이버 광고 API 비용이 아니므로 쇼핑검색 보조비로 별도 합산",
        "targetRank": "네이버 쇼핑 검색 순위 1페이지 1~5위",
    }


def inspection_key(row: dict, index: int) -> str:
    parts = [
        safe_text(row.get("광고유형")),
        safe_text(row.get("캠페인명")),
        safe_text(row.get("광고그룹명")),
        safe_text(row.get("키워드")),
        safe_text(row.get("상품명")),
    ]
    return "|".join(parts) or f"row-{index}"


def save_note(payload: dict, month: str) -> dict:
    state = load_state(month)
    key = safe_text(payload.get("key"))
    if not key:
        raise ValueError("key is required")
    state.setdefault("notes", {})[key] = {
        "decision": safe_text(payload.get("decision")) or "검토중",
        "memo": safe_text(payload.get("memo")),
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
    }
    save_state(state, month)
    return {"ok": True}


def save_memo(payload: dict, month: str) -> dict:
    state = load_state(month)
    state["planMemo"] = safe_text(payload.get("planMemo"))
    state["reportMemo"] = safe_text(payload.get("reportMemo"))
    state["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    save_state(state, month)
    return {"ok": True}


def month_label(month: str) -> str:
    year, month_num = month.split("-")
    return f"{year}년 {int(month_num)}월"


def month_period(month: str) -> str:
    year, month_num = month.split("-")
    today = datetime.now()
    if month_num == "02":
        end_day = 29 if int(year) % 4 == 0 else 28
    elif month_num in {"04", "06", "09", "11"}:
        end_day = 30
    else:
        end_day = 31
    if int(year) == today.year and int(month_num) == today.month and today.day > 1:
        end_day = today.day - 1
    return f"{year}.{month_num}.01 - {year}.{month_num}.{end_day:02d}"


def money(value) -> str:
    return f"₩{safe_number(value):,.0f}"


def count(value) -> str:
    return f"{safe_number(value):,.0f}"


def ratio(value) -> str:
    return f"{safe_number(value):.2f}"


def percent(value) -> str:
    return f"{safe_number(value) * 100:.1f}%"


def td(value, class_name: str = "") -> str:
    class_attr = f' class="{class_name}"' if class_name else ""
    return f"<td{class_attr}>{escape(safe_text(value))}</td>"


def build_rows(rows: list[dict], columns: list[tuple[str, str, str]]) -> str:
    body = []
    for row in rows:
        cells = []
        for key, formatter, class_name in columns:
            value = row.get(key)
            if formatter == "money":
                rendered = money(value)
            elif formatter == "count":
                rendered = count(value)
            elif formatter == "ratio":
                rendered = ratio(value)
            elif formatter == "percent":
                rendered = percent(value)
            else:
                rendered = safe_text(value)
            cells.append(td(rendered, class_name))
        body.append(f"<tr>{''.join(cells)}</tr>")
    return "\n".join(body)


def build_designed_report(data: dict) -> str:
    month = data["month"]
    summary = data["summary"]
    state = data["state"]
    type_rows = data["typePerformance"]
    campaign_rows = sorted(data["campaigns"], key=lambda row: safe_number(row.get("총비용")), reverse=True)[:10]
    inspection_rows = data["inspection"]
    plan_rows = data["plan"]
    keyword_rows = data["keywordPerformance"]
    brand = data["brandContract"]
    reward = data["rewardMarketing"]
    shopping_mix = data["shoppingIntegrated"]
    core_rows = [
        row
        for row in keyword_rows
        if row.get("광고유형") == "파워링크" and safe_text(row.get("키워드")).strip() in CORE_POWERLINK_KEYWORDS
    ]
    core_rows = sorted(core_rows, key=lambda row: (safe_text(row.get("검색기기")), safe_text(row.get("키워드"))))

    type_table = build_rows(
        type_rows,
        [
            ("광고유형", "text", ""),
            ("총비용", "money", "num"),
            ("클릭수", "count", "num"),
            ("전환수", "count", "num"),
            ("전환매출", "money", "num"),
            ("ROAS", "ratio", "num"),
        ],
    )
    campaign_table = build_rows(
        campaign_rows,
        [
            ("캠페인명", "text", ""),
            ("총비용", "money", "num"),
            ("전환수", "count", "num"),
            ("전환매출", "money", "num"),
            ("ROAS", "ratio", "num"),
            ("판단", "text", "center"),
        ],
    )
    core_table = build_rows(
        core_rows,
        [
            ("키워드", "text", ""),
            ("검색기기", "text", "center"),
            ("실제검색순위", "text", "center"),
            ("CPC", "money", "num"),
            ("전환수", "count", "num"),
            ("ROAS", "ratio", "num"),
            ("권장조치", "text", ""),
        ],
    )
    inspection_table = build_rows(
        inspection_rows[:12],
        [
            ("광고유형", "text", "center"),
            ("캠페인명", "text", ""),
            ("키워드", "text", ""),
            ("점검사유", "text", ""),
            ("권장조치", "text", ""),
            ("결정", "text", "center"),
        ],
    )
    plan_table = build_rows(
        plan_rows,
        [
            ("구분", "text", "center"),
            ("대상", "text", ""),
            ("계획", "text", ""),
            ("근거", "text", ""),
        ],
    )
    reward_table = build_rows(
        reward.get("items", []),
        [
            ("productName", "text", ""),
            ("keyword", "text", "center"),
            ("startDate", "text", "center"),
            ("endDate", "text", "center"),
            ("recognizedAmount", "money", "num"),
            ("totalAmount", "money", "num"),
            ("status", "text", "center"),
        ],
    )
    brand_keywords = ", ".join(
        [
            f"{safe_text(row.get('키워드'))} {count(row.get('노출수'))}회"
            for row in brand.get("keywords", [])[:5]
            if safe_text(row.get("키워드"))
        ]
    )

    plan_memo = escape(state.get("planMemo") or "추가 운영 계획 없음")
    report_memo = escape(state.get("reportMemo") or "보고서 코멘트 없음")

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(month_label(month))} 네이버 광고 월간 보고서</title>
  <style>
    :root {{
      --green: #03a66a;
      --ink: #102033;
      --muted: #607086;
      --line: #dbe3eb;
      --soft: #f4f7f9;
      --warn: #b57b12;
      --red: #c84646;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: #eef2f5;
      color: var(--ink);
      font-family: Arial, "Malgun Gothic", sans-serif;
      font-size: 14px;
      line-height: 1.5;
    }}
    .page {{
      width: 1120px;
      margin: 28px auto;
      background: #fff;
      border: 1px solid var(--line);
      box-shadow: 0 18px 48px rgba(15, 32, 51, .12);
    }}
    header {{
      padding: 34px 42px 26px;
      border-bottom: 4px solid var(--green);
      display: flex;
      justify-content: space-between;
      gap: 40px;
      align-items: flex-start;
    }}
    .brand {{ color: var(--green); font-weight: 800; letter-spacing: 0; }}
    h1 {{ margin: 8px 0 10px; font-size: 30px; line-height: 1.2; }}
    h2 {{ margin: 0 0 14px; font-size: 18px; }}
    h3 {{ margin: 0 0 10px; font-size: 15px; }}
    .meta {{ color: var(--muted); }}
    .summary-box {{
      min-width: 280px;
      padding: 18px;
      background: var(--soft);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .summary-box strong {{ display: block; font-size: 22px; margin-top: 4px; }}
    main {{ padding: 30px 42px 42px; }}
    .kpis {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
      margin-bottom: 26px;
    }}
    .kpi {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 15px 16px;
      background: #fff;
    }}
    .kpi span {{ color: var(--muted); font-size: 12px; font-weight: 700; }}
    .kpi strong {{ display: block; margin-top: 6px; font-size: 22px; }}
    section {{ margin-top: 28px; }}
    .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      background: #fff;
    }}
    table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
    th, td {{
      border-bottom: 1px solid #e9eef2;
      padding: 9px 8px;
      vertical-align: top;
      word-break: keep-all;
      overflow-wrap: anywhere;
    }}
    th {{ background: #f6f8fa; color: #304256; font-size: 12px; }}
    .num {{ text-align: right; white-space: nowrap; }}
    .center {{ text-align: center; }}
    .memo {{
      min-height: 76px;
      padding: 14px;
      border: 1px solid var(--line);
      background: #fbfcfd;
      border-radius: 8px;
      white-space: pre-wrap;
    }}
    .note-list {{
      margin: 0;
      padding-left: 18px;
      color: var(--muted);
    }}
    .contract {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
    }}
    .contract div {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #fbfcfd;
    }}
    .contract span {{ display: block; color: var(--muted); font-size: 12px; }}
    .contract strong {{ display: block; margin-top: 4px; font-size: 16px; }}
    footer {{
      padding: 18px 42px 26px;
      color: var(--muted);
      border-top: 1px solid var(--line);
      font-size: 12px;
    }}
    @media print {{
      body {{ background: #fff; }}
      .page {{ width: auto; margin: 0; border: 0; box-shadow: none; }}
      section {{ break-inside: avoid; }}
    }}
  </style>
</head>
<body>
  <article class="page">
    <header>
      <div>
        <div class="brand">NAVER ADS MONTHLY REPORT</div>
        <h1>{escape(month_label(month))} 네이버 광고 월간 보고서</h1>
        <div class="meta">분석 기간 {escape(month_period(month))} · 생성 {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
      </div>
      <div class="summary-box">
        <div class="meta">이번 달 핵심 판단</div>
        <strong>ROAS {ratio(summary["roas"])}</strong>
        <div class="meta">점검대상 {count(len(inspection_rows))}건 · 전환 {count(summary["conversions"])}건</div>
      </div>
    </header>
    <main>
      <div class="kpis">
        <div class="kpi"><span>총 광고비</span><strong>{money(summary["cost"])}</strong></div>
        <div class="kpi"><span>전환매출</span><strong>{money(summary["revenue"])}</strong></div>
        <div class="kpi"><span>CTR / CPC</span><strong>{percent(summary["ctr"])} · {money(summary["cpc"])}</strong></div>
        <div class="kpi"><span>CVR</span><strong>{percent(summary["cvr"])}</strong></div>
      </div>

      <section>
        <h2>쇼핑검색 통합 운영 비용</h2>
        <div class="contract">
          <div><span>쇼핑검색 광고비</span><strong>{money(shopping_mix.get("adCost"))}</strong></div>
          <div><span>리워드 인정 비용</span><strong>{money(shopping_mix.get("rewardCost"))}</strong></div>
          <div><span>통합 기준 ROAS</span><strong>{ratio(shopping_mix.get("blendedRoas"))}</strong></div>
        </div>
        <p class="meta">{escape(safe_text(shopping_mix.get("rewardMemo")))} · 목표: {escape(safe_text(shopping_mix.get("targetRank")))}</p>
      </section>

      <section class="grid-2">
        <div class="panel">
          <h2>운영 요약</h2>
          <ul class="note-list">
            <li>파워링크 핵심 키워드는 감액 대상이 아니라 실제 검색 순위 기준으로 입찰가와 노출 순위를 관리합니다.</li>
            <li>쇼핑검색은 키워드 순위보다 상품·소재 효율과 전환 성과를 기준으로 판단합니다.</li>
            <li>브랜드검색은 2026년 5월부터 3개월 계약 노출 상태를 확인하는 항목으로 관리합니다.</li>
          </ul>
        </div>
        <div class="panel">
          <h2>보고서 코멘트</h2>
          <div class="memo">{report_memo}</div>
        </div>
      </section>

      <section>
        <h2>광고유형별 성과</h2>
        <table>
          <thead><tr><th>유형</th><th>비용</th><th>클릭</th><th>전환</th><th>매출</th><th>ROAS</th></tr></thead>
          <tbody>{type_table}</tbody>
        </table>
      </section>

      <section>
        <h2>캠페인 성과 및 판단</h2>
        <table>
          <thead><tr><th>캠페인</th><th>비용</th><th>전환</th><th>매출</th><th>ROAS</th><th>판단</th></tr></thead>
          <tbody>{campaign_table}</tbody>
        </table>
      </section>

      <section>
        <h2>파워링크 핵심 키워드 순위 관리</h2>
        <table>
          <thead><tr><th>키워드</th><th>기기</th><th>실제순위</th><th>CPC</th><th>전환</th><th>ROAS</th><th>권장조치</th></tr></thead>
          <tbody>{core_table or '<tr><td colspan="7" class="center">핵심 키워드 데이터가 없습니다.</td></tr>'}</tbody>
        </table>
      </section>

      <section>
        <h2>점검대상 및 조치 결정</h2>
        <table>
          <thead><tr><th>유형</th><th>캠페인</th><th>키워드/상품</th><th>점검사유</th><th>권장조치</th><th>결정</th></tr></thead>
          <tbody>{inspection_table or '<tr><td colspan="6" class="center">점검대상이 없습니다.</td></tr>'}</tbody>
        </table>
      </section>

      <section>
        <h2>다음달 진행 계획</h2>
        <table>
          <thead><tr><th>구분</th><th>대상</th><th>계획</th><th>근거</th></tr></thead>
          <tbody>{plan_table}</tbody>
        </table>
      </section>

      <section>
        <h2>리워드 마케팅 운영 내역</h2>
        <table>
          <thead><tr><th>상품</th><th>키워드</th><th>시작</th><th>종료</th><th>보고기간 비용</th><th>총 계약금</th><th>상태</th></tr></thead>
          <tbody>{reward_table or '<tr><td colspan="7" class="center">리워드 마케팅 내역이 없습니다.</td></tr>'}</tbody>
        </table>
      </section>

      <section class="panel">
        <h2>브랜드검색 계약 확인</h2>
        <div class="contract">
          <div><span>계약 상태</span><strong>{escape(safe_text(brand.get("status")))}</strong></div>
          <div><span>계약 기간</span><strong>{escape(safe_text(brand.get("period")))}</strong></div>
          <div><span>총 계약 금액</span><strong>{money(brand.get("totalAmount"))}</strong></div>
        </div>
        <p class="meta">PC {money(brand.get("pcAmount"))} · 모바일 {money(brand.get("mobileAmount"))} · 월 환산 {money(brand.get("monthlyAmount"))} · {escape(safe_text(brand.get("payment")))}</p>
        <p class="meta">{escape(safe_text(brand.get("checkPoint")))}</p>
        <p class="meta">주요 브랜드 키워드 노출: {escape(brand_keywords or "확인 가능한 브랜드 키워드 데이터 없음")}</p>
      </section>

      <section>
        <h2>추가 운영 계획</h2>
        <div class="memo">{plan_memo}</div>
      </section>
    </main>
    <footer>
      보고서 파일: {escape(safe_text(data.get("reportPath")))} · 대시보드 기준 데이터로 자동 생성
    </footer>
  </article>
</body>
</html>
"""


def build_draft(month: str) -> dict:
    data = load_dashboard(month)
    state = data["state"]
    summary = data["summary"]
    type_rows = data["typePerformance"]
    inspection_rows = data["inspection"]
    plan_rows = data["plan"]

    lines = [
        f"# {month_label(data['month'])} 네이버 광고 월간 보고서 초안",
        "",
        "## 1. 전체 요약",
        "",
        f"- 파워링크+쇼핑검색 총 광고비: {summary['cost']:,.0f}원",
        f"- 전환: {summary['conversions']:,.0f}건 / 전환매출: {summary['revenue']:,.0f}원",
        f"- ROAS: {summary['roas']:.2f} / CTR: {summary['ctr']:.2%} / CVR: {summary['cvr']:.2%}",
        "",
        "## 2. 유형별 성과",
        "",
    ]
    for row in type_rows:
        lines.append(
            f"- {row.get('광고유형')}: 비용 {safe_number(row.get('총비용')):,.0f}원, "
            f"전환 {safe_number(row.get('전환수')):,.0f}건, ROAS {safe_number(row.get('ROAS')):.2f}"
        )

    lines.extend(["", "## 3. 점검 대상", ""])
    for row in inspection_rows:
        lines.append(
            f"- [{row.get('결정')}] {row.get('캠페인명')} / {row.get('키워드')}: "
            f"{row.get('점검사유')} → {row.get('권장조치')}"
        )
        if row.get("담당자메모"):
            lines.append(f"  - 메모: {row.get('담당자메모')}")

    lines.extend(["", "## 4. 다음달 진행 계획", ""])
    for row in plan_rows:
        lines.append(f"- {row.get('구분')} / {row.get('대상')}: {row.get('계획')} ({row.get('근거')})")

    if state.get("planMemo"):
        lines.extend(["", "## 5. 운영자 추가 계획", "", state["planMemo"]])
    if state.get("reportMemo"):
        lines.extend(["", "## 6. 보고서 작성 메모", "", state["reportMemo"]])

    target = draft_file(data["month"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report_target = designed_report_file(data["month"])
    report_target.parent.mkdir(parents=True, exist_ok=True)
    report_target.write_text(build_designed_report(data), encoding="utf-8")
    return {
        "ok": True,
        "draftPath": str(target),
        "reportPath": str(report_target),
        "reportUrl": f"/report?month={data['month']}",
    }


def update_search_ranks(month: str) -> dict:
    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "update_naver_search_ranks.py"),
        "--output",
        str(search_rank_file(month)),
    ]
    completed = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=90)
    if completed.returncode != 0:
        return {"ok": False, "stdout": completed.stdout, "stderr": completed.stderr}
    return {"ok": True, "stdout": completed.stdout, "stderr": completed.stderr}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        month = normalize_month((query.get("month") or [""])[0])
        if parsed.path in ["/", "/dashboard"]:
            self.send_file(HTML_FILE, "text/html; charset=utf-8")
            return
        if parsed.path == "/rank-dashboard":
            if not RANK_DASHBOARD_FILE.exists():
                self.send_error(404, f"rank dashboard not found: {RANK_DASHBOARD_FILE}")
                return
            self.send_file(RANK_DASHBOARD_FILE, "text/html; charset=utf-8")
            return
        if parsed.path == "/report":
            report = designed_report_file(month)
            if not report.exists():
                build_draft(month)
            self.send_file(report, "text/html; charset=utf-8")
            return
        if parsed.path == "/api/monthly-dashboard":
            self.send_json(load_dashboard(month))
            return
        if parsed.path == "/api/export-draft":
            self.send_json(build_draft(month))
            return
        if parsed.path == "/api/update-ranks":
            self.send_json(update_search_ranks(month))
            return
        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        month = normalize_month((query.get("month") or [""])[0])
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        if parsed.path == "/api/note":
            self.send_json(save_note(payload, month))
            return
        if parsed.path == "/api/memo":
            self.send_json(save_memo(payload, month))
            return
        self.send_error(404)

    def log_message(self, format: str, *args) -> None:
        return

    def send_file(self, path: Path, content_type: str) -> None:
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 8790), Handler)
    print("Monthly Naver ads dashboard local: http://127.0.0.1:8790")
    print("Monthly Naver ads dashboard LAN: http://192.168.0.9:8790")
    server.serve_forever()


if __name__ == "__main__":
    main()
