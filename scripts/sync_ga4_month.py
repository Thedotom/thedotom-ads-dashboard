from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, OrderBy, RunReportRequest
from google.oauth2 import service_account


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CREDENTIALS = Path(r"D:\광고보고서\state\ga4-service-account.json")
CLASSIFICATION_PATH = ROOT / "data" / "utm-classification.json"


def scalar(value: str, metric_type: str) -> int | float:
    number = float(value or 0)
    if metric_type in {"TYPE_INTEGER", "TYPE_SECONDS"}:
        return int(round(number))
    return number


def run_report(
    client: BetaAnalyticsDataClient,
    property_id: str,
    start_date: str,
    end_date: str,
    dimensions: list[str],
    metrics: list[str],
    limit: int = 100,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimensions=[Dimension(name=name) for name in dimensions],
        metrics=[Metric(name=name) for name in metrics],
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name=metrics[0]), desc=True)] if dimensions else [],
        limit=limit,
    )
    response = client.run_report(request)
    metric_types = {header.name: header.type_.name for header in response.metric_headers}
    rows = []
    for source in response.rows:
        row = {header.name: value.value for header, value in zip(response.dimension_headers, source.dimension_values)}
        row.update({
            header.name: scalar(value.value, metric_types[header.name])
            for header, value in zip(response.metric_headers, source.metric_values)
        })
        rows.append(row)
    metadata = {
        "currencyCode": response.metadata.currency_code,
        "timeZone": response.metadata.time_zone,
        "rowCount": response.row_count,
    }
    return rows, metadata


def classify_source_rows(rows: list[dict[str, Any]], taxonomy: dict[str, Any]) -> list[dict[str, Any]]:
    source_map = taxonomy.get("sources") or {}
    medium_map = taxonomy.get("mediums") or {}
    result = []
    for source in rows:
        row = dict(source)
        value = str(row.get("sessionSourceMedium") or "")
        source_name, _, medium_name = value.partition(" / ")
        source_key, medium_key = source_name.lower(), medium_name.lower()
        medium_rule = medium_map.get(medium_key) or {}
        missing_source = source_key in {"", "(not set)"}
        mapped = bool(medium_rule) and not missing_source
        row.update(
            sourceKey=source_key,
            mediumKey=medium_key,
            sourceLabel=("소스 누락" if missing_source else source_map.get(source_key, source_name)),
            mediumLabel=medium_rule.get("label", medium_name or "미분류"),
            channelGroup=medium_rule.get("group", "미분류"),
            isMapped=mapped,
            qualityIssue=("utm_source 누락" if missing_source else ("utm_medium 미등록" if not medium_rule else "")),
        )
        result.append(row)
    return result


def classify_campaign_rows(rows: list[dict[str, Any]], taxonomy: dict[str, Any]) -> list[dict[str, Any]]:
    campaign_map = taxonomy.get("campaigns") or {}
    system_names = {"(direct)", "(referral)", "(organic)", "(cross-network)"}
    result = []
    for source in rows:
        row = dict(source)
        raw = str(row.get("sessionCampaignName") or "")
        key = raw.lower()
        rule = campaign_map.get(key) or {}
        missing = key in {"", "(not set)"}
        system = key in system_names
        row.update(
            campaignKey=key,
            campaignLabel=rule.get("label", raw or "캠페인 누락"),
            device=rule.get("device", "미분류"),
            isMapped=bool(rule) or system,
            qualityIssue=("utm_campaign 누락" if missing else ("등록되지 않은 캠페인" if not rule and not system else "")),
        )
        result.append(row)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync one month of GA4 data into the dashboard JSON.")
    parser.add_argument("--month", required=True, help="Month in YYYY-MM format")
    parser.add_argument("--property-id", default="434716547")
    parser.add_argument("--credentials", type=Path, default=DEFAULT_CREDENTIALS)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args()

    year, month = map(int, args.month.split("-"))
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    start_date = f"{args.month}-01"
    end_date = (next_month.date() - timedelta(days=1)).isoformat()
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    if start_date <= today.isoformat() < end_date:
        end_date = today.isoformat()

    credentials = service_account.Credentials.from_service_account_file(args.credentials)
    client = BetaAnalyticsDataClient(credentials=credentials)
    summary_rows, metadata = run_report(
        client, args.property_id, start_date, end_date, [],
        ["sessions", "totalUsers", "newUsers", "engagedSessions", "engagementRate", "transactions", "purchaseRevenue"],
        1,
    )
    daily, _ = run_report(
        client, args.property_id, start_date, end_date, ["date"],
        ["sessions", "totalUsers", "transactions", "purchaseRevenue"],
        100,
    )
    sources, _ = run_report(
        client, args.property_id, start_date, end_date, ["sessionSourceMedium"],
        ["sessions", "totalUsers", "transactions", "purchaseRevenue"],
        100,
    )
    channels, _ = run_report(
        client, args.property_id, start_date, end_date, ["sessionDefaultChannelGroup"],
        ["sessions", "totalUsers", "transactions", "purchaseRevenue"],
        50,
    )
    campaigns, _ = run_report(
        client, args.property_id, start_date, end_date, ["sessionCampaignName"],
        ["sessions", "totalUsers", "transactions", "purchaseRevenue"],
        100,
    )
    products, _ = run_report(
        client, args.property_id, start_date, end_date, ["itemId", "itemName", "itemCategory"],
        ["itemRevenue", "itemsPurchased", "itemsAddedToCart", "itemsViewed"],
        10_000,
    )

    taxonomy = json.loads(CLASSIFICATION_PATH.read_text(encoding="utf-8-sig"))
    sources = classify_source_rows(sources, taxonomy)
    campaigns = classify_campaign_rows(campaigns, taxonomy)
    total_sessions = int((summary_rows[0] if summary_rows else {}).get("sessions", 0) or 0)
    source_session_total = sum(int(row.get("sessions", 0) or 0) for row in sources)
    mapped_sessions = sum(int(row.get("sessions", 0) or 0) for row in sources if row.get("isMapped"))
    missing_source_sessions = sum(int(row.get("sessions", 0) or 0) for row in sources if row.get("qualityIssue") == "utm_source 누락")
    missing_campaign_sessions = sum(int(row.get("sessions", 0) or 0) for row in campaigns if row.get("qualityIssue") == "utm_campaign 누락")
    shopping_rows = [row for row in sources if row.get("sourceKey") == "naver" and row.get("mediumKey") == "ns"]
    shopping_measurement = {
        "utmSource": "naver",
        "utmMedium": "ns",
        "sessions": sum(int(row.get("sessions", 0) or 0) for row in shopping_rows),
        "transactions": sum(int(row.get("transactions", 0) or 0) for row in shopping_rows),
        "purchaseRevenue": sum(float(row.get("purchaseRevenue", 0) or 0) for row in shopping_rows),
        "status": "확인" if shopping_rows and any(int(row.get("sessions", 0) or 0) > 0 for row in shopping_rows) else "UTM 미수집",
        "nextAction": "쇼핑검색 랜딩 URL에 utm_source=naver&utm_medium=ns를 적용한 뒤 7일 이상 관측"
    }

    target = args.data_dir / f"monthly-dashboard-{args.month}.json"
    data = json.loads(target.read_text(encoding="utf-8-sig"))
    summary = summary_rows[0] if summary_rows else {name: 0 for name in [
        "sessions", "totalUsers", "newUsers", "engagedSessions", "engagementRate", "transactions", "purchaseRevenue"
    ]}
    data["ga4Analytics"] = {
        "propertyId": args.property_id,
        "period": {"startDate": start_date, "endDate": end_date},
        "updatedAt": datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S"),
        "source": "Google Analytics Data API",
        "currencyCode": metadata.get("currencyCode") or "KRW",
        "timeZone": metadata.get("timeZone") or "Asia/Seoul",
        "summary": summary,
        "daily": sorted(daily, key=lambda row: row.get("date", "")),
        "sourceMedium": sources,
        "channels": channels,
        "campaigns": campaigns,
        "products": products,
        "utmQuality": {
            "mappedSessions": mapped_sessions,
            "unmappedSessions": max(0, source_session_total - mapped_sessions),
            "missingSourceSessions": missing_source_sessions,
            "missingCampaignSessions": missing_campaign_sessions,
            "mappingCoverage": mapped_sessions / source_session_total if source_session_total else 0,
        },
        "utmClassificationUpdatedAt": taxonomy.get("updatedAt"),        "shoppingSearchMeasurement": shopping_measurement,
        "note": "GA4는 태그가 설치된 자사몰의 방문·구매 행동 기준이며 스마트스토어·무라 매출은 포함하지 않습니다.",
    }
    target.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"updated {target}")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()

