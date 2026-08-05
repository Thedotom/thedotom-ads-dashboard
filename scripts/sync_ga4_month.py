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
        "note": "GA4는 태그가 설치된 자사몰의 방문·구매 행동 기준이며 스마트스토어·무라 매출은 포함하지 않습니다.",
    }
    target.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"updated {target}")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()

