from __future__ import annotations

import argparse
import ast
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


METRICS = ["노출수", "클릭수", "총비용", "전환수", "전환매출"]


def number(value: Any) -> float:
    try:
        return 0.0 if value is None or pd.isna(value) else float(value)
    except (TypeError, ValueError):
        return 0.0


def whole(value: Any) -> int | float:
    value = number(value)
    return int(round(value)) if abs(value - round(value)) < 0.000001 else value


def clean(value: Any) -> str:
    try:
        if value is None or pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def campaign_type(value: Any) -> str:
    text = clean(value)
    if "브랜드" in text:
        return "브랜드검색"
    if "쇼핑" in text:
        return "쇼핑검색"
    return "파워링크"


def metrics(row: dict[str, Any]) -> dict[str, Any]:
    impressions = number(row.get("노출수"))
    clicks = number(row.get("클릭수"))
    cost = number(row.get("총비용"))
    conversions = number(row.get("전환수"))
    revenue = number(row.get("전환매출"))
    row.update(
        CTR=clicks / impressions if impressions else 0.0,
        CPC=cost / clicks if clicks else 0.0,
        CVR=conversions / clicks if clicks else 0.0,
        CPA=cost / conversions if conversions else 0.0,
        ROAS=revenue / cost if cost else 0.0,
    )
    return row


def aggregate(frame: pd.DataFrame, keys: list[str]) -> list[dict[str, Any]]:
    grouped = frame.groupby(keys, dropna=False, as_index=False)[METRICS].sum()
    rows = []
    for item in grouped.to_dict("records"):
        row = {key: (None if pd.isna(item.get(key)) else item.get(key)) for key in keys}
        row.update({key: whole(item.get(key)) for key in METRICS})
        rows.append(metrics(row))
    return sorted(rows, key=lambda row: (number(row.get("총비용")), number(row.get("전환매출"))), reverse=True)


def week_index(date_text: str) -> int:
    day = int(date_text[8:10])
    return 0 if day <= 7 else 1 if day <= 14 else 2 if day <= 21 else 3 if day <= 28 else 4


def parse_product(value: Any) -> dict[str, Any]:
    text = clean(value)
    if text.startswith("{") and text.endswith("}"):
        try:
            parsed = ast.literal_eval(text)
            return parsed if isinstance(parsed, dict) else {}
        except (SyntaxError, ValueError):
            return {}
    return {"productName": text} if text else {}


def image_url(value: Any) -> str:
    text = clean(value)
    if text.startswith("/"):
        return "https://shopping-phinf.pstatic.net" + text
    return text


def build_inspection(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for source in rows:
        cost, roas, clicks, ctr = map(number, (source.get("총비용"), source.get("ROAS"), source.get("클릭수"), source.get("CTR")))
        if cost >= 100000 and roas < 3:
            reason = "비용 10만원 이상, ROAS 300% 미만"
            action = "입찰가 인하, 저수익 상품 제외, 전환 좋은 유사 키워드로 예산 이동"
        elif clicks >= 50 and ctr < 0.01:
            reason = "클릭은 있으나 CTR 1% 미만"
            action = "소재/상품명 개선, 연관성 낮은 검색어 제외"
        else:
            continue
        row = dict(source)
        row.update(점검사유=reason, 권장조치=action, 결정="검토중", 담당자메모="")
        row["대시보드키"] = "|".join(clean(row.get(key)) for key in ["광고유형", "캠페인명", "광고그룹명", "키워드", "상품명"])
        result.append(row)
    return result[:12]


def build_shopping(frame: pd.DataFrame, existing: dict[str, Any], raw_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    shop = frame[frame["광고유형"] == "쇼핑검색"].copy()
    dates = sorted(shop["날짜"].dropna().unique().tolist())
    old_items = (existing.get("dailyProductCosts") or {}).get("items") or []
    old_by_id = {clean(item.get("productId")): item for item in old_items if clean(item.get("productId"))}
    old_by_group = {(clean(item.get("campaign")), clean(item.get("adgroup"))): item for item in old_items}
    grouped: dict[str, dict[str, Any]] = {}
    for _, row in shop.iterrows():
        campaign, adgroup, product_id = clean(row.get("캠페인명")), clean(row.get("광고그룹명")), clean(row.get("상품 ID"))
        parsed = parse_product(row.get("상품명"))
        product_name = clean(parsed.get("productName")) or clean(row.get("소재명")) or adgroup
        prior = old_by_id.get(product_id) or old_by_group.get((campaign, adgroup)) or {}
        key = product_id or f"{campaign}|{adgroup}|{product_name}"
        item = grouped.setdefault(key, {
            "campaign": campaign, "adgroup": adgroup, "adProductName": adgroup,
            "productName": product_name, "productId": product_id,
            "link": clean(prior.get("link")), "image": image_url(parsed.get("imagePath")) or clean(prior.get("image")),
            "rankTitle": clean(prior.get("rankTitle")) or product_name,
            "totalCost": 0.0, "clicks": 0.0, "conversions": 0.0, "revenue": 0.0, "daily": {},
        })
        date_text = clean(row.get("날짜"))
        day = item["daily"].setdefault(date_text, {"date": date_text, "cost": 0.0, "clicks": 0.0, "conversions": 0.0, "revenue": 0.0, "impressions": 0.0})
        values = {"cost": number(row.get("총비용")), "clicks": number(row.get("클릭수")), "conversions": number(row.get("전환수")), "revenue": number(row.get("전환매출")), "impressions": number(row.get("노출수"))}
        for field, value in values.items():
            day[field] += value
        item["totalCost"] += values["cost"]
        item["clicks"] += values["clicks"]
        item["conversions"] += values["conversions"]
        item["revenue"] += values["revenue"]
    items = []
    for item in grouped.values():
        item["daily"] = [{key: (whole(value) if key != "date" else value) for key, value in day.items()} for day in sorted(item["daily"].values(), key=lambda value: value["date"])]
        for field in ["totalCost", "clicks", "conversions", "revenue"]:
            item[field] = whole(item[field])
        item["avgDailyCost"] = number(item["totalCost"]) / len(dates) if dates else 0.0
        item["cpc"] = number(item["totalCost"]) / number(item["clicks"]) if number(item["clicks"]) else 0.0
        item["roas"] = number(item["revenue"]) / number(item["totalCost"]) if number(item["totalCost"]) else 0.0
        items.append(item)
    items.sort(key=lambda item: (number(item.get("totalCost")), number(item.get("revenue"))), reverse=True)
    totals = {field: whole(shop[column].sum()) for field, column in {"cost": "총비용", "clicks": "클릭수", "conversions": "전환수", "revenue": "전환매출"}.items()}
    integrated = {"adCost": totals["cost"], "clicks": totals["clicks"], "conversions": totals["conversions"], "revenue": totals["revenue"], "adRoas": number(totals["revenue"]) / number(totals["cost"]) if number(totals["cost"]) else 0.0, "memo": "네이버 쇼핑검색 광고 API 기준 성과입니다. 리워드/슬롯 비용은 순위 트래픽에서 별도 관리합니다."}
    period = f"{dates[0]} ~ {dates[-1]}" if dates else ""
    daily = {"sourcePath": str(raw_path), "dates": dates, "items": items, "totalCost": totals["cost"], "summary": f"{period} 쇼핑검색 상품/소재별 일 광고비"}
    return integrated, daily


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", required=True)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    args = parser.parse_args()
    target = args.data_dir / f"monthly-dashboard-{args.month}.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    frame = pd.read_excel(args.raw)
    # Brand keyword and creative stats describe the same traffic.
    # Keep keyword rows so clicks, conversions, and revenue are not doubled.
    brand_creative = (
        frame["\ucea0\ud398\uc778\uba85"].astype(str).str.contains("\ube0c\ub79c\ub4dc", na=False)
        & frame["\uc18c\uc7ac ID"].fillna("").astype(str).str.strip().ne("")
    )
    frame = frame.loc[~brand_creative].copy()
    for column in METRICS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
    frame["날짜"] = frame["날짜"].astype(str).str[:10]
    frame["광고유형"] = frame["캠페인명"].map(campaign_type)
    frame["키워드"] = frame["키워드"].where(frame["키워드"].notna(), None)
    frame["상품명"] = frame["상품명"].where(frame["상품명"].notna(), frame["소재명"])
    types = aggregate(frame, ["광고유형"])
    campaigns = aggregate(frame, ["광고유형", "캠페인명"])
    adgroups = aggregate(frame, ["광고유형", "캠페인명", "광고그룹명"])
    details = aggregate(frame, ["광고유형", "캠페인명", "광고그룹명", "키워드", "상품명"])
    for row in details:
        row.update(검색기기="공통", 실제검색순위=None, 순위확인시각="", 순위메모="")
        row["판단"] = "확대후보" if number(row.get("ROAS")) >= 5 and number(row.get("총비용")) >= 10000 else "유지"
        row["권장조치"] = "효율 유지 시 예산 또는 입찰 소폭 확대" if row["판단"] == "확대후보" else "성과 추적"
    dates = sorted(frame["날짜"].dropna().unique().tolist())
    totals = {column: whole(frame[column].sum()) for column in METRICS}
    total_metrics = metrics(dict(totals))
    period = f"{dates[0]} ~ {dates[-1]}"
    inspection = build_inspection(details)
    data.update(
        monthly=[{"항목": "보고기간", "내용": period}, {"항목": "원천 행 수", "내용": len(frame)}, {"항목": "상세 행 수", "내용": len(details)}, {"항목": "총비용", "내용": totals["총비용"]}, {"항목": "전환매출", "내용": totals["전환매출"]}, {"항목": "ROAS", "내용": total_metrics["ROAS"]}],
        typePerformance=types, campaigns=campaigns, adgroups=adgroups, keywordPerformance=details, inspection=inspection,
        summary={"cost": totals["총비용"], "clicks": totals["클릭수"], "conversions": totals["전환수"], "revenue": totals["전환매출"], "ctr": total_metrics["CTR"], "cpc": total_metrics["CPC"], "cvr": total_metrics["CVR"], "roas": total_metrics["ROAS"], "inspectionCount": len(inspection)},
        dataProfile={"period": period, "granularity": "월 누적 성과를 광고/키워드 단위로 집계", "rawRows": len(frame), "detailRows": len(details), "campaigns": len(campaigns), "adgroups": len(adgroups), "sourceDateLabels": dates},
    )
    data["shoppingIntegrated"], data["dailyProductCosts"] = build_shopping(frame, data, args.raw)
    weeks = [0, 0, 0, 0, 0]
    for date_text, value in frame.groupby("날짜")["총비용"].sum().items():
        weeks[week_index(str(date_text))] += int(round(number(value)))
    metrics_data = data.setdefault("totalSalesMetrics", {})
    rows = metrics_data.setdefault("autoAdCosts", [])
    naver = next((row for row in rows if row.get("name") == "네이버 광고 자동수집"), None)
    if naver is None:
        naver = {"name": "네이버 광고 자동수집"}
        rows.insert(0, naver)
    naver.update(weeks=weeks, total=sum(weeks))
    combined = [sum(number(row.get("weeks", [0] * 5)[index]) for row in rows) for index in range(5)]
    metrics_data["autoAdCostTotal"] = {"name": "광고비 합계", "weeks": [whole(value) for value in combined], "total": whole(sum(combined))}
    data["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    target.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"month": args.month, "period": period, "rows": len(frame), "cost": totals["총비용"], "revenue": totals["전환매출"], "weeks": weeks, "campaigns": len(campaigns), "adgroups": len(adgroups), "details": len(details), "shoppingItems": len(data["dailyProductCosts"]["items"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
